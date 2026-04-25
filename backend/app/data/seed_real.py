"""
Collecte de données RÉELLES depuis des APIs publiques ouvertes (sans authentification).

Sources utilisées :
  - World Bank Open Data API   → projets actifs France + Afrique
  - AFD Open Data              → projets AFD en Afrique
  - ADEME data.ademe.fr        → aides ADEME aux entreprises
  - EU Funding Tenders API     → appels à propositions européens
  - private                    → VC, Business Angels, IFC, Proparco (financement privé)

Usage :
    docker compose exec backend python -m app.data.seed_real
    docker compose exec backend python -m app.data.seed_real --sources worldbank afd ademe eu private
    docker compose exec backend python -m app.data.seed_real --sources private
    docker compose exec backend python -m app.data.seed_real --limit 100
"""
import asyncio
import sys
import os
import logging
import argparse
import json
import re
from datetime import datetime, date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("seed_real")
logger.setLevel(logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=200, help="Nombre max de dispositifs à collecter par source")
parser.add_argument("--sources", nargs="*", default=["worldbank", "afd", "ademe", "eu"],
                    help="Sources à utiliser (worldbank afd ademe eu private ifc proparco)")
args, _ = parser.parse_known_args()


# ─── Mapping secteurs Banque Mondiale ────────────────────────────────────────
WB_SECTOR_MAP = {
    "agriculture": "agriculture", "rural": "agriculture", "irrigation": "eau",
    "energy": "energie", "power": "energie", "solar": "energie", "renewable": "energie",
    "health": "sante", "education": "education", "urban": "immobilier",
    "transport": "transport", "water": "eau", "sanitation": "eau",
    "finance": "finance", "digital": "numerique", "environment": "environnement",
    "climate": "environnement", "industry": "industrie", "trade": "finance",
    "social": "social", "culture": "culture",
}

WB_TYPE_MAP = {
    "loan": "pret", "grant": "subvention", "guarantee": "garantie",
    "technical assistance": "accompagnement", "investment project": "subvention",
}


def _detect_sectors_from_text(text: str) -> list:
    text_l = (text or "").lower()
    from app.collector.normalizer import SECTOR_RULES
    return [s for s, kws in SECTOR_RULES.items() if any(kw in text_l for kw in kws)] or ["transversal"]


def _parse_date_str(val) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(val)[:10], fmt[:len(str(val)[:10])]).date()
        except (ValueError, IndexError):
            pass
    return None


def _parse_amount_str(val) -> Optional[float]:
    if not val:
        return None
    try:
        clean = str(val).replace(",", "").replace(" ", "").strip()
        return float(clean) if clean else None
    except ValueError:
        return None


def _clean_seed_text(value: Optional[str]) -> str:
    from app.utils.text_utils import sanitize_text
    return sanitize_text(value or "")


def _extract_record_date(record: dict, *field_names: str) -> Optional[date]:
    from app.utils.text_utils import extract_close_date

    def candidates(value):
        if value is None:
            return
        if isinstance(value, list):
            for item in value:
                yield from candidates(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                yield from candidates(item)
            return
        yield value

    for field in field_names:
        if field not in record:
            continue
        for raw in candidates(record.get(field)):
            parsed = _parse_date_str(raw)
            if parsed:
                return parsed
            if isinstance(raw, str):
                parsed = extract_close_date(raw)
                if parsed:
                    return parsed
    return None


def _serialize_source_raw(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, default=str)[:5000]


def _extract_close_date_if_hint(*texts: str) -> Optional[date]:
    from app.utils.text_utils import extract_close_date

    combined = " ".join((text or "") for text in texts if text).strip()
    if not combined:
        return None
    if not any(
        hint in combined.lower()
        for hint in ["clôture", "cloture", "date limite", "deadline", "closing date", "candidature", "dépôt", "depot", "avant le", "jusqu'au", "au plus tard le"]
    ):
        return None
    return extract_close_date(combined)


DATA_GOUV_ACTIVE_HINTS = (
    "appel",
    "appels",
    "candidature",
    "candidatures",
    "candidatez",
    "deposer",
    "depot",
    "dépôt",
    "date limite",
    "cloture",
    "clôture",
    "guichet",
    "postuler",
    "jusqu'au",
    "jusqu’au",
    "au plus tard",
)

DATA_GOUV_STRONG_OPPORTUNITY_HINTS = (
    "appel a projets",
    "appel a projet",
    "appel a candidatures",
    "appel a candidature",
    "appel a manifestation",
    "candidatez",
    "date limite",
    "cloture",
    "clôture",
    "au plus tard",
    "jusqu'au",
    "jusqu’au",
)

DATA_GOUV_HISTORICAL_TERMS = (
    "subventions versees",
    "subventions versées",
    "subventions allouees",
    "subventions allouées",
    "subventions accordees",
    "subventions accordées",
    "subventions attribuees",
    "subventions attribuées",
    "dotations",
    "compte administratif",
    "donnees essentielles",
    "données essentielles",
    "budget",
    "depenses",
    "dépenses",
    "paiements",
    "versements",
    "reserve parlementaire",
    "réserve parlementaire",
    "pac ",
    "historique",
    "archive",
    "archives",
    "deliberation",
    "délibération",
    "beneficie",
    "bénéficié",
)


def _normalize_seed_match_text(value: Optional[str]) -> str:
    text = _clean_seed_text(value).lower()
    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ç": "c",
        "œ": "oe",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def _is_historical_datagouv_record(record: dict, description: str, resource_blob: str) -> bool:
    title = (record.get("title") or "").strip()
    title_norm = _normalize_seed_match_text(title)
    full_text = _normalize_seed_match_text(
        " ".join(
            part
            for part in [
                title,
                description or "",
                resource_blob or "",
                " ".join(
                    str(extra.get("value", ""))
                    for extra in (record.get("extras") or [])
                    if isinstance(extra, dict)
                ),
                record.get("page") or "",
                record.get("slug") or "",
            ]
            if part
        )
    )

    if not title_norm:
        return False

    if any(hint in full_text for hint in DATA_GOUV_ACTIVE_HINTS):
        return False

    year_matches = [int(year) for year in re.findall(r"\b(19\d{2}|20\d{2})\b", full_text)]
    old_year = any(year <= 2024 for year in year_matches)
    year_range = bool(re.search(r"\b(19\d{2}|20\d{2})\s*[-/]\s*(19\d{2}|20\d{2})\b", full_text))

    dataset_markers = (
        "/datasets/" in (record.get("page") or "")
        or "dataset" in full_text
        or "jeu de donnees" in full_text
        or "jeu de données" in full_text
    )
    historical_marker = any(term in full_text for term in DATA_GOUV_HISTORICAL_TERMS)

    if dataset_markers and historical_marker and (old_year or year_range):
        return True

    if title_norm.startswith(("subventions ", "dotations ", "budget ", "compte administratif ")):
        return True

    awarded_subsidy_markers = (
        "subvention allouee",
        "subvention allouée",
        "subventions allouees",
        "subventions allouées",
        "subvention accordee",
        "subvention accordée",
        "subventions accordees",
        "subventions accordées",
        "ayant beneficie d'une subvention",
        "ayant bénéficié d'une subvention",
        "detail des subventions accordees",
        "détail des subventions accordées",
        "deliberation subvention",
        "délibération subvention",
    )
    if dataset_markers and any(marker in full_text for marker in awarded_subsidy_markers):
        return True

    return False


def _looks_like_active_datagouv_opportunity(record: dict, description: str, resource_blob: str) -> bool:
    full_text = _normalize_seed_match_text(
        " ".join(
            part
            for part in [
                record.get("title") or "",
                description or "",
                resource_blob or "",
                " ".join(
                    str(extra.get("value", ""))
                    for extra in (record.get("extras") or [])
                    if isinstance(extra, dict)
                ),
            ]
            if part
        )
    )
    return any(hint in full_text for hint in DATA_GOUV_STRONG_OPPORTUNITY_HINTS)


# ─── Collecteur World Bank ────────────────────────────────────────────────────
async def fetch_worldbank(limit: int) -> list:
    """
    Projets actifs de la Banque Mondiale couvrant la France et l'Afrique francophone.
    API: https://search.worldbank.org/api/v2/projects (totalement ouverte, sans auth)
    """
    import httpx

    items = []
    countries = [
        "France", "Senegal", "Cote d'Ivoire", "Morocco", "Tunisia",
        "Cameroon", "Mali", "Burkina Faso", "Niger", "Togo", "Benin",
        "Madagascar", "Guinea", "Ethiopia", "Kenya", "Ghana",
    ]

    country_name_map = {
        "France": "France", "Senegal": "Sénégal", "Cote d'Ivoire": "Côte d'Ivoire",
        "Morocco": "Maroc", "Tunisia": "Tunisie", "Cameroon": "Cameroun",
        "Mali": "Mali", "Burkina Faso": "Burkina Faso", "Niger": "Niger",
        "Togo": "Togo", "Benin": "Bénin", "Madagascar": "Madagascar",
        "Guinea": "Guinée", "Ethiopia": "Éthiopie", "Kenya": "Kenya", "Ghana": "Ghana",
    }

    headers = {
        "User-Agent": "Kafundo/1.0 (research; contact: admin@kafundo.com)",
        "Accept": "application/json",
    }

    # World Bank uses ISO2 country codes for exact matching
    WB_COUNTRY_CODES = {
        "France": "FR", "Senegal": "SN", "Cote d'Ivoire": "CI",
        "Morocco": "MA", "Tunisia": "TN", "Cameroon": "CM",
        "Mali": "ML", "Burkina Faso": "BF", "Niger": "NE",
        "Togo": "TG", "Benin": "BJ", "Madagascar": "MG",
        "Guinea": "GN", "Ethiopia": "ET", "Kenya": "KE", "Ghana": "GH",
    }

    per_batch = min(50, limit // max(len(countries), 1) + 10)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for country in countries:
            if len(items) >= limit:
                break
            try:
                iso2 = WB_COUNTRY_CODES.get(country, "")
                url = (
                    "https://search.worldbank.org/api/v2/projects"
                    f"?format=json&status_exact=Active"
                    f"&fl=id,name,status,totalamt,boardapprovaldate,closingdate,"
                    f"sector1,countryname,borrower,project_abstract,lendprojectcost"
                    f"&countrycode_exact={iso2}"
                    f"&rows={per_batch}&os=0"
                )
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"  WorldBank {country}: HTTP {resp.status_code}")
                    continue

                data = resp.json()
                projects = data.get("projects", {})
                # projects is a dict with project IDs as keys
                for pid, proj in projects.items():
                    if pid in ("total", "totalprojects"):
                        continue
                    name = proj.get("name") or proj.get("project_name")
                    if not name:
                        continue

                    abstract = ""
                    if isinstance(proj.get("project_abstract"), dict):
                        abstract = proj["project_abstract"].get("cdata", "") or ""
                    elif isinstance(proj.get("project_abstract"), str):
                        abstract = proj["project_abstract"]

                    sector_raw = proj.get("sector1", {})
                    if isinstance(sector_raw, dict):
                        sector_name = sector_raw.get("Name", "")
                    else:
                        sector_name = str(sector_raw)

                    amount = _parse_amount_str(proj.get("totalamt") or proj.get("lendprojectcost"))

                    items.append({
                        "title": name.strip(),
                        "organism": "Banque Mondiale / World Bank",
                        "country": country_name_map.get(country, country),
                        "source_url": f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}",
                        "device_type": "pret",
                        "sectors": _detect_sectors_from_text(f"{name} {sector_name} {abstract}"),
                        "beneficiaries": ["collectivite", "porteur_projet"],
                        "short_description": (abstract[:600] if abstract else f"Projet de la Banque Mondiale : {name}"),
                        "amount_max": amount,
                        "currency": "USD",
                        "status": "open",
                        "close_date": _parse_date_str(proj.get("closingdate")),
                        "open_date": _parse_date_str(proj.get("boardapprovaldate")),
                        "language": "fr",
                        "validation_status": "auto_published",
                    })
                    if len(items) >= limit:
                        break

                logger.info(f"  WorldBank {country}: {len([x for x in items if x['country'] == country_name_map.get(country, country)])} projets")

            except Exception as e:
                logger.warning(f"  WorldBank {country}: {e}")

    logger.info(f"  WorldBank TOTAL: {len(items)} projets récupérés")
    return items


# ─── Collecteur AFD Open Data ─────────────────────────────────────────────────
async def fetch_afd(limit: int) -> list:
    """
    Projets AFD via OpenDataSoft (open, sans auth).
    Dataset: les-projets-de-l-afd  (champs réels vérifiés)
    """
    import httpx
    from app.collector.normalizer import COUNTRY_MAP

    items = []
    headers = {"User-Agent": "Kafundo/1.0", "Accept": "application/json"}

    DATASETS = [
        "les-projets-de-l-afd",
        "projets-climat-afd",
        "donnees-aide-au-developpement-afd",
    ]

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for ds_id in DATASETS:
            if len(items) >= limit:
                break
            offset = 0
            page_size = 50
            while len(items) < limit:
                try:
                    url = (
                        f"https://opendata.afd.fr/api/explore/v2.1/catalog/datasets/"
                        f"{ds_id}/records?limit={page_size}&offset={offset}"
                    )
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        logger.warning(f"  AFD {ds_id}: HTTP {resp.status_code}")
                        break

                    data = resp.json()
                    records = data.get("results", [])
                    if not records:
                        break

                    for rec in records:
                        # Real field names from API inspection
                        title = (
                            rec.get("title_narrative") or rec.get("libelle")
                            or rec.get("nom_du_projet") or rec.get("name") or ""
                        )
                        if not title or len(str(title).strip()) < 5:
                            continue

                        desc = (
                            rec.get("description_narrative") or rec.get("description")
                            or rec.get("description_text") or ""
                        )
                        country_raw = (
                            rec.get("cntry_name") or rec.get("country_narrative_text")
                            or rec.get("pays") or rec.get("recipient_country_narrative") or "Afrique"
                        )
                        if isinstance(country_raw, list):
                            country_raw = country_raw[0] if country_raw else "Afrique"
                        country = COUNTRY_MAP.get(str(country_raw).lower().strip(), str(country_raw))

                        amount_raw = rec.get("sum_transaction_value_text") or rec.get("montant") or ""
                        amount = _parse_amount_str(str(amount_raw).replace(" ", "").replace(",", "."))

                        close_raw = rec.get("date_dachevement") or rec.get("date_fin") or rec.get("date")
                        close_date = _parse_date_str(close_raw)

                        zone = rec.get("zone_geographique") or rec.get("zone") or ""
                        sector = rec.get("sector_narrative") or rec.get("cicd") or rec.get("libelle") or ""

                        items.append({
                            "title": str(title).strip()[:400],
                            "organism": "Agence Française de Développement (AFD)",
                            "country": country,
                            "source_url": f"https://opendata.afd.fr/explore/dataset/{ds_id}/",
                            "device_type": "pret",
                            "sectors": _detect_sectors_from_text(f"{title} {desc} {sector}"),
                            "beneficiaries": ["collectivite", "pme", "porteur_projet"],
                            "short_description": str(desc)[:600] if desc else f"Projet AFD : {title}",
                            "amount_max": amount,
                            "currency": "EUR",
                            "status": "open",
                            "close_date": close_date,
                            "zone": str(zone)[:200] if zone else None,
                            "language": "fr",
                            "validation_status": "auto_published",
                        })
                        if len(items) >= limit:
                            break

                    if len(records) < page_size:
                        break
                    offset += page_size

                except Exception as e:
                    logger.warning(f"  AFD {ds_id}: {e}")
                    break

            logger.info(f"  AFD dataset '{ds_id}': {len(items)} items cumulés")

    logger.info(f"  AFD TOTAL: {len(items)} projets récupérés")
    return items


# ─── Collecteur ADEME Open Data ───────────────────────────────────────────────
async def fetch_ademe(limit: int) -> list:
    """
    Aides ADEME via data.ademe.fr data-fair API (open, sans auth).
    Dataset: les-aides-financieres-de-l'ademe  (champs réels vérifiés)
    """
    import httpx

    items = []
    headers = {"User-Agent": "Kafundo/1.0", "Accept": "application/json"}

    # Dataset IDs réels (vérifiés)
    DATASETS = [
        {
            "id": "les-aides-financieres-de-l%27ademe",
            "title_field": "objet",
            "organism_field": "Nom_de_l_attribuant",
            "amount_field": "montant",
            "date_fields": [
                "date_fin",
                "dateFin",
                "date_cloture",
                "dateCloture",
                "date_limite_candidature",
                "dateLimiteCandidature",
            ],
            "type": "subvention",
        },
        {
            "id": "vouhs4v32xnqjzq4wck721vo",  # Programmes d'Etat - Projets ADEME
            "title_field": "intitule_du_projet",
            "organism_field": None,
            "amount_field": "montant_subvention",
            "date_fields": [
                "date_fin",
                "dateFin",
                "date_cloture",
                "dateCloture",
                "date_limite_candidature",
                "dateLimiteCandidature",
                "deadline",
                "date_de_fin_du_projet",
                "dateDeFinDuProjet",
            ],
            "type": "subvention",
        },
    ]

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for ds in DATASETS:
            if len(items) >= limit:
                break
            try:
                skip = 0
                size = 100
                while len(items) < limit:
                    url = (
                        f"https://data.ademe.fr/data-fair/api/v1/datasets/"
                        f"{ds['id']}/lines?size={size}&skip={skip}"
                    )
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 404:
                        logger.warning(f"  ADEME '{ds['id']}' introuvable — ignoré")
                        break
                    if resp.status_code != 200:
                        logger.warning(f"  ADEME {ds['id']}: HTTP {resp.status_code}")
                        break

                    data = resp.json()
                    records = data.get("results", [])
                    if not records:
                        break

                    for rec in records:
                        title_raw = (
                            rec.get(ds["title_field"]) or rec.get("intitule")
                            or rec.get("titre") or rec.get("nom") or rec.get("libelle") or ""
                        )
                        if not title_raw or len(str(title_raw).strip()) < 5:
                            continue

                        # Build readable title from purpose
                        title = f"Aide ADEME – {str(title_raw).strip()[:200]}"
                        beneficiary = rec.get("nomBeneficiaire") or ""
                        if beneficiary and len(title) < 250:
                            title = f"{str(title_raw).strip()[:150]} ({beneficiary[:80]})"

                        amount = _parse_amount_str(rec.get(ds["amount_field"]))
                        close_date = _extract_record_date(
                            rec,
                            *ds["date_fields"],
                        )
                        close_date = close_date or _extract_close_date_if_hint(
                            str(rec.get("description") or ""),
                            str(rec.get("objet") or ""),
                            str(rec.get("intitule") or ""),
                            str(rec.get("intitule_du_projet") or ""),
                        )

                        sector_hint = rec.get("activite") or rec.get("secteur") or title_raw
                        organism = (
                            rec.get(ds["organism_field"]) if ds["organism_field"] else None
                        ) or "ADEME"

                        status = "recurring"
                        if close_date and close_date < date.today():
                            status = "expired"

                        items.append({
                            "title": title[:400],
                            "organism": str(organism)[:255],
                            "country": "France",
                            "source_url": f"https://data.ademe.fr/datasets/{ds['id'].replace('%27', chr(39))}",
                            "device_type": ds["type"],
                            "sectors": _detect_sectors_from_text(str(sector_hint)) or ["environnement"],
                            "beneficiaries": ["pme", "startup", "porteur_projet"],
                            "short_description": f"Aide financière ADEME accordée à {beneficiary}" if beneficiary else f"Aide ADEME : {str(title_raw)[:400]}",
                            "amount_max": amount,
                            "currency": "EUR",
                            "status": status,
                            "close_date": close_date,
                            "source_raw": _serialize_source_raw(rec),
                            "language": "fr",
                            "validation_status": "auto_published",
                        })
                        if len(items) >= limit:
                            break

                    logger.info(f"  ADEME '{ds['id']}': {len(items)} items cumulés")
                    if len(records) < size:
                        break
                    skip += size

            except Exception as e:
                logger.warning(f"  ADEME {ds['id']}: {e}")

    logger.info(f"  ADEME TOTAL: {len(items)} aides récupérées")
    return items


# ─── Collecteur EU Grants ─────────────────────────────────────────────────────
async def fetch_datagouv(limit: int) -> list:
    """
    Jeux de données et publications data.gouv.fr contenant des aides ou subventions.
    """
    import httpx

    items = []
    headers = {"User-Agent": "Kafundo/1.0", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        page = 1
        page_size = min(100, max(20, limit))

        while len(items) < limit:
            try:
                url = (
                    "https://www.data.gouv.fr/api/1/datasets/"
                    f"?tag=subvention&page_size={page_size}&sort=-created&page={page}"
                )
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"  data.gouv.fr: HTTP {resp.status_code}")
                    break

                data = resp.json()
                records = data.get("data", [])
                if not records:
                    break

                for rec in records:
                    title = (rec.get("title") or "").strip()
                    if len(title) < 5:
                        continue

                    description = rec.get("description") or ""
                    resources = rec.get("resources") or []
                    organization = rec.get("organization") or {}
                    org_name = (
                        organization.get("acronym")
                        or organization.get("name")
                        or organization.get("title")
                        or "Gouvernement francais"
                    )

                    resource_blob = " ".join(
                        f"{r.get('title', '')} {r.get('description', '')} {r.get('type', '')} {r.get('url', '')}"
                        for r in resources[:10]
                    )
                    close_date = _extract_close_date_if_hint(
                        description,
                        resource_blob,
                        " ".join(str(extra.get("value", "")) for extra in rec.get("extras") or [] if isinstance(extra, dict)),
                    )

                    if _is_historical_datagouv_record(rec, description, resource_blob):
                        continue
                    if not close_date and not _looks_like_active_datagouv_opportunity(rec, description, resource_blob):
                        continue

                    items.append({
                        "title": title[:400],
                        "organism": str(org_name)[:255],
                        "country": "France",
                        "source_url": rec.get("page") or rec.get("uri") or "https://www.data.gouv.fr/",
                        "device_type": "subvention",
                        "sectors": _detect_sectors_from_text(f"{title} {description} {resource_blob}"),
                        "beneficiaries": ["pme", "startup", "porteur_projet"],
                        "short_description": _clean_seed_text(description)[:600] if description else f"Publication data.gouv.fr : {title}",
                        "status": "open",
                        "close_date": close_date,
                        "source_raw": _serialize_source_raw(rec),
                        "language": "fr",
                        "validation_status": "auto_published",
                    })
                    if len(items) >= limit:
                        break

                if len(records) < page_size:
                    break
                page += 1

            except Exception as e:
                logger.warning(f"  data.gouv.fr: {e}")
                break

    logger.info(f"  data.gouv.fr TOTAL: {len(items)} elements recuperes")
    return items


async def fetch_eu_grants(limit: int) -> list:
    """
    Appels à propositions UE via l'API EC SEDIA (accès public).
    """
    import httpx

    items = []
    headers = {
        "User-Agent": "Kafundo/1.0",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # EC SEDIA API requires POST with apiKey as query param
            url = (
                "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
                "?apiKey=SEDIA&text=*&pageSize=50&pageNumber=1"
                "&languages=fr%2Cen"
                "&sortField=startDate&sortOrder=DESC"
            )
            resp = await client.post(url, headers=headers, json={})

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                logger.info(f"  EU Grants API: {len(results)} résultats")

                for item in results[:limit]:
                    metadata = item.get("metadata", {})
                    title = (
                        item.get("title") or
                        metadata.get("title", [""])[0] if isinstance(metadata.get("title"), list) else metadata.get("title", "")
                    )
                    if not title:
                        continue

                    desc = item.get("description") or item.get("summary") or ""
                    if isinstance(desc, list):
                        desc = desc[0] if desc else ""

                    deadline_raw = metadata.get("deadlineDate") or metadata.get("deadline")
                    if isinstance(deadline_raw, list):
                        deadline_raw = deadline_raw[0] if deadline_raw else None
                    close_date = _parse_date_str(deadline_raw)

                    items.append({
                        "title": str(title).strip()[:400],
                        "organism": "Commission Européenne / EU",
                        "country": "France",
                        "source_url": item.get("url") or "https://ec.europa.eu/info/funding-tenders/",
                        "device_type": "aap",
                        "sectors": _detect_sectors_from_text(str(title) + " " + str(desc)),
                        "beneficiaries": ["startup", "pme", "chercheur", "porteur_projet"],
                        "short_description": str(desc)[:600] if desc else f"Appel EU : {title}",
                        "currency": "EUR",
                        "status": "open",
                        "close_date": close_date,
                        "language": "fr",
                        "validation_status": "auto_published",
                    })
            else:
                logger.warning(f"  EU Grants API: HTTP {resp.status_code}")

    except Exception as e:
        logger.warning(f"  EU Grants: {e}")

    logger.info(f"  EU TOTAL: {len(items)} appels récupérés")
    return items


# ─── Collecteur IFC (Banque Mondiale — secteur privé) ─────────────────────────
async def fetch_ifc(limit: int) -> list:
    """
    Projets IFC (International Finance Corporation) via World Bank API.
    Financement privé institutionnel pour les entreprises africaines et emergentes.
    """
    import httpx
    from app.collector.normalizer import COUNTRY_MAP

    items = []
    headers = {"User-Agent": "Kafundo/1.0", "Accept": "application/json"}
    WB_COUNTRY_CODES = {
        "Senegal": "SN", "Cote d'Ivoire": "CI", "Morocco": "MA", "Tunisia": "TN",
        "Cameroon": "CM", "Mali": "ML", "Burkina Faso": "BF", "Niger": "NE",
        "Togo": "TG", "Benin": "BJ", "Madagascar": "MG", "Guinea": "GN",
        "Ethiopia": "ET", "Kenya": "KE", "Ghana": "GH", "Nigeria": "NG",
        "Rwanda": "RW", "Tanzania": "TZ", "Mozambique": "MZ", "France": "FR",
    }
    country_name_map = {
        "Senegal": "Sénégal", "Cote d'Ivoire": "Côte d'Ivoire", "Morocco": "Maroc",
        "Tunisia": "Tunisie", "Cameroon": "Cameroun", "Mali": "Mali",
        "Burkina Faso": "Burkina Faso", "Niger": "Niger", "Togo": "Togo",
        "Benin": "Bénin", "Madagascar": "Madagascar", "Guinea": "Guinée",
        "Ethiopia": "Éthiopie", "Kenya": "Kenya", "Ghana": "Ghana",
        "Nigeria": "Nigeria", "Rwanda": "Rwanda", "Tanzania": "Tanzanie",
        "Mozambique": "Mozambique", "France": "France",
    }

    per_batch = min(50, limit // max(len(WB_COUNTRY_CODES), 1) + 5)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for country, iso2 in WB_COUNTRY_CODES.items():
            if len(items) >= limit:
                break
            try:
                url = (
                    "https://search.worldbank.org/api/v2/projects"
                    f"?format=json&source=ifc&status_exact=Active"
                    f"&fl=id,name,totalamt,boardapprovaldate,closingdate,"
                    f"sector1,countryname,borrower,project_abstract"
                    f"&countrycode_exact={iso2}&rows={per_batch}&os=0"
                )
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                projects = data.get("projects", {})
                for pid, proj in projects.items():
                    if pid in ("total", "totalprojects"):
                        continue
                    name = proj.get("name") or proj.get("project_name")
                    if not name:
                        continue
                    abstract = ""
                    if isinstance(proj.get("project_abstract"), dict):
                        abstract = proj["project_abstract"].get("cdata", "")
                    elif isinstance(proj.get("project_abstract"), str):
                        abstract = proj["project_abstract"]
                    sector_raw = proj.get("sector1", {})
                    sector_name = sector_raw.get("Name", "") if isinstance(sector_raw, dict) else str(sector_raw)
                    amount = _parse_amount_str(proj.get("totalamt"))

                    items.append({
                        "title": f"IFC – {name.strip()}"[:400],
                        "organism": "IFC — International Finance Corporation (Groupe Banque Mondiale)",
                        "country": country_name_map.get(country, country),
                        "source_url": f"https://disclosures.ifc.org/project-detail/SII/{pid}",
                        "device_type": "investissement",
                        "sectors": _detect_sectors_from_text(f"{name} {sector_name} {abstract}"),
                        "beneficiaries": ["pme", "eti", "startup"],
                        "short_description": (
                            (abstract[:600] if abstract else None)
                            or f"Investissement IFC dans le secteur privé : {name}"
                        ),
                        "amount_max": amount,
                        "currency": "USD",
                        "status": "open",
                        "close_date": _parse_date_str(proj.get("closingdate")),
                        "open_date": _parse_date_str(proj.get("boardapprovaldate")),
                        "language": "fr",
                        "validation_status": "auto_published",
                    })
                    if len(items) >= limit:
                        break
                if len(items) > 0:
                    logger.info(f"  IFC {country}: {len(items)} items cumulés")
            except Exception as e:
                logger.warning(f"  IFC {country}: {e}")

    logger.info(f"  IFC TOTAL: {len(items)} projets récupérés")
    return items


async def fetch_proparco(limit: int) -> list:
    """
    Projets Proparco (bras privé de l'AFD) via AFD Open Data.
    Financement des entreprises privées en Afrique et Asie.
    """
    import httpx
    from app.collector.normalizer import COUNTRY_MAP

    items = []
    headers = {"User-Agent": "Kafundo/1.0", "Accept": "application/json"}

    DATASETS = [
        "liste-des-prestations-et-des-subventions-contractes-par-proparco-dans-le-cadre-d",
        "donnees-de-laide-au-developpement-de-proparco",
    ]

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for ds_id in DATASETS:
            if len(items) >= limit:
                break
            offset = 0
            while len(items) < limit:
                try:
                    url = (
                        f"https://opendata.afd.fr/api/explore/v2.1/catalog/datasets/"
                        f"{ds_id}/records?limit=50&offset={offset}"
                    )
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    records = data.get("results", [])
                    if not records:
                        break

                    for rec in records:
                        title = (
                            rec.get("title_narrative") or rec.get("libelle")
                            or rec.get("name") or rec.get("intitule") or ""
                        )
                        if not title or len(str(title).strip()) < 5:
                            continue
                        desc = rec.get("description_narrative") or rec.get("description") or ""
                        country_raw = (
                            rec.get("cntry_name") or rec.get("recipient_country_narrative")
                            or rec.get("pays") or "Afrique"
                        )
                        if isinstance(country_raw, list):
                            country_raw = country_raw[0] if country_raw else "Afrique"
                        country = COUNTRY_MAP.get(str(country_raw).lower().strip(), str(country_raw))
                        amount = _parse_amount_str(
                            str(rec.get("sum_transaction_value_text") or rec.get("montant") or "")
                            .replace(" ", "").replace(",", ".")
                        )

                        items.append({
                            "title": f"Proparco – {str(title).strip()}"[:400],
                            "organism": "Proparco — Filiale de l'AFD (secteur privé)",
                            "country": country,
                            "source_url": f"https://opendata.afd.fr/explore/dataset/{ds_id}/",
                            "device_type": "investissement",
                            "sectors": _detect_sectors_from_text(f"{title} {desc}"),
                            "beneficiaries": ["pme", "eti", "startup"],
                            "short_description": str(desc)[:600] if desc else f"Financement Proparco : {title}",
                            "amount_max": amount,
                            "currency": "EUR",
                            "status": "open",
                            "language": "fr",
                            "validation_status": "auto_published",
                        })
                        if len(items) >= limit:
                            break

                    if len(records) < 50:
                        break
                    offset += 50
                except Exception as e:
                    logger.warning(f"  Proparco {ds_id}: {e}")
                    break
            logger.info(f"  Proparco '{ds_id}': {len(items)} items cumulés")

    logger.info(f"  Proparco TOTAL: {len(items)} projets")
    return items


# ─── Données curatives : VC, Business Angels, Institutionnels ─────────────────
def build_private_finance_catalog() -> list:
    """
    Base curée des principaux fonds VC, Business Angels et investisseurs
    institutionnels actifs en France et en Afrique.
    Données vérifiées et mises à jour (2024-2026).
    """
    return [

        # ══════════════════════════════════════════════════════════════════════
        # FRANCE — FONDS VENTURE CAPITAL (VC)
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "Partech Partners – Fonds Tech & Digital (Seed à Growth)",
            "organism": "Partech Partners",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "sante"],
            "beneficiaries": ["startup", "pme"],
            "amount_min": 500_000, "amount_max": 50_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://partechpartners.com",
            "short_description": (
                "Partech est l'un des principaux fonds VC européens avec 2,3 Md€ sous gestion. "
                "Il investit de l'amorçage au growth dans les secteurs tech, digital, SaaS, fintech, healthtech. "
                "Tickets de 500 K€ (seed) à 50 M€ (growth). Présence en Europe, Afrique et Amérique."
            ),
            "eligibility_criteria": "Startup tech à fort potentiel de croissance, marché > 1 Md€, équipe fondatrice solide.",
            "funding_details": "Prise de participation minoritaire. Lead investor ou co-investisseur.",
            "geographic_scope": "international",
        },
        {
            "title": "Alven Capital – Fonds Amorçage & Série A/B Tech",
            "organism": "Alven Capital",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "finance"],
            "beneficiaries": ["startup"],
            "amount_min": 500_000, "amount_max": 30_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.alven.co",
            "short_description": (
                "Alven est un fonds de capital-risque créé en 2000, spécialisé dans les startups "
                "tech françaises et européennes. Portfolio : Doctolib, Back Market, Alan, Alma. "
                "Investit en seed, série A et B. 1,5 Md€ sous gestion."
            ),
            "eligibility_criteria": "Startup tech, SaaS, marketplace avec traction démontrable. Fondateurs ambitieux.",
            "geographic_scope": "national",
        },
        {
            "title": "Kima Ventures – Fonds Seed Ultra-Actif",
            "organism": "Kima Ventures",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "finance", "sante", "social"],
            "beneficiaries": ["startup"],
            "amount_min": 150_000, "amount_max": 500_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.kimaventures.com",
            "short_description": (
                "Kima Ventures (Xavier Niel) est l'un des fonds seed les plus actifs au monde : "
                "2 investissements par semaine. Tickets de 150 à 500 K€ pour 10 à 15% du capital. "
                "Process de décision en 72h. Ouvert aux startups mondiales."
            ),
            "eligibility_criteria": "Pre-seed ou seed. Tout secteur. Équipe fondatrice ambitieuse, marché global.",
            "geographic_scope": "international",
        },
        {
            "title": "ISAI – Fonds VC par des Entrepreneurs pour des Entrepreneurs",
            "organism": "ISAI",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "finance"],
            "beneficiaries": ["startup"],
            "amount_min": 500_000, "amount_max": 10_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.isai.fr",
            "short_description": (
                "ISAI est un fonds VC fondé par des entrepreneurs du numérique (fondateurs de PriceMinister, "
                "Meetic, Dailymotion...). 400 M€ sous gestion, investit en seed et série A dans le B2B SaaS, "
                "marketplaces et infrastructures tech."
            ),
            "eligibility_criteria": "Startup B2B ou B2C tech, revenue récurrent ou forte croissance utilisateurs.",
            "geographic_scope": "national",
        },
        {
            "title": "Newfund – Capital-Risque Seed & Série A",
            "organism": "Newfund",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "sante", "environnement"],
            "beneficiaries": ["startup"],
            "amount_min": 300_000, "amount_max": 5_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.newfund.fr",
            "short_description": (
                "Newfund investit en seed et série A dans des startups tech franco-américaines. "
                "Présence à Paris et New York. Focus deeptech, SaaS B2B, fintech. "
                "Accompagnement actif pour l'expansion internationale, notamment vers les USA."
            ),
            "eligibility_criteria": "Startup deeptech ou SaaS avec ambition internationale, fondateurs expérimentés.",
            "geographic_scope": "international",
        },
        {
            "title": "Eurazeo (ex-Idinvest) – Growth Capital & Private Equity",
            "organism": "Eurazeo",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "finance", "industrie"],
            "beneficiaries": ["pme", "eti", "startup"],
            "amount_min": 5_000_000, "amount_max": 200_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.eurazeo.com",
            "short_description": (
                "Eurazeo est un investisseur global avec 35 Md€ sous gestion. "
                "Intervient en venture (Idinvest), growth capital, buyout et dette privée. "
                "Portfolio : Doctolib, Content Square, Vestiaire Collective. "
                "Tickets de 5 M€ (venture) à 200 M€ (PE)."
            ),
            "eligibility_criteria": "PME à ETI à fort potentiel, rentables ou en hypercroissance. Secteur tech et consommation.",
            "geographic_scope": "international",
        },
        {
            "title": "XAnge – Fonds VC Seed & Série A (Société Générale)",
            "organism": "XAnge",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["finance", "numerique", "sante", "industrie"],
            "beneficiaries": ["startup"],
            "amount_min": 500_000, "amount_max": 15_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://xange.vc",
            "short_description": (
                "XAnge (filiale de La Banque Postale) investit en seed et série A dans des startups "
                "tech ayant un impact sur la transition numérique et écologique. "
                "350 M€ sous gestion. Portfolio : Shine, Lunchr, Treezor."
            ),
            "eligibility_criteria": "Startup tech à impact positif, modèle scalable, équipe pluridisciplinaire.",
            "geographic_scope": "national",
        },
        {
            "title": "Elaia Partners – Deeptech & B2B SaaS",
            "organism": "Elaia Partners",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "sante"],
            "beneficiaries": ["startup"],
            "amount_min": 500_000, "amount_max": 20_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.elaia.com",
            "short_description": (
                "Elaia Partners est un fonds VC spécialisé dans la deep tech et le B2B SaaS. "
                "280 M€ sous gestion. Investit de la pré-seed à la série B. "
                "Portfolio : Shift Technology, Teads, Kyriba."
            ),
            "eligibility_criteria": "Startup deeptech ou B2B SaaS avec barrières technologiques fortes.",
            "geographic_scope": "national",
        },
        {
            "title": "Axeleo Capital – B2B SaaS & Industrie 4.0",
            "organism": "Axeleo Capital",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie"],
            "beneficiaries": ["startup"],
            "amount_min": 200_000, "amount_max": 8_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.axeleo.com",
            "short_description": (
                "Axeleo Capital investit en seed et série A dans les startups B2B tech (SaaS, industrie 4.0, "
                "logistique, supply chain). Programme d'accélération + investissement. "
                "Basé à Lyon et Paris."
            ),
            "eligibility_criteria": "Startup B2B tech avec premiers clients, marché industriel ou supply chain.",
            "geographic_scope": "national",
        },
        {
            "title": "Founders Future – Fonds d'Amorçage Entrepreneurs",
            "organism": "Founders Future",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "social", "environnement", "sante"],
            "beneficiaries": ["startup"],
            "amount_min": 150_000, "amount_max": 3_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.foundersfuture.com",
            "short_description": (
                "Founders Future investit en pre-seed et seed dans des startups à fort impact social ou environnemental. "
                "Réseau de 250 entrepreneurs. Tickets 150 K€ à 3 M€. "
                "Accompagnement intensif sur 6 mois après investissement."
            ),
            "eligibility_criteria": "Startup pre-seed ou seed, modèle scalable, impact positif démontrable.",
            "geographic_scope": "national",
        },

        # ══════════════════════════════════════════════════════════════════════
        # FRANCE — BUSINESS ANGELS & RÉSEAUX
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "France Angels – Réseau National de Business Angels (80 clubs)",
            "organism": "France Angels",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "industrie", "social", "environnement"],
            "beneficiaries": ["startup", "pme", "porteur_projet"],
            "amount_min": 50_000, "amount_max": 1_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.franceangels.org",
            "short_description": (
                "France Angels fédère 80 clubs et réseaux de business angels répartis sur tout le territoire. "
                "Chaque club réunit des entrepreneurs et dirigeants qui co-investissent entre 50 K€ et 1 M€ "
                "en equity. Accès possible aux dispositifs IR-PME et ISF-PME. "
                "7 000 investisseurs actifs, 350 M€ investis par an."
            ),
            "eligibility_criteria": (
                "Startup ou PME innovante en phase d'amorçage. "
                "Présenter un business plan solide et une équipe fondatrice complémentaire."
            ),
            "geographic_scope": "national",
        },
        {
            "title": "Initiative France – Prêts d'Honneur Sans Intérêt pour Créateurs",
            "organism": "Initiative France",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "commerce", "social", "agriculture"],
            "beneficiaries": ["porteur_projet", "startup", "pme"],
            "amount_min": 5_000, "amount_max": 90_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.initiative-france.fr",
            "short_description": (
                "Initiative France est le 1er réseau d'appui à la création et reprise d'entreprise en France. "
                "80 000 entreprises accompagnées par an. Prêts d'honneur de 5 000 à 90 000€ "
                "sans intérêt ni garantie personnelle. Effet levier sur les prêts bancaires (x 7). "
                "Accompagnement par des bénévoles chefs d'entreprise."
            ),
            "eligibility_criteria": (
                "Porteur de projet ou créateur d'entreprise. Projet viable économiquement. "
                "Résidence en France. Présentation devant un comité d'agrément local."
            ),
            "geographic_scope": "national",
        },
        {
            "title": "Réseau Entreprendre – Prêt d'Honneur + Accompagnement Dirigeants",
            "organism": "Réseau Entreprendre",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "commerce", "sante", "social"],
            "beneficiaries": ["porteur_projet", "startup", "pme"],
            "amount_min": 15_000, "amount_max": 90_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.reseau-entreprendre.org",
            "short_description": (
                "Réseau Entreprendre accompagne les créateurs et repreneurs ambitieux via des prêts d'honneur "
                "de 15 à 90 K€ (sans intérêts, sans garantie) et un accompagnement personnalisé "
                "par un chef d'entreprise pendant 3 ans. "
                "3 000 lauréats/an, 600 000 emplois créés ou pérennisés depuis 1986."
            ),
            "eligibility_criteria": "Projet créateur d'au moins 10 emplois à 3 ans. Ambition de croissance claire.",
            "geographic_scope": "national",
        },
        {
            "title": "Femmes Business Angels – Investissement & Mentoring au Féminin",
            "organism": "Femmes Business Angels",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "social", "industrie"],
            "beneficiaries": ["startup", "porteur_projet"],
            "amount_min": 30_000, "amount_max": 500_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.femmesbusinessangels.org",
            "short_description": (
                "Femmes Business Angels est un réseau de 200 investisseuses qui soutiennent "
                "les entrepreneurs (toutes cibles, pas uniquement les femmes). "
                "Investissements en equity de 30 K€ à 500 K€. "
                "Accompagnement et mise en réseau avec des dirigeantes expérimentées."
            ),
            "eligibility_criteria": "Startup innovante en phase d'amorçage ou seed. Pitch et dossier complet requis.",
            "geographic_scope": "national",
        },
        {
            "title": "50 Partners – Fonds Seed + Studio de Startups",
            "organism": "50 Partners",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "social", "environnement"],
            "beneficiaries": ["startup"],
            "amount_min": 100_000, "amount_max": 2_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.50partners.fr",
            "short_description": (
                "50 Partners est une plateforme d'investissement seed qui combine un fonds VC, "
                "un studio de startups et un réseau de 200 entrepreneurs. "
                "Investit 100 K€ à 2 M€ en seed + accompagnement intensif 6 mois. "
                "Focus impact social et environnemental."
            ),
            "eligibility_criteria": "Startup pre-seed ou seed, marché validé, équipe opérationnelle, impact mesurable.",
            "geographic_scope": "national",
        },

        # ══════════════════════════════════════════════════════════════════════
        # FRANCE — INVESTISSEURS INSTITUTIONNELS
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "Bpifrance Investissement – Capital-Risque, Amorçage & Growth",
            "organism": "Bpifrance",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "sante", "environnement", "energie"],
            "beneficiaries": ["startup", "pme", "eti"],
            "amount_min": 200_000, "amount_max": 100_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.bpifrance.fr/investissement",
            "short_description": (
                "Bpifrance est le principal investisseur public français : 7 Md€/an en capital. "
                "Intervient en direct (fonds propres) et via des fonds partenaires à toutes les étapes : "
                "pré-amorçage (50 K€), amorçage (200 K€–3 M€), capital-risque (1–20 M€), "
                "capital-développement (5–100 M€). Possibilité de co-investissement avec des VCs privés."
            ),
            "eligibility_criteria": (
                "Startup ou PME française innovante. Projet à fort potentiel. "
                "Business plan, états financiers et pitch deck requis."
            ),
            "geographic_scope": "national",
        },
        {
            "title": "EIF – Fonds Européen d'Investissement (Garanties & Capital)",
            "organism": "Fonds Européen d'Investissement (EIF)",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "sante", "environnement"],
            "beneficiaries": ["startup", "pme"],
            "amount_min": 500_000, "amount_max": 50_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.eif.org",
            "short_description": (
                "L'EIF (filiale de la BEI) est le principal fonds de fonds et garant public européen "
                "pour les PME et startups. Il investit dans des fonds VC (pas directement dans les entreprises) "
                "et fournit des garanties à des intermédiaires financiers (banques, fonds de prêt). "
                "Via le programme InvestEU et Horizon Europe, il mobilise 10 Md€/an."
            ),
            "eligibility_criteria": (
                "PME ou startup européenne. Accès via un intermédiaire accrédité EIF "
                "(banque, fonds de capital-risque partenaire). Pas d'accès direct."
            ),
            "geographic_scope": "international",
        },
        {
            "title": "CDC Investissement Croissance – Fonds de Fonds (Régions)",
            "organism": "Caisse des Dépôts — Direction des Investissements",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "environnement", "sante", "tourisme"],
            "beneficiaries": ["pme", "eti"],
            "amount_min": 1_000_000, "amount_max": 30_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.caissedesdepots.fr/investissement",
            "short_description": (
                "La Caisse des Dépôts investit dans les PME et ETI via des fonds régionaux (FEDER, "
                "fonds Banque des Territoires) et des co-investissements directs. "
                "Focus transition écologique, industrie, tourisme et économie sociale. "
                "Mobilise 3 Md€/an en fonds propres pour les entreprises."
            ),
            "eligibility_criteria": "PME ou ETI en développement. Projet structurant pour un territoire ou secteur stratégique.",
            "geographic_scope": "national",
        },

        # ══════════════════════════════════════════════════════════════════════
        # AFRIQUE — FONDS VENTURE CAPITAL
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "Partech Africa – Fonds VC Tech Afrique (Seed à Série B)",
            "organism": "Partech Africa",
            "country": "Sénégal",
            "device_type": "investissement",
            "sectors": ["numerique", "finance", "sante", "transport", "agriculture"],
            "beneficiaries": ["startup", "pme"],
            "amount_min": 500_000, "amount_max": 20_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://partechpartners.com/africa",
            "short_description": (
                "Partech Africa est l'un des principaux fonds VC tech pan-africains. "
                "280 M$ sous gestion. Investit de la seed à la série B dans les startups tech en Afrique subsaharienne. "
                "Portfolio : Wave, Yoco, Cheki, Aerobotics. "
                "Basé à Dakar, présence dans toute l'Afrique francophone et anglophone."
            ),
            "eligibility_criteria": (
                "Startup tech africaine, marché démontrable, équipe locale expérimentée. "
                "Priorité aux solutions locales à fort impact."
            ),
            "geographic_scope": "continental",
        },
        {
            "title": "I&P (Investisseurs & Partenaires) – Impact Investing PME Afrique",
            "organism": "Investisseurs & Partenaires (I&P)",
            "country": "Côte d'Ivoire",
            "device_type": "investissement",
            "sectors": ["agriculture", "sante", "education", "numerique", "industrie"],
            "beneficiaries": ["pme", "startup"],
            "amount_min": 200_000, "amount_max": 3_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.ietp.com",
            "short_description": (
                "I&P est un fonds d'impact investing spécialisé dans les PME africaines. "
                "Cible les entreprises en croissance en Afrique subsaharienne et francophone. "
                "200 K€ à 3 M€ en equity + quasi-equity. Accompagnement opérationnel intensif. "
                "Actif dans 20+ pays africains, 120+ entreprises financées."
            ),
            "eligibility_criteria": (
                "PME africaine formelle, CA > 200 K€, équipe managériale solide. "
                "Impact social ou environnemental mesurable requis."
            ),
            "geographic_scope": "continental",
        },
        {
            "title": "AfricInvest – Fonds Private Equity Pan-Africain",
            "organism": "AfricInvest Group",
            "country": "Tunisie",
            "device_type": "investissement",
            "sectors": ["finance", "industrie", "sante", "agriculture", "numerique"],
            "beneficiaries": ["pme", "eti"],
            "amount_min": 2_000_000, "amount_max": 30_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://www.africinvest.com",
            "short_description": (
                "AfricInvest est un leader du private equity africain avec 2 Md$ sous gestion. "
                "Actif en Afrique du Nord (Tunisie, Maroc, Égypte) et subsaharienne. "
                "Tickets de 2 à 30 M$ en capital-développement et buyout. "
                "200+ investissements réalisés depuis 1994."
            ),
            "eligibility_criteria": (
                "PME ou ETI africaine rentable, CA > 2 M$. "
                "Secteur porteur avec barrières à l'entrée. Équipe dirigeante expérimentée."
            ),
            "geographic_scope": "continental",
        },
        {
            "title": "Cauris Management – Fonds de Capital-Investissement UEMOA",
            "organism": "Cauris Management",
            "country": "Côte d'Ivoire",
            "device_type": "investissement",
            "sectors": ["agriculture", "industrie", "finance", "sante"],
            "beneficiaries": ["pme", "eti"],
            "amount_min": 500_000, "amount_max": 8_000_000,
            "currency": "XOF",
            "status": "open",
            "source_url": "https://www.cauris.biz",
            "short_description": (
                "Cauris Management est un fonds de capital-investissement spécialisé en Afrique de l'Ouest (zone UEMOA). "
                "Cible les PME et PMI dans les secteurs de l'agroalimentaire, l'industrie et les services. "
                "Tickets en FCFA équivalant à 500 K€–8 M€. "
                "Accompagnement en gouvernance et développement stratégique."
            ),
            "eligibility_criteria": "PME de la zone UEMOA (Sénégal, Côte d'Ivoire, Burkina, Mali…) en croissance.",
            "geographic_scope": "regional",
        },
        {
            "title": "Seedstars Africa Ventures – Fonds Seed Tech Afrique émergente",
            "organism": "Seedstars",
            "country": "Sénégal",
            "device_type": "investissement",
            "sectors": ["numerique", "finance", "sante", "agriculture"],
            "beneficiaries": ["startup"],
            "amount_min": 200_000, "amount_max": 2_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://www.seedstars.com/ventures",
            "short_description": (
                "Seedstars Africa Ventures investit en seed dans des startups tech dans les marchés africains "
                "à fort potentiel de croissance. Tickets de 200 K$ à 2 M$. "
                "Réseau mondial de 6 000 startups, présence dans 25 pays africains. "
                "Programme d'accélération inclus pour les lauréats."
            ),
            "eligibility_criteria": "Startup tech africaine au stade seed, solution locale scalable, équipe diversifiée.",
            "geographic_scope": "continental",
        },
        {
            "title": "Launch Africa – Fonds Micro-VC Pan-Africain (Seed)",
            "organism": "Launch Africa Ventures",
            "country": "Maroc",
            "device_type": "investissement",
            "sectors": ["numerique", "finance", "sante", "transport", "agriculture"],
            "beneficiaries": ["startup"],
            "amount_min": 100_000, "amount_max": 1_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://www.launchafricaventures.com",
            "short_description": (
                "Launch Africa est un fonds micro-VC pan-africain qui investit en pre-seed et seed "
                "dans des startups tech avec un fort potentiel. "
                "100 K$ à 1 M$ par ticket. Portefeuille de 100+ startups dans 30 pays africains. "
                "Réseau de 150 co-investisseurs africains et internationaux."
            ),
            "eligibility_criteria": "Startup tech africaine, pre-seed ou seed, produit validé ou MVP fonctionnel.",
            "geographic_scope": "continental",
        },
        {
            "title": "Janngo Capital – Fonds Tech & Impact pour l'Afrique",
            "organism": "Janngo Capital",
            "country": "Côte d'Ivoire",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "finance", "agriculture", "education"],
            "beneficiaries": ["startup", "pme"],
            "amount_min": 500_000, "amount_max": 5_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.janngo.africa",
            "short_description": (
                "Janngo Capital (fondé par Fatoumata Ba) est un fonds tech & impact ciblant les entreprises "
                "africaines qui placent les femmes et les jeunes au centre de leur modèle. "
                "60 M€ levés, investit de la seed à la série A. "
                "Présence Afrique francophone et anglophone."
            ),
            "eligibility_criteria": (
                "Startup ou PME tech africaine, business model inclusif, "
                "impact démontré sur les communautés les moins desservies."
            ),
            "geographic_scope": "continental",
        },
        {
            "title": "TLcom Capital – Fonds Série A/B Tech Afrique",
            "organism": "TLcom Capital",
            "country": "Sénégal",
            "device_type": "investissement",
            "sectors": ["numerique", "finance", "sante", "transport"],
            "beneficiaries": ["startup", "pme"],
            "amount_min": 2_000_000, "amount_max": 15_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://tlcomcapital.com",
            "short_description": (
                "TLcom Capital est un fonds VC panafricain centré sur les startups tech en croissance "
                "en phase série A et B. 150 M$ sous gestion. Portfolio : Andela, Twiga Foods, Kobo360. "
                "Focus Kenya, Nigeria, Afrique du Sud et francophone."
            ),
            "eligibility_criteria": "Startup tech en hypercroissance, series A minimum, modèle scalable prouvé.",
            "geographic_scope": "continental",
        },

        # ══════════════════════════════════════════════════════════════════════
        # AFRIQUE — INSTITUTIONNELS PRIVÉS
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "BOAD – Fonds de Capital Investissement UEMOA",
            "organism": "Banque Ouest-Africaine de Développement (BOAD)",
            "country": "Togo",
            "device_type": "investissement",
            "sectors": ["industrie", "agriculture", "energie", "transport", "finance"],
            "beneficiaries": ["pme", "eti"],
            "amount_min": 500_000, "amount_max": 20_000_000,
            "currency": "XOF",
            "status": "open",
            "source_url": "https://www.boad.org/secteur-prive",
            "short_description": (
                "La BOAD accompagne le secteur privé de l'UEMOA via des prises de participations, "
                "lignes de crédit aux banques locales et garanties. "
                "Cible les PME et ETI de l'agroalimentaire, l'industrie, l'énergie et l'infrastructure. "
                "Guichet secteur privé en cours de développement."
            ),
            "eligibility_criteria": "Entreprise privée de la zone UEMOA, projet viable, financement complémentaire au crédit bancaire.",
            "geographic_scope": "regional",
        },
        {
            "title": "BAD – Fonds Afrique 50 (Infrastructure & Secteur Privé)",
            "organism": "Banque Africaine de Développement (BAD) — Africa50",
            "country": "Maroc",
            "device_type": "investissement",
            "sectors": ["energie", "transport", "eau", "numerique"],
            "beneficiaries": ["eti"],
            "amount_min": 10_000_000, "amount_max": 200_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://www.africa50.com",
            "short_description": (
                "Africa50 est un fonds d'infrastructure africain lancé par la BAD. "
                "3 Md$ de capital. Investit en equity et quasi-equity dans des projets "
                "d'infrastructure (énergie, transport, numérique, eau) en Afrique. "
                "Tickets de 10 à 200 M$. Co-investissement avec des partenaires publics et privés."
            ),
            "eligibility_criteria": "Projet d'infrastructure africain à grande échelle, secteur public ou partenariat public-privé.",
            "geographic_scope": "continental",
        },
        {
            "title": "XSML – Fonds Small & Medium Business Afrique Centrale",
            "organism": "XSML",
            "country": "Cameroun",
            "device_type": "investissement",
            "sectors": ["agriculture", "industrie", "sante", "education"],
            "beneficiaries": ["pme"],
            "amount_min": 100_000, "amount_max": 2_000_000,
            "currency": "USD",
            "status": "open",
            "source_url": "https://www.xsml.com",
            "short_description": (
                "XSML est un fonds d'investissement spécialisé dans les petites et moyennes entreprises "
                "d'Afrique centrale (RDC, Cameroun, Congo). "
                "Tickets de 100 K$ à 2 M$ en equity et quasi-equity. "
                "Accompagnement en gouvernance et digitalisation inclus."
            ),
            "eligibility_criteria": "PME d'Afrique centrale, formelle, CA > 100 K$, impact local démontrable.",
            "geographic_scope": "regional",
        },
        {
            "title": "Averroès Finance – Fonds de Co-Investissement Méditerranée",
            "organism": "Averroès Finance",
            "country": "Maroc",
            "device_type": "investissement",
            "sectors": ["numerique", "industrie", "finance", "sante"],
            "beneficiaries": ["pme", "startup"],
            "amount_min": 500_000, "amount_max": 10_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.averroes-finance.com",
            "short_description": (
                "Averroès Finance est un fonds de fonds franco-maghrébin qui investit dans des fonds "
                "de capital-risque et capital-développement au Maghreb (Maroc, Tunisie, Algérie) "
                "et en Europe du Sud. Soutenu par Bpifrance et l'UE. "
                "Favorise les co-investissements entre fonds européens et nord-africains."
            ),
            "eligibility_criteria": "Entreprise innovante du Maghreb ou PME méditerranéenne avec potentiel export.",
            "geographic_scope": "regional",
        },

        # ══════════════════════════════════════════════════════════════════════
        # PROGRAMMES MIXTES PUBLIC-PRIVÉ
        # ══════════════════════════════════════════════════════════════════════
        {
            "title": "French Tech Capital – Fonds de Co-Investissement Startups French Tech",
            "organism": "French Tech / BPI",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "industrie", "environnement"],
            "beneficiaries": ["startup"],
            "amount_min": 500_000, "amount_max": 15_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://lafrenchtech.com/fr/comment-on-aide/french-tech-capital/",
            "short_description": (
                "French Tech Capital est un dispositif de co-investissement géré par Bpifrance "
                "dans le cadre de la mission French Tech. "
                "Investit en systématique aux côtés de fonds privés labellisés dans des startups French Tech. "
                "500 K€ à 15 M€ par tour. Dédié aux startups inscrites dans un hub French Tech."
            ),
            "eligibility_criteria": "Startup membre d'un hub French Tech, tour de financement en cours, co-lead privé identifié.",
            "geographic_scope": "national",
        },
        {
            "title": "SATT (Sociétés d'Accélération du Transfert de Technologies)",
            "organism": "Réseau des SATT — 13 SATT en France",
            "country": "France",
            "device_type": "investissement",
            "sectors": ["numerique", "sante", "industrie", "environnement", "agriculture"],
            "beneficiaries": ["chercheur", "startup"],
            "amount_min": 50_000, "amount_max": 2_000_000,
            "currency": "EUR",
            "status": "open",
            "source_url": "https://www.satt.fr",
            "short_description": (
                "Les 13 SATT investissent dans la maturation de technologies issues de la recherche publique "
                "en vue de leur transfert vers des startups ou des industriels. "
                "Financement de 50 K€ à 2 M€ (maturation + protection IP). "
                "Accès aux brevets, licences et accompagnement pour créer une startup deeptech."
            ),
            "eligibility_criteria": "Chercheur ou laboratoire avec une innovation brevetable issue d'un établissement public.",
            "geographic_scope": "national",
        },
    ]


async def fetch_private_finance(limit: int) -> list:
    """
    Combine : catalogue curé (VC + BA + Institutionnels) + IFC + Proparco.
    """
    items = []

    # 1. Catalogue curé VC / Business Angels
    catalog = build_private_finance_catalog()
    items.extend(catalog)
    logger.info(f"  Catalogue curé: {len(catalog)} fonds/réseaux")

    # 2. Projets IFC (World Bank Private)
    ifc_items = await fetch_ifc(min(limit // 2, 150))
    items.extend(ifc_items)

    # 3. Proparco (AFD private)
    proparco_items = await fetch_proparco(min(limit // 2, 100))
    items.extend(proparco_items)

    logger.info(f"  Financement privé TOTAL: {len(items)} éléments")
    return items[:limit]


# ─── Insertion en base ────────────────────────────────────────────────────────
async def insert_devices(items: list, source_name: str, source_id: Optional[str] = None) -> dict:
    """
    Insère les dispositifs via DeviceService (déduplication par slug/hash).
    """
    from app.database import AsyncSessionLocal
    from app.services.device_service import DeviceService
    from app.schemas.device import DeviceCreate
    from app.collector.enricher import Enricher
    from app.utils.hash_utils import compute_content_hash
    from app.utils.text_utils import sanitize_text, looks_english_text, derive_device_status, extract_close_date

    enricher = Enricher()
    stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        service = DeviceService(db)

        for item in items:
            try:
                short_description = sanitize_text(item.get("short_description") or "")
                full_description = sanitize_text(item.get("full_description") or "")

                combined_text = f"{short_description} {full_description}".strip()
                if looks_english_text(combined_text):
                    stats["skipped"] += 1
                    continue

                item["short_description"] = short_description or None
                if full_description:
                    item["full_description"] = full_description

                close_date = item.get("close_date")
                if close_date is None:
                    close_date = extract_close_date(
                        " ".join(
                            part for part in [
                                item.get("title") or "",
                                short_description,
                                full_description,
                                item.get("source_raw") or "",
                            ] if part
                        )
                    )
                    item["close_date"] = close_date
                item["status"] = derive_device_status(close_date, item.get("status"))

                # Enrichissement
                enriched = enricher.enrich(item, source_level=1)
                enriched["source_hash"] = compute_content_hash(
                    (enriched.get("title") or "") + (enriched.get("short_description") or "")
                )
                if source_id:
                    enriched["source_id"] = source_id

                # Champs autorisés par DeviceCreate
                from app.collector.pipeline import DEVICE_CREATE_FIELDS
                create_data = {k: v for k, v in enriched.items() if k in DEVICE_CREATE_FIELDS}
                # Assurer les champs obligatoires
                create_data.setdefault("title", item.get("title", "Sans titre"))
                create_data.setdefault("organism", item.get("organism", source_name))
                create_data.setdefault("country", item.get("country", "France"))
                create_data.setdefault("device_type", item.get("device_type", "autre"))
                create_data.setdefault("source_url", item.get("source_url", "https://kafundo.com"))
                create_data.setdefault("status", item.get("status", "open"))

                device_schema = DeviceCreate(**create_data)
                await service.create(device_schema, created_by="seed_real")
                stats["new"] += 1

            except Exception as e:
                err_msg = str(e).lower()
                if "unique" in err_msg or "duplicate" in err_msg or "already exists" in err_msg:
                    stats["skipped"] += 1
                else:
                    logger.debug(f"  Erreur insertion '{item.get('title', '?')[:50]}': {e}")
                    stats["errors"] += 1

    return stats


# ─── Main ─────────────────────────────────────────────────────────────────────
async def run():
    from app.database import create_tables

    print()
    print("=" * 60)
    print("  Kafundo - Collecte de donnees REELLES")
    print("=" * 60)
    print(f"  Sources  : {', '.join(args.sources)}")
    print(f"  Limite   : {args.limit} dispositifs / source")
    print()

    await create_tables()

    FETCHERS = {
        "worldbank": ("World Bank Open Data",             fetch_worldbank),
        "afd":       ("AFD Open Data",                    fetch_afd),
        "ademe":     ("ADEME data.ademe.fr",              fetch_ademe),
        "datagouv":  ("data.gouv.fr",                     fetch_datagouv),
        "eu":        ("EU Grants API",                    fetch_eu_grants),
        "private":   ("VC / Business Angels / Privé",     fetch_private_finance),
        "ifc":       ("IFC — World Bank Private Sector",  fetch_ifc),
        "proparco":  ("Proparco — AFD Secteur Privé",     fetch_proparco),
    }

    total_new = 0
    total_skip = 0
    total_errors = 0

    for key in args.sources:
        if key not in FETCHERS:
            print(f"  Source inconnue '{key}' — ignorée")
            continue
        if key == "datagouv":
            print("  Source 'datagouv' désactivée — trop de jeux de données historiques et de faux positifs.")
            print("  Utiliser des datasets data.gouv.fr ciblés en liste blanche si besoin.")
            print()
            continue

        name, fetcher = FETCHERS[key]
        print(f"Collecte : {name}")
        print(f"  Récupération des données...")

        items = await fetcher(args.limit)
        print(f"  {len(items)} dispositifs récupérés")

        if items:
            print(f"  Insertion en base...")
            stats = await insert_devices(items, name)
            total_new   += stats["new"]
            total_skip  += stats["skipped"]
            total_errors += stats["errors"]
            print(f"  OK — nouveau:{stats['new']}  doublons:{stats['skipped']}  erreurs:{stats['errors']}")
        else:
            print(f"  Aucun item récupéré (vérifier la connectivité réseau)")
        print()

    print("=" * 60)
    print("  Résumé")
    print("=" * 60)
    print(f"  Nouveaux dispositifs : {total_new}")
    print(f"  Doublons ignorés     : {total_skip}")
    print(f"  Erreurs              : {total_errors}")
    print()
    if total_new > 0:
        print("  Données disponibles sur : http://localhost:3000")
    else:
        print("  Aucune donnée insérée.")
        print("  Vérifiez la connectivité internet du conteneur.")
    print()


if __name__ == "__main__":
    asyncio.run(run())
