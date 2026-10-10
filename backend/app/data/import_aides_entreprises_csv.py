"""
Import massif depuis le CSV public data.aides-entreprises.fr
~45k fiches France — source officielle, pas besoin d'API key.
Usage: docker exec kafundo-backend python -m app.data.import_aides_entreprises_csv [--dry-run]

Nettoyage du catalogue (octobre 2026) — pourquoi cette version
--------------------------------------------------------------
L'audit de production a montré que les doublons de cette source ne viennent
PAS d'une réimportation à chaque modification : l'identifiant ``id_aid`` du CSV
est stable. La cause réelle est le changement de schéma de slug du
1er octobre 2026 (slug construit sur le titre -> ``fr-ae-<id_aid>``) :
les ~2 300 lignes historiques portaient un slug titre que le nouveau code ne
retrouvait plus, d'où une vague de réinsertions le 2 octobre, et l'import ne
regardait jamais les fiches des autres sources (import manuel, autres
portails). Cette version :

* retrouve d'abord la fiche existante (slug stable, puis ancien hash
  ``sha256(id_aid:titre)``, puis jumeau CERTAIN de la même source) et la
  RATTACHE au slug stable au lieu d'insérer un doublon ;
* ne crée pas une fiche dont un jumeau CERTAIN existe dans une autre source ;
* enregistre les doublons PROBABLES en file de revue, sans les fusionner ;
* ne touche jamais une fiche archivée, ni son statut de validation ;
* évalue la qualité utilisateur à l'insertion (plus de fiche publiée « jamais
  évaluée ») et ne met pas en file IA une fiche non publiable ;
* met à jour ``source_hash`` et ``title_normalized`` (clé cohérente avec le
  reste du pipeline) et conserve les statuts « standby / recurring ».
"""
import asyncio
import csv
import hashlib
import io
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
from slugify import slugify
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.ai_eligibility import initial_ai_rewrite_status
from app.services.catalog_guard import record_duplicate_candidate
from app.services.device_identity import DuplicateIndex, DuplicateTier
from app.services.user_quality import compute_user_quality
from app.utils.text_utils import normalize_title

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

KEEP_STATUSES = ("standby", "recurring", "pending_review")


def clean_text(txt: str) -> str:
    if not txt:
        return ""
    # Le CSV est décodé en cp1252 — pas de re-encodage, juste strip HTML
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
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
    # aid_id is the CSV's own stable government identifier: prefer it over the title. Truncating a
    # slugified title to max_length can cut mid multi-byte accented character, and the two halves the
    # transliteration library produces for that cut are not guaranteed stable run to run - that produced
    # a different slug for the same aid between two imports (e.g. "...exon-rat" vs "...exonerat" for
    # "Exonération"), so ON CONFLICT missed it and inserted a duplicate device instead of updating it.
    if aid_id:
        return f"fr-ae-{aid_id}"
    base = slugify(title, max_length=60) or "aide-sans-titre"
    return f"fr-ae-{base}"


def content_hash_for(aid_id: str, title: str) -> str:
    return hashlib.sha256(f"{aid_id}:{title}".encode()).hexdigest()


def build_device_fields(row: dict, now: Optional[datetime] = None) -> Optional[dict[str, Any]]:
    """Transforme une ligne CSV en champs de fiche, ou None si elle doit être ignorée.

    Pur (aucun accès base) : testé directement. Les lignes sans titre exploitable ou
    déjà expirées sont ignorées, comme avant.
    """
    now = now or datetime.now(timezone.utc)
    aid_id = (row.get("id_aid") or "").strip()
    title = clean_text(row.get("aid_nom") or "")
    if not title or len(title) < 5:
        return None

    close_date = parse_date(row.get("date_fin") or "")
    if close_date and close_date < now:
        return None

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

    device_type = detect_device_type(row.get("natures") or "")

    geo = clean_text(row.get("couverture_geo") or "")
    region = None
    if geo and geo.lower() not in ("france", "national", ""):
        region = geo[:100]

    financeurs = clean_text(row.get("financeurs") or "")
    # financeurs peut contenir des IDs numériques internes — fallback sur SOURCE_ORGANISM
    organism = (
        financeurs[:150]
        if financeurs and not re.match(r'^[\d\s,;/]+$', financeurs.strip())
        else SOURCE_ORGANISM
    )

    sources_links = clean_text(row.get("complements_sources") or "")
    source_url_match = re.search(r'https?://[^\s"<>]+', sources_links)
    source_url = source_url_match.group(0) if source_url_match else f"https://www.aides-entreprises.fr/aide/{aid_id}"

    return {
        "aid_id": aid_id,
        "slug": make_slug(title, aid_id),
        "title": title,
        "title_normalized": normalize_title(title),
        "organism": organism,
        "country": "France",
        "region": region,
        "device_type": device_type,
        "sectors": build_sectors(row),
        "beneficiaries": build_beneficiaries(row),
        "short_description": short_desc[:1000],
        "full_description": full_desc[:10000],
        "eligibility_criteria": conditions[:3000] if conditions else None,
        "funding_details": montant[:2000] if montant else None,
        "close_date": close_date,
        "status": "open",
        "source_url": source_url[:500],
        "source_hash": content_hash_for(aid_id, title),
        "keywords": [w for w in re.findall(r'\w+', title.lower()) if len(w) > 3][:10],
        "tags": ["source:aides-entreprises", f"type:{device_type}"],
    }


# --- planification (pure) -----------------------------------------------------

@dataclass
class ImportDecision:
    action: str                       # insert | update | adopt | update_keeper | skip_duplicate | skip_archived
    device_id: Optional[Any] = None   # fiche existante concernée (update / adopt / skip_*)
    reason: str = ""
    candidates: list = field(default_factory=list)  # (autre fiche, Assessment) PROBABLES


class ImportIndex:
    """Fiches connues, pour décider sans requête par ligne."""

    def __init__(self, devices: list[dict], source_id: Any, merges: Optional[dict] = None):
        self.source_id = str(source_id)
        #: doublon archivé (id) -> fiche conservée (id), d'après le journal d'archivage
        self.merged_into = {str(k): v for k, v in (merges or {}).items()}
        self.by_id = {str(d["id"]): d for d in devices}
        self.by_slug = {d["slug"]: d for d in devices if d.get("slug")}
        self.by_hash = {
            d["source_hash"]: d for d in devices
            if d.get("source_hash") and str(d.get("source_id")) == self.source_id
        }
        self.similarity = DuplicateIndex(devices)

    def register(self, fields: dict, device_id: Any) -> None:
        record = {
            "id": device_id, "slug": fields["slug"], "title": fields["title"], "organism": fields["organism"],
            "country": fields["country"], "source_url": fields["source_url"], "source_hash": fields["source_hash"],
            "source_id": self.source_id, "validation_status": "auto_published",
        }
        self.by_slug[record["slug"]] = record
        self.by_hash[record["source_hash"]] = record
        self.similarity = DuplicateIndex(list(self.by_slug.values()))


def _archived_decision(index: ImportIndex, archived: dict, reason: str) -> ImportDecision:
    """Fiche archivée : si c'est un doublon fusionné, on met à jour la fiche conservée.

    Sans cela, la fiche conservée (qui porte un autre slug) ne recevrait plus jamais les
    mises à jour de la source, puisque le slug stable appartient au doublon archivé.
    """
    keeper_id = index.merged_into.get(str(archived["id"]))
    keeper = index.by_id.get(str(keeper_id)) if keeper_id else None
    if keeper is not None and keeper.get("validation_status") != "archived":
        return ImportDecision("update_keeper", keeper["id"], "follow_merge")
    return ImportDecision("skip_archived", archived["id"], reason)


def plan_import_row(fields: dict, index: ImportIndex) -> ImportDecision:
    existing = index.by_slug.get(fields["slug"])
    if existing is not None:
        if existing.get("validation_status") == "archived":
            return _archived_decision(index, existing, "slug_archived")
        return ImportDecision("update", existing["id"], "stable_slug")

    legacy = index.by_hash.get(fields["source_hash"])
    if legacy is not None:
        if legacy.get("validation_status") == "archived":
            return _archived_decision(index, legacy, "legacy_hash_archived")
        return ImportDecision("adopt", legacy["id"], "legacy_hash")

    probable = []
    twin_other_source = None
    for other, assessment in index.similarity.assess({**fields, "id": None}):
        if assessment.tier is DuplicateTier.CERTAIN:
            if str(other.get("source_id")) == index.source_id:
                if other.get("validation_status") == "archived":
                    return _archived_decision(index, other, "twin_archived")
                return ImportDecision("adopt", other["id"], "same_source_certain_twin")
            twin_other_source = twin_other_source or other
        elif assessment.tier is DuplicateTier.PROBABLE:
            probable.append((other, assessment))
    if twin_other_source is not None:
        return ImportDecision("skip_duplicate", twin_other_source["id"], "certain_twin_other_source")
    return ImportDecision("insert", None, "new", candidates=probable)


# --- accès base ---------------------------------------------------------------

async def ensure_source(db: AsyncSession):
    r = await db.execute(
        select(text("id")).select_from(text("sources")).where(text("name = :n")), {"n": SOURCE_NAME}
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


async def _load_index(db: AsyncSession, source_id) -> ImportIndex:
    rows = (await db.execute(text("""
        SELECT id, slug, title, organism, country, source_url, source_hash, source_id, validation_status
        FROM devices
    """))).mappings().all()
    merges = {
        row[0]: row[1] for row in (await db.execute(text(
            "SELECT device_id, merged_into_id FROM device_archive_log "
            "WHERE action = 'archive' AND merged_into_id IS NOT NULL AND restored_at IS NULL"
        ))).all()
    }
    return ImportIndex([dict(row) for row in rows], source_id, merges)


_UPSERT = text("""
    INSERT INTO devices (
        id, slug, title, title_normalized, organism, country, region,
        device_type, sectors, beneficiaries,
        short_description, full_description, eligibility_criteria,
        funding_details, close_date, status, is_recurring,
        source_id, source_url, source_hash, language,
        keywords, tags, confidence_score, completeness_score,
        ai_readiness_score, user_quality_score, user_quality_decision, user_quality_reasons,
        ai_rewrite_status, validation_status, created_at, updated_at
    ) VALUES (
        :id, :slug, :title, :title_normalized, :organism, 'France', :region,
        :device_type, :sectors, :beneficiaries,
        :short_description, :full_description, :eligibility_criteria,
        :funding_details, :close_date, :status, false,
        :source_id, :source_url, :source_hash, 'fr',
        :keywords, :tags, 75, 70,
        0, :user_quality_score, :user_quality_decision, :user_quality_reasons,
        :ai_rewrite_status, :validation_status, NOW(), NOW()
    ) ON CONFLICT (slug) DO UPDATE SET
        title=EXCLUDED.title, title_normalized=EXCLUDED.title_normalized,
        short_description=EXCLUDED.short_description,
        full_description=EXCLUDED.full_description, eligibility_criteria=EXCLUDED.eligibility_criteria,
        funding_details=EXCLUDED.funding_details, close_date=EXCLUDED.close_date,
        source_hash=EXCLUDED.source_hash, source_url=EXCLUDED.source_url,
        status=CASE WHEN devices.status IN ('standby', 'recurring', 'pending_review')
                    THEN devices.status ELSE EXCLUDED.status END,
        updated_at=NOW()
    WHERE devices.validation_status IS DISTINCT FROM 'archived'
""")


_UPDATE_KEEPER = text("""
    UPDATE devices SET
        title=:title, title_normalized=:title_normalized, short_description=:short_description,
        full_description=:full_description, eligibility_criteria=:eligibility_criteria,
        funding_details=:funding_details, close_date=:close_date,
        status=CASE WHEN status IN ('standby', 'recurring', 'pending_review') THEN status ELSE :status END,
        updated_at=NOW()
    WHERE id = :id AND validation_status IS DISTINCT FROM 'archived'
""")


def _quality(fields: dict):
    return compute_user_quality({
        **fields, "status": "open", "validation_status": "auto_published",
        "source_url": fields["source_url"], "tags": fields["tags"],
    })


async def main(dry_run: bool = False, csv_text: Optional[str] = None):
    if csv_text is None:
        print("Téléchargement du CSV...", flush=True)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(CSV_URL)
            resp.raise_for_status()
        csv_text = resp.content.decode("cp1252", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";", quotechar='"')
    rows = list(reader)
    print(f"{len(rows)} lignes CSV chargées", flush=True)

    # Filtrer : status actif
    active_rows = [r for r in rows if (r.get("status") or "").strip().lower() in ("1", "actif", "active", "")]
    print(f"{len(active_rows)} lignes actives", flush=True)

    counts = {"insert": 0, "update": 0, "adopt": 0, "update_keeper": 0, "skip_duplicate": 0, "skip_archived": 0,
              "ignored": 0, "errors": 0, "candidates": 0}

    async with AsyncSessionLocal() as db:
        source_id = await ensure_source(db)
        index = await _load_index(db, source_id)
        print(f"{len(index.by_slug)} fiches connues (toutes sources)", flush=True)

        for i, row in enumerate(active_rows):
            try:
                fields = build_device_fields(row)
                if fields is None:
                    counts["ignored"] += 1
                    continue
                decision = plan_import_row(fields, index)
                counts[decision.action] += 1
                if dry_run or decision.action in ("skip_duplicate", "skip_archived"):
                    continue

                if decision.action == "adopt":
                    # Rattache la fiche existante au slug stable (aucune duplication).
                    await db.execute(
                        text("UPDATE devices SET slug = :slug WHERE id = :id AND validation_status IS DISTINCT FROM 'archived'"),
                        {"slug": fields["slug"], "id": str(decision.device_id)},
                    )

                if decision.action == "update_keeper":
                    await db.execute(_UPDATE_KEEPER, {
                        **{k: v for k, v in fields.items() if k not in ("aid_id", "slug")}, "id": str(decision.device_id),
                    })
                    continue

                quality = _quality(fields)
                publishable = quality.decision in ("publish", "publish_with_caution")
                params = {
                    **{k: v for k, v in fields.items() if k != "aid_id"},
                    "id": str(decision.device_id or uuid4()),
                    "source_id": str(source_id),
                    "user_quality_score": quality.score,
                    "user_quality_decision": quality.decision,
                    "user_quality_reasons": quality.reasons,
                    "ai_rewrite_status": initial_ai_rewrite_status("auto_published" if publishable else "admin_only"),
                    "validation_status": "auto_published",
                }
                await db.execute(_UPSERT, params)
                if decision.action == "insert":
                    index.register(fields, params["id"])
                    for other, assessment in decision.candidates:
                        await record_duplicate_candidate(db, params["id"], other["id"], assessment)
                        counts["candidates"] += 1

                if (counts["insert"] + counts["update"] + counts["adopt"]) % 500 == 0:
                    await db.commit()
                    print(f"  {counts}", flush=True)

            except Exception as e:
                counts["errors"] += 1
                if counts["errors"] <= 3:
                    print(f"  ERR ligne {i}: {str(e)[:150]}", flush=True)
                await db.rollback()

        if dry_run:
            await db.rollback()
            print(f"\nSIMULATION (rien n'est écrit): {counts}", flush=True)
            return counts

        await db.commit()
        print(f"\nTERMINÉ: {counts}", flush=True)

        # Réinitialiser le compteur d'erreurs de la source
        await db.execute(text("""
            UPDATE sources SET consecutive_errors = 0, last_success_at = NOW(), last_checked_at = NOW()
            WHERE name = :n
        """), {"n": SOURCE_NAME})
        await db.commit()
        return counts


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
