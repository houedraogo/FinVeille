"""
Nettoie le stock AECF :
- publie les deux fiches metier propres
- rejette les anciens doublons et le bruit editorial historique

Usage : docker exec finveille-backend python -m app.data.cleanup_aecf
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import build_structured_sections, compute_completeness


GENERAL_SOURCE = "AECF - competitions et challenge funds"
DIFEC_SOURCE = "AECF - DIFEC"

KEEP_TITLES = {
    "AECF - entrepreneuriat feminin pour une economie plus verte au Benin et au Burkina Faso",
    "AECF - Digital Innovation Fund for Energy & Climate (DIFEC)",
}

REJECT_TITLE_SNIPPETS = (
    "Shaping tomorrow, today",
    "AECF-WHO regional workshop",
    "Investing in women entrepreneurship for a greener economy In Benin and Burkina Faso",
    "Investir dans l'entrepreneuriat féminin pour une économie plus verte Au Bénin et au Burkina Faso",
)


def _aecf_payload(device: Device) -> dict[str, str]:
    title = device.title or ""
    if "DIFEC" in title:
        return {
            "summary": (
                "Programme AECF destine aux entreprises africaines qui developpent des solutions "
                "digitales pour l'energie propre, le climat et l'acces aux services essentiels. "
                "La fiche doit etre confirmee sur la page officielle AECF avant candidature."
            ),
            "eligibility": (
                "La cible principale est constituee d'entreprises ou organisations africaines "
                "portant des solutions numeriques liees a l'energie, au climat ou a la resilience. "
                "Les pays eligibles, le stade de maturite, les exigences de cofinancement et les "
                "pieces attendues doivent etre confirmes sur la source officielle AECF."
            ),
            "funding": (
                "La fiche mentionne deux fenetres de financement indicatives, avec des tickets "
                "pouvant se situer entre 150 000 et 400 000 USD selon la categorie et le profil du "
                "projet. Les montants exacts et contreparties doivent etre verifies sur AECF."
            ),
            "procedure": (
                "Consulter la page officielle AECF DIFEC pour verifier l'ouverture effective, "
                "telecharger les lignes directrices et suivre la procedure de candidature indiquee."
            ),
        }

    return {
        "summary": (
            "Programme AECF visant a soutenir l'entrepreneuriat feminin et des activites plus "
            "vertes au Benin et au Burkina Faso. La fiche est utile pour la veille, mais les "
            "conditions operationnelles doivent etre confirmees sur la page officielle AECF."
        ),
        "eligibility": (
            "Le programme cible principalement des femmes entrepreneures, entreprises ou projets "
            "portes dans les zones couvertes au Benin et au Burkina Faso, avec une orientation "
            "economie verte, impact local et developpement economique. Les criteres exacts, "
            "secteurs eligibles et exclusions doivent etre confirmes sur AECF."
        ),
        "funding": (
            "Le soutien peut combiner financement, appui technique, accompagnement et renforcement "
            "de capacites selon le profil du projet. Les montants, plafonds et obligations de "
            "cofinancement doivent etre confirmes sur la source officielle."
        ),
        "procedure": (
            "Consulter la page officielle AECF du programme pour verifier les fenetres ouvertes, "
            "les documents requis, les criteres d'eligibilite et la procedure de depot."
        ),
    }


def _normalize_device(device: Device) -> bool:
    payload = _aecf_payload(device)
    changed = False

    if device.status == "open" and not device.close_date:
        device.status = "standby"
        changed = True

    if device.status == "standby":
        note = (
            "Date limite non communiquee par la source publique. "
            "La fiche reste exploitable avec verification sur la source officielle AECF."
        )
        if device.recurrence_notes != note:
            device.recurrence_notes = note
            changed = True

    if device.device_type in {None, "", "autre"}:
        device.device_type = "subvention"
        changed = True

    if device.short_description != payload["summary"]:
        device.short_description = payload["summary"]
        changed = True

    if device.eligibility_criteria != payload["eligibility"]:
        device.eligibility_criteria = payload["eligibility"]
        changed = True

    if device.funding_details != payload["funding"]:
        device.funding_details = payload["funding"]
        changed = True

    full_description = build_structured_sections(
        presentation=payload["summary"],
        eligibility=payload["eligibility"],
        funding=payload["funding"],
        open_date=device.open_date,
        close_date=device.close_date,
        procedure=payload["procedure"],
        recurrence_notes=device.recurrence_notes,
    )
    if device.full_description != full_description:
        device.full_description = full_description
        changed = True

    device.validation_status = "auto_published"
    device.completeness_score = compute_completeness(
        {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    )

    # Les sections structurees sont suffisamment propres pour servir de fallback public.
    sections = [
        {"key": "presentation", "title": "Presentation", "content": payload["summary"], "confidence": 75, "source": "aecf_cleanup"},
        {"key": "eligibility", "title": "Criteres d'eligibilite", "content": payload["eligibility"], "confidence": 75, "source": "aecf_cleanup"},
        {"key": "funding", "title": "Montant / avantages", "content": payload["funding"], "confidence": 75, "source": "aecf_cleanup"},
        {"key": "calendar", "title": "Calendrier", "content": device.recurrence_notes or "Date limite a confirmer sur la source officielle.", "confidence": 70, "source": "aecf_cleanup"},
        {"key": "procedure", "title": "Demarche", "content": payload["procedure"], "confidence": 75, "source": "aecf_cleanup"},
        {"key": "checks", "title": "Points a verifier", "content": "Verifier la date limite, les pays eligibles, les montants exacts et les documents attendus sur AECF.", "confidence": 70, "source": "aecf_cleanup"},
    ]
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = "structured_sections_fallback"
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    return changed


async def run() -> None:
    async with AsyncSessionLocal() as db:
        sources = (
            await db.execute(
                select(Source).where(Source.name.in_([GENERAL_SOURCE, DIFEC_SOURCE]))
            )
        ).scalars().all()
        source_ids = {str(source.id) for source in sources}

        devices = (
            await db.execute(
                select(Device).where(Device.source_id.in_([source.id for source in sources]))
            )
        ).scalars().all()

        published = 0
        rejected = 0
        now = datetime.now(timezone.utc)

        for device in devices:
            if device.title in KEEP_TITLES:
                _normalize_device(device)
                device.last_verified_at = now
                published += 1
                continue

            if any(snippet == (device.title or "") for snippet in REJECT_TITLE_SNIPPETS):
                device.validation_status = "rejected"
                device.last_verified_at = now
                rejected += 1

        await db.commit()
        print(
            f"[OK] AECF cleanup termine | sources={len(source_ids)} | "
            f"published={published} | rejected={rejected}"
        )


if __name__ == "__main__":
    asyncio.run(run())
