"""
Import massif depuis l'API Aides-Territoires (ANCT / beta.gouv.fr).
~3000+ aides France — la plus grosse base nationale.
Usage: docker exec kafundo-backend python -m app.data.import_aides_territoires
"""
import asyncio
import hashlib
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from slugify import slugify
from sqlalchemy import text

from app.database import AsyncSessionLocal

API_TOKEN = "16ddf385b7472fcdd87ddb7bb3c1854da0c522e0363deca064fc5d49728c03d8"
AUTH_URL = "https://aides-territoires.beta.gouv.fr/api/connexion/"
AIDS_URL = "https://aides-territoires.beta.gouv.fr/api/aids/?format=json&page_size=50"

SOURCE_NAME = "Aides-territoires (ANCT) - toutes aides France"
SOURCE_ORGANISM = "ANCT / Aides-territoires"

AID_TYPE_MAP = {
    "grant": "subvention",
    "loan": "pret",
    "recoverable_advance": "pret",
    "technical_engineering": "accompagnement",
    "financial_engineering": "accompagnement",
    "legal_engineering": "accompagnement",
    "tax_credit": "credit_impot",
    "other": "subvention",
    "cee": "subvention",
}

AUDIENCE_MAP = {
    "commune": "collectivite",
    "epci": "collectivite",
    "department": "collectivite",
    "region": "collectivite",
    "association": "association",
    "private_sector": "pme",
    "public_cies": "institution_publique",
    "public_org": "institution_publique",
    "researcher": "chercheur",
    "farmer": "agriculteur",
}

CATEGORY_SECTOR_MAP = {
    "culture": "culture",
    "economie": "finance",
    "environnement": "environnement",
    "agriculture": "agriculture",
    "eau": "eau",
    "energie": "energie",
    "industrie": "industrie",
    "numerique": "numerique",
    "sante": "sante",
    "social": "social",
    "education": "education",
    "tourisme": "tourisme",
    "transport": "transport",
    "urbanisme": "urbanisme",
}


def clean_html(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r"<br\s*/?>", "\n", txt)
    txt = re.sub(r"<li>", "\n- ", txt)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"&amp;", "&", txt)
    txt = re.sub(r"&lt;", "<", txt)
    txt = re.sub(r"&gt;", ">", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r" {2,}", " ", txt)
    return txt.strip()


def parse_date(d):
    if not d:
        return None
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def detect_device_type(aid_types: list) -> str:
    if not aid_types:
        return "subvention"
    for at in aid_types:
        slug = at if isinstance(at, str) else at.get("slug", "")
        if slug in AID_TYPE_MAP:
            return AID_TYPE_MAP[slug]
    return "subvention"


def build_beneficiaries(targeted_audiences: list) -> list[str]:
    bens = set()
    for ta in (targeted_audiences or []):
        slug = ta if isinstance(ta, str) else ta.get("slug", "")
        if slug in AUDIENCE_MAP:
            bens.add(AUDIENCE_MAP[slug])
    if not bens:
        bens.add("pme")
    return sorted(bens)


def build_sectors(categories: list) -> list[str]:
    secs = set()
    for cat in (categories or []):
        name = cat if isinstance(cat, str) else cat.get("name", "")
        name_lower = name.lower()
        for key, sector in CATEGORY_SECTOR_MAP.items():
            if key in name_lower:
                secs.add(sector)
                break
    if not secs:
        secs.add("transversal")
    return sorted(secs)


def extract_organism(financers, financers_full):
    if financers_full:
        names = [f.get("name", "") if isinstance(f, dict) else str(f) for f in financers_full[:3]]
        return ", ".join(n for n in names if n)[:200]
    if financers:
        return ", ".join(str(f) for f in financers[:3])[:200]
    return SOURCE_ORGANISM


def extract_region(perimeter, perimeter_scale):
    if not perimeter:
        return None
    name = perimeter if isinstance(perimeter, str) else perimeter.get("name", "")
    scale = perimeter_scale or ""
    if scale in ("country", "continent", "europe"):
        return None
    if name and name.lower() not in ("france", "métropole", "outre-mer"):
        return name[:100]
    return None


async def get_bearer_token() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(AUTH_URL, headers={"X-AUTH-TOKEN": API_TOKEN})
        resp.raise_for_status()
        data = resp.json()
        return data["token"]


async def fetch_all_aids(bearer: str) -> list[dict]:
    aids = []
    url = AIDS_URL
    async with httpx.AsyncClient(timeout=60) as client:
        page = 0
        while url:
            page += 1
            resp = await client.get(url, headers={"Authorization": f"Bearer {bearer}"})
            if resp.status_code == 401:
                print("Token expiré, renouvellement...", flush=True)
                bearer = await get_bearer_token()
                continue
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            aids.extend(results)
            url = data.get("next")
            if page % 10 == 0:
                print(f"  page {page}: {len(aids)} aides chargées...", flush=True)
            await asyncio.sleep(0.2)
    return aids


async def ensure_source(db) -> str:
    r = await db.execute(text(
        "SELECT id FROM sources WHERE name = :n"
    ), {"n": SOURCE_NAME})
    existing = r.scalar_one_or_none()
    if existing:
        return str(existing)

    source_id = str(uuid4())
    await db.execute(text("""
        INSERT INTO sources (id, name, organism, country, source_type, level, url,
                             collection_mode, check_frequency, reliability, category,
                             is_active, created_at, updated_at)
        VALUES (:id, :name, :organism, 'France', 'portail_officiel', 1, :url,
                'api_import', 'daily', 5, 'financement',
                true, NOW(), NOW())
    """), {
        "id": source_id,
        "name": SOURCE_NAME,
        "organism": SOURCE_ORGANISM,
        "url": "https://aides-territoires.beta.gouv.fr/api/aids/",
    })
    await db.commit()
    print(f"Source créée: {source_id}")
    return source_id


async def main():
    print("=== Authentification ===", flush=True)
    bearer = await get_bearer_token()
    print(f"Bearer obtenu: {bearer[:20]}...", flush=True)

    print("=== Récupération des aides ===", flush=True)
    aids = await fetch_all_aids(bearer)
    print(f"Total: {len(aids)} aides récupérées", flush=True)

    async with AsyncSessionLocal() as db:
        source_id = await ensure_source(db)

        existing = await db.execute(text(
            "SELECT source_hash FROM devices WHERE source_id = :sid"
        ), {"sid": source_id})
        existing_hashes = {row[0] for row in existing.fetchall()}
        print(f"{len(existing_hashes)} fiches déjà importées", flush=True)

        ok = 0
        skipped = 0
        errors = 0
        expired_skip = 0

        for i, aid in enumerate(aids):
            try:
                title = (aid.get("name") or "").strip()
                if not title or len(title) < 5:
                    skipped += 1
                    continue

                aid_id = str(aid.get("id", ""))
                content_hash = hashlib.sha256(f"at:{aid_id}:{title}".encode()).hexdigest()
                if content_hash in existing_hashes:
                    skipped += 1
                    continue

                # Check deadline
                deadline = parse_date(aid.get("submission_deadline"))
                if deadline and deadline < datetime.now(timezone.utc):
                    expired_skip += 1
                    continue

                description = clean_html(aid.get("description") or "")
                eligibility = clean_html(aid.get("eligibility") or "")
                project_examples = clean_html(aid.get("project_examples") or "")
                contact = clean_html(aid.get("contact") or "")

                short_desc = description[:500] if description else title
                full_parts = []
                if description:
                    full_parts.append(f"## Présentation\n{description}")
                if eligibility:
                    full_parts.append(f"## Conditions d'éligibilité\n{eligibility}")
                if project_examples:
                    full_parts.append(f"## Exemples de projets\n{project_examples}")
                if contact:
                    full_parts.append(f"## Contact\n{contact}")
                full_desc = "\n\n".join(full_parts) if full_parts else short_desc

                device_type = detect_device_type(aid.get("aid_types") or aid.get("aid_types_full", []))
                beneficiaries = build_beneficiaries(aid.get("targeted_audiences"))
                sectors = build_sectors(aid.get("categories", []))
                organism = extract_organism(aid.get("financers"), aid.get("financers_full"))
                region = extract_region(aid.get("perimeter"), aid.get("perimeter_scale"))

                recurrence = aid.get("recurrence") or ""
                is_recurring = recurrence in ("recurring", "ongoing")
                status = "recurring" if is_recurring else "open"
                start_date = parse_date(aid.get("start_date"))

                source_url = aid.get("origin_url") or aid.get("application_url") or aid.get("url") or ""
                if not source_url:
                    source_url = f"https://aides-territoires.beta.gouv.fr/aides/{aid.get('slug', aid_id)}/"

                # Funding info
                funding_parts = []
                sub_lower = aid.get("subvention_rate_lower_bound")
                sub_upper = aid.get("subvention_rate_upper_bound")
                if sub_lower or sub_upper:
                    if sub_lower and sub_upper:
                        funding_parts.append(f"Taux de subvention : {sub_lower}% à {sub_upper}%")
                    elif sub_upper:
                        funding_parts.append(f"Taux de subvention : jusqu'à {sub_upper}%")
                sub_comment = aid.get("subvention_comment")
                if sub_comment:
                    funding_parts.append(clean_html(sub_comment))
                loan = aid.get("loan_amount")
                if loan:
                    funding_parts.append(f"Montant du prêt : {loan}")
                funding_details = "\n".join(funding_parts) if funding_parts else None

                slug = f"at-{slugify(title, max_length=60) or aid_id}"

                device_id = uuid4()
                await db.execute(text("""
                    INSERT INTO devices (
                        id, slug, title, title_normalized, organism, country, region,
                        device_type, sectors, beneficiaries,
                        short_description, full_description, eligibility_criteria,
                        funding_details, open_date, close_date, status, is_recurring,
                        source_id, source_url, source_hash, language,
                        keywords, tags, confidence_score, completeness_score,
                        validation_status, created_at, updated_at
                    ) VALUES (
                        :id, :slug, :title, :title_norm, :organism, 'France', :region,
                        :dtype, :sectors, :bens,
                        :short, :full, :elig,
                        :funding, :open_date, :close_date, :status, :recurring,
                        :source_id, :source_url, :hash, 'fr',
                        :keywords, :tags, 85, 80,
                        'auto_published', NOW(), NOW()
                    ) ON CONFLICT (slug) DO UPDATE SET
                        title=EXCLUDED.title, short_description=EXCLUDED.short_description,
                        full_description=EXCLUDED.full_description, eligibility_criteria=EXCLUDED.eligibility_criteria,
                        funding_details=EXCLUDED.funding_details, close_date=EXCLUDED.close_date,
                        status=EXCLUDED.status, organism=EXCLUDED.organism, updated_at=NOW()
                """), {
                    "id": str(device_id),
                    "slug": slug,
                    "title": title,
                    "title_norm": title.lower(),
                    "organism": organism,
                    "region": region,
                    "dtype": device_type,
                    "sectors": sectors,
                    "bens": beneficiaries,
                    "short": short_desc[:1000],
                    "full": full_desc[:15000],
                    "elig": eligibility[:5000] if eligibility else None,
                    "funding": funding_details[:3000] if funding_details else None,
                    "open_date": start_date,
                    "close_date": deadline,
                    "status": status,
                    "recurring": is_recurring,
                    "source_id": source_id,
                    "source_url": source_url[:500],
                    "hash": content_hash,
                    "keywords": [w for w in re.findall(r'\w+', title.lower()) if len(w) > 3][:10],
                    "tags": [f"source:aides-territoires", f"type:{device_type}"],
                })
                ok += 1
                existing_hashes.add(content_hash)

                if ok % 200 == 0:
                    await db.commit()
                    print(f"  {ok} importés, {skipped} ignorés, {expired_skip} expirés...", flush=True)

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  ERR aide {i}: {str(e)[:150]}", flush=True)
                try:
                    await db.rollback()
                except Exception:
                    pass

        await db.commit()
        print(f"\nTERMINÉ: {ok} importés, {skipped} ignorés, {expired_skip} expirés skip, {errors} erreurs", flush=True)

        # Réinitialiser le compteur d'erreurs de la source
        await db.execute(text("""
            UPDATE sources SET consecutive_errors = 0, last_success_at = NOW(), last_checked_at = NOW()
            WHERE name = :n
        """), {"n": SOURCE_NAME})
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
