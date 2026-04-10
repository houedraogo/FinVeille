"""
Importe les 228 dispositifs de financement depuis le fichier Excel de veille.
Usage : docker exec finveille-backend python app/data/seed_excel.py
"""
import asyncio
import json
import re
import sys
import os
from contextlib import asynccontextmanager

JSON_PATH = "/app/app/data/excel_sources.json"


# ─── Mapping type de financement → device_type ────────────────────────────
TYPE_MAP = {
    "equity": "investissement",
    "quasi-equity": "investissement",
    "obligations convertibles": "investissement",
    "crowdfunding": "investissement",
    "revenue-based financing": "investissement",
    "subvention": "subvention",
    "prêt": "pret",
    "pret": "pret",
    "prêt d'honneur": "pret",
    "prêt participatif": "pret",
    "avance remboursable": "pret",
    "garantie": "garantie",
    "accompagnement": "accompagnement",
    "concours": "concours",
}

# ─── Mapping secteurs ─────────────────────────────────────────────────────
SECTOR_MAP = {
    "fintech": "finance",
    "agritech": "agriculture",
    "healthtech": "sante",
    "edtech": "education",
    "énergie": "energie",
    "energie": "energie",
    "cleantech": "energie",
    "e-commerce": "industrie",
    "logistique": "transport",
    "immobilier": "immobilier",
    "saas": "numerique",
    "b2b tech": "numerique",
    "mining": "industrie",
    "télécoms": "numerique",
    "telecoms": "numerique",
    "tourisme": "tourisme",
    "environnement": "environnement",
    "esg": "environnement",
    "multi-sectoriel": "transversal",
    "jeu vidéo": "culture",
    "création numérique": "culture",
    "industrie": "industrie",
}

# ─── Mapping bénéficiaires (stade) ────────────────────────────────────────
BENE_MAP = {
    "idée": "porteur_projet",
    "mvp": "startup",
    "early revenue": "startup",
    "croissance": "pme",
    "scale-up": "eti",
}

# ─── Mapping pays ─────────────────────────────────────────────────────────
def normalize_country(raw: str) -> str:
    if not raw or raw == "nan":
        return "International"
    raw = str(raw)
    # Retire les parenthèses et leur contenu si > 1 pays
    c = re.sub(r"\s*\(.*?\)", "", raw).strip()
    mapping = {
        "pan-afrique": "Afrique",
        "pan afrique": "Afrique",
        "ue": "Europe",
        "union européenne": "Europe",
        "france (pan-afrique)": "France",
        "côte d'ivoire": "Côte d'Ivoire",
        "senegal": "Sénégal",
        "sénégal": "Sénégal",
        "nigeria": "Nigeria",
        "egypte": "Égypte",
        "égypte": "Égypte",
        "afrique du sud": "Afrique du Sud",
        "kenya": "Kenya",
        "rwanda": "Rwanda",
        "tunisie": "Tunisie",
        "maroc": "Maroc",
        "international": "International",
        "allemagne": "Allemagne",
        "suisse": "Suisse",
        "pays-bas": "Pays-Bas",
    }
    return mapping.get(c.lower(), c)


def parse_amount(val) -> float | None:
    if val is None or str(val).lower() in ("nan", "", "0", "n/a", "-"):
        return None
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except Exception:
        return None


def map_device_type(raw: str) -> str:
    if not raw or raw == "nan":
        return "subvention"
    return TYPE_MAP.get(raw.lower().strip(), "subvention")


def map_sectors(raw: str) -> list:
    if not raw or raw == "nan":
        return ["transversal"]
    sectors = set()
    for part in re.split(r"[/,;]", str(raw)):
        part = part.strip().lower()
        for key, val in SECTOR_MAP.items():
            if key in part:
                sectors.add(val)
                break
    return list(sectors) if sectors else ["transversal"]


def map_beneficiaries(raw: str) -> list:
    if not raw or raw == "nan":
        return ["startup"]
    b = BENE_MAP.get(str(raw).lower().strip())
    return [b] if b else ["startup"]


def map_currency(country: str) -> str:
    if any(x in country for x in ["Sénégal", "Côte d'Ivoire", "Mali", "Burkina",
                                    "Bénin", "Niger", "Togo", "Guinée-Bissau"]):
        return "XOF"
    if "Maroc" in country:
        return "MAD"
    if "Tunisie" in country:
        return "TND"
    return "EUR"


def build_devices(rows: list, sheet_name: str) -> list:
    devices = []
    seen = set()
    for row in rows:
        title = str(row.get("Nom du dispositif", "")).strip()
        if not title or title.lower() in ("nan", "", "—", "-"):
            continue
        if title in seen:
            continue
        seen.add(title)

        country_raw = str(row.get("Pays", "International"))
        country = normalize_country(country_raw)
        type_fin = str(row.get("Type de financement", ""))
        device_type = map_device_type(type_fin)
        amount_min = parse_amount(row.get("Ticket minimum"))
        amount_max = parse_amount(row.get("Ticket maximum"))
        url = str(row.get("Lien officiel", "") or "").strip()
        if not url or url == "nan":
            url = f"https://www.google.com/search?q={title.replace(' ', '+')}"
        organism = str(row.get("Organisme gestionnaire", "") or "").strip()
        if not organism or organism == "nan":
            organism = title

        eligibility = str(row.get("Critères d'éligibilité clés", "") or "").strip()
        if eligibility == "nan":
            eligibility = ""
        conditions = str(row.get("Exigences particulières", "") or "").strip()
        if conditions == "nan":
            conditions = ""
        comments = str(row.get("Commentaires / Observations", "") or "").strip()
        if comments == "nan":
            comments = ""

        pertinence = row.get("Pertinence (1-5)", 3)
        try:
            pertinence = int(float(str(pertinence)))
        except Exception:
            pertinence = 3
        confidence = 60 + pertinence * 8  # 68-100

        dilution = str(row.get("% dilution moyenne", "") or "").strip()
        dilution_note = f"Dilution : {dilution}" if dilution and dilution != "nan" and dilution != "N/A" else ""

        short_desc = " | ".join(filter(None, [
            f"Type : {type_fin}" if type_fin and type_fin != "nan" else "",
            f"Stade : {row.get('Stade ciblé', '')}" if row.get("Stade ciblé") and str(row.get("Stade ciblé")) != "nan" else "",
            dilution_note,
            comments[:200] if comments else "",
        ]))

        devices.append({
            "title": title,
            "organism": organism,
            "country": country,
            "region": str(row.get("Région", "") or "").replace("nan", "").strip() or None,
            "device_type": device_type,
            "status": "open",
            "source_url": url,
            "short_description": short_desc[:500] if short_desc else None,
            "eligibility_criteria": eligibility[:1000] if eligibility else None,
            "specific_conditions": conditions[:500] if conditions else None,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "currency": map_currency(country),
            "sectors": map_sectors(str(row.get("Secteurs ciblés", ""))),
            "beneficiaries": map_beneficiaries(str(row.get("Stade ciblé", ""))),
            "confidence_score": min(100, confidence),
            "completeness_score": 65,
            "relevance_score": pertinence * 20,
            "validation_status": "validated",
            "is_recurring": True,
        })
    return devices


@asynccontextmanager
async def get_db():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


async def main():
    import sys
    sys.path.insert(0, "/app")

    from app.services.device_service import DeviceService
    from app.schemas.device import DeviceCreate
    from app.collector.enricher import Enricher
    from sqlalchemy import select, func
    from app.models.device import Device

    # Charger le JSON
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    all_devices = []
    for sheet in ["Afrique", "France"]:
        if sheet not in data:
            print(f"⚠️  Sheet '{sheet}' introuvable")
            continue
        rows = data[sheet]["rows"]
        devices = build_devices(rows, sheet)
        print(f"📋 {sheet}: {len(devices)} dispositifs extraits")
        all_devices.extend(devices)

    print(f"\n🔄 Import de {len(all_devices)} dispositifs en base...")

    enricher = Enricher()
    inserted = 0
    skipped = 0
    errors = 0

    # Charger les titres existants pour déduplication
    async with get_db() as db:
        r = await db.execute(select(Device.title))
        existing_titles = {row[0].lower().strip() for row in r.fetchall()}

    async with get_db() as db:
        service = DeviceService(db)
        for d in all_devices:
            title = d.get("title", "")
            if title.lower().strip() in existing_titles:
                skipped += 1
                continue
            try:
                # Enrichissement des scores
                d = enricher.enrich(d)
                # Forcer validation (source manuelle fiable)
                d["validation_status"] = "validated"
                d["confidence_score"] = d.get("confidence_score", 75)

                payload = DeviceCreate(**{
                    k: v for k, v in d.items()
                    if k in DeviceCreate.model_fields
                })
                await service.create(payload, created_by="import_excel")
                existing_titles.add(title.lower().strip())
                inserted += 1
                if inserted % 25 == 0:
                    print(f"  → {inserted} insérés...")
            except Exception as e:
                errors += 1
                print(f"  ❌ Erreur [{title}]: {e}")

    print(f"\n✅ Résultat : {inserted} insérés | {skipped} déjà existants | {errors} erreurs")

    # Stats finales
    async with get_db() as db:
        r = await db.execute(select(func.count()).select_from(Device))
        total = r.scalar()
        print(f"📊 Total dispositifs en base : {total}")


if __name__ == "__main__":
    asyncio.run(main())
