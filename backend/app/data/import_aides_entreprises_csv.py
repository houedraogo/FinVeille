"""
Import massif depuis le CSV public data.aides-entreprises.fr
~45k fiches France — source officielle, pas besoin d'API key.
Usage: docker exec kafundo-backend python -m app.data.import_aides_entreprises_csv
"""
import asyncio
import csv
import hashlib
import io
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from slugify import slugify
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

CSV_URL = "https://data.aides-entreprises.fr/files/aides.csv"

SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises (CSV)"
SOURCE_ORGANISM = "DGE / aides-entreprises.fr"

NATURE_MAP = {
    "subvention": "subvention",
    "prêt": "pret",
    "pret": "pret",
    "avance": "pret",
    "garantie": "garantie",
    "exonération": "exoneration",
    "exoneration": "exoneration",
    "crédit d'impôt": "credit_impot",
    "credit d'impot": "credit_impot",
    "allègement": "exoneration",
    "bonification": "subvention",
}

DOMAINE_TO_SECTOR = {
    "1": "industrie",
    "2": "commerce",
    "3": "artisanat",
    "4": "agriculture",
    "5": "tourisme",
    "6": "environnement",
    "7": "numerique",
    "8": "culture",
    "9": "sante",
    "10": "social",
    "11": "education",
    "12": "transversal",
}


def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = txt.encode("latin-1", errors="ignore").decode("utf-8", errors="replace")
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = txt.replace("\x92", "'").replace("\x93", '"').replace("\x94", '"')
    txt = txt.replace("�", "'")
    return txt


def parse_date(d: str):
    if not d or d.strip() in ("", "0000-00-00"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def detect_device_type(natures: str) -> str:
    natures_lower = (natures or "").lower()
    for key, dtype in NATURE_MAP.items():
        if key in natures_lower:
            return dtype
    return "subvention"


def build_beneficiaries(row: dict) -> list[str]:
    bens = []
    profils = (row.get("profils") or "").lower()
    if "auto-entrepreneur" in profils or "micro" in profils:
        bens.append("auto_entrepreneur")
    if "tpe" in profils or "artisan" in profils:
        bens.append("tpe")
    if "pme" in profils:
        bens.append("pme")
    if "eti" in profils:
        bens.append("eti")
    if "association" in profils:
        bens.append("association")
    if "startup" in profils or "jeune entreprise" in profils:
        bens.append("startup")
    if not bens:
        bens = ["pme", "tpe"]
    return bens


def build_sectors(row: dict) -> list[str]:
    domaine = row.get("id_domaine", "")
    sectors = set()
    for d in str(domaine).split(","):
        d = d.strip()
        if d in DOMAINE_TO_SECTOR:
            sectors.add(DOMAINE_TO_SECTOR[d])
    if not sectors:
        sectors.add("transversal")
    return sorted(sectors)


def make_slug(title: str, aid_id: str) -> str:
    base = slugify(title, max_length=60) or f"aide-{aid_id}"
    return f"fr-ae-{base}"


async def ensure_source(db: AsyncSession):
    r = await db.execute(
        select(text("id")).select_from(text("sources")).where(text(f"name = '{SOURCE_NAME}'"))
    )
    existing = r.scalar_one_or_none()
    if existing:
        return existing

    source_id = uuid4()
    await db.execute(text("""
        INSERT INTO sources (id, name, organism, country, source_type, level, url,
                             collection_mode, check_frequency, reliability, category,
                             is_active, created_at, updated_at)
        VALUES (:id, :name, :organism, 'France', 'portail_officiel', 1, :url,
                'csv_import', 'weekly', 5, 'financement',
                true, NOW(), NOW())
    """), {
        "id": str(source_id),
        "name": SOURCE_NAME,
        "organism": SOURCE_ORGANISM,
        "url": CSV_URL,
    })
    await db.commit()
    print(f"Source créée: {source_id}")
    return source_id


async def main():
    print("Téléchargement du CSV...", flush=True)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(CSV_URL)
        resp.raise_for_status()

    raw = resp.content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(raw), delimiter=";", quotechar='"')
    rows = list(reader)
    print(f"{len(rows)} lignes CSV chargées", flush=True)

    # Filtrer : status actif, pas de doublon titre
    active_rows = [r for r in rows if (r.get("status") or "").strip().lower() in ("1", "actif", "active", "")]
    print(f"{len(active_rows)} lignes actives", flush=True)

    async with AsyncSessionLocal() as db:
        source_id = await ensure_source(db)

        existing = await db.execute(text(
            "SELECT source_hash FROM devices WHERE source_id = :sid"
        ), {"sid": str(source_id)})
        existing_hashes = {row[0] for row in existing.fetchall()}
        print(f"{len(existing_hashes)} fiches déjà importées", flush=True)

        ok = 0
        skipped = 0
        errors = 0

        for i, row in enumerate(active_rows):
            try:
                aid_id = (row.get("id_aid") or "").strip()
                title = clean_text(row.get("aid_nom") or "")
                if not title or len(title) < 5:
                    skipped += 1
                    continue

                content_hash = hashlib.sha256(f"{aid_id}:{title}".encode()).hexdigest()
                if content_hash in existing_hashes:
                    skipped += 1
                    continue

                objet = clean_text(row.get("aid_objet") or "")
                conditions = clean_text(row.get("aid_conditions") or "")
                montant = clean_text(row.get("aid_montant") or "")
                operations = clean_text(row.get("aid_operations_el") or "")
                beneficiaires_txt = clean_text(row.get("aid_benef") or "")

                short_desc = objet[:500] if objet else title
                full_parts = []
                if objet:
                    full_parts.append(f"## Présentation\n{objet}")
                if operations:
                    full_parts.append(f"## Opérations éligibles\n{operations}")
                if conditions:
                    full_parts.append(f"## Conditions\n{conditions}")
                if montant:
                    full_parts.append(f"## Montant\n{montant}")
                if beneficiaires_txt:
                    full_parts.append(f"## Bénéficiaires\n{beneficiaires_txt}")
                full_desc = "\n\n".join(full_parts) if full_parts else short_desc

                close_date = parse_date(row.get("date_fin") or "")
                status = "open"
                if close_date and close_date < datetime.now(timezone.utc):
                    status = "expired"
                    skipped += 1
                    continue

                device_type = detect_device_type(row.get("natures") or "")
                beneficiaries = build_beneficiaries(row)
                sectors = build_sectors(row)
                slug = make_slug(title, aid_id)

                geo = clean_text(row.get("couverture_geo") or "")
                region = None
                if geo and geo.lower() not in ("france", "national", ""):
                    region = geo[:100]

                financeurs = clean_text(row.get("financeurs") or "")
                organism = financeurs[:150] if financeurs else SOURCE_ORGANISM

                sources_links = clean_text(row.get("complements_sources") or "")
                source_url_match = re.search(r'https?://[^\s"<>]+', sources_links)
                source_url = source_url_match.group(0) if source_url_match else f"https://www.aides-entreprises.fr/aide/{aid_id}"

                device_id = uuid4()
                await db.execute(text("""
                    INSERT INTO devices (
                        id, slug, title, title_normalized, organism, country, region,
                        device_type, sectors, beneficiaries,
                        short_description, full_description, eligibility_criteria,
                        funding_details, close_date, status, is_recurring,
                        source_id, source_url, source_hash, language,
                        keywords, tags, confidence_score, completeness_score,
                        validation_status, created_at, updated_at
                    ) VALUES (
                        :id, :slug, :title, :title_normalized, :organism, 'France', :region,
                        :device_type, :sectors, :beneficiaries,
                        :short_desc, :full_desc, :eligibility,
                        :funding, :close_date, :status, false,
                        :source_id, :source_url, :source_hash, 'fr',
                        :keywords, :tags, 75, 70,
                        'auto_published', NOW(), NOW()
                    ) ON CONFLICT (slug) DO UPDATE SET
                        title=EXCLUDED.title, short_description=EXCLUDED.short_description,
                        full_description=EXCLUDED.full_description, eligibility_criteria=EXCLUDED.eligibility_criteria,
                        funding_details=EXCLUDED.funding_details, close_date=EXCLUDED.close_date,
                        status=EXCLUDED.status, updated_at=NOW()
                """), {
                    "id": str(device_id),
                    "slug": slug,
                    "title": title,
                    "title_normalized": title.lower(),
                    "organism": organism,
                    "region": region,
                    "device_type": device_type,
                    "sectors": sectors,
                    "beneficiaries": beneficiaries,
                    "short_desc": short_desc[:1000],
                    "full_desc": full_desc[:10000],
                    "eligibility": conditions[:3000] if conditions else None,
                    "funding": montant[:2000] if montant else None,
                    "close_date": close_date,
                    "status": status,
                    "source_id": str(source_id),
                    "source_url": source_url[:500],
                    "source_hash": content_hash,
                    "keywords": [w for w in re.findall(r'\w+', title.lower()) if len(w) > 3][:10],
                    "tags": [f"source:aides-entreprises", f"type:{device_type}"],
                })
                ok += 1
                existing_hashes.add(content_hash)

                if ok % 500 == 0:
                    await db.commit()
                    print(f"  {ok} importés, {skipped} ignorés...", flush=True)

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERR ligne {i}: {str(e)[:150]}", flush=True)
                await db.rollback()

        await db.commit()
        print(f"\nTERMINÉ: {ok} importés, {skipped} ignorés, {errors} erreurs", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
