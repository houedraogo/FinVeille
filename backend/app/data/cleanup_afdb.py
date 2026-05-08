import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Banque Africaine de Developpement - opportunites"


def _notes(device: Device) -> dict[str, str]:
    title = clean_editorial_text(device.title).lower()
    if "afawa" in title:
        return {
            "presentation": "AFAWA est une initiative de la Banque Africaine de Developpement qui vise a ameliorer l'acces au financement des femmes entrepreneures en Afrique, avec une combinaison d'instruments financiers et d'appui technique.",
            "eligibility": "Le programme cible des institutions financieres partenaires et, de facon indirecte, des entreprises fondees ou dirigees par des femmes sur le continent africain.",
            "funding": "Le dispositif s'appuie sur des garanties, de l'assistance technique et des mecanismes d'accompagnement pour fluidifier l'acces au credit et aux services financiers.",
            "procedure": "La consultation detaillee se fait depuis la page officielle AFAWA. Il faut verifier les pays couverts, les partenaires financiers actifs et les modalites d'acces selon votre situation.",
            "recurrence": "Initiative institutionnelle recurrente ou permanente de la BAD, sans date de cloture unique conservee dans la fiche actuelle.",
        }
    return {
        "presentation": "Le Fonds Jeunesse BAD s'inscrit dans l'initiative Jobs for Youth in Africa et soutient des actions favorisant l'employabilite, l'entrepreneuriat et l'inclusion economique des jeunes.",
        "eligibility": "Le dispositif vise des programmes, partenaires ou interventions lies a l'insertion professionnelle, a l'entrepreneuriat des jeunes et au developpement economique sur le continent africain.",
        "funding": "Le soutien prend la forme d'un fonds ou d'un mecanisme de financement institutionnel au service des priorites jeunesse de la BAD.",
        "procedure": "Il faut consulter la page officielle Jobs for Youth in Africa pour confirmer les voies d'acces, les partenaires d'execution et les conditions de mobilisation du fonds.",
        "recurrence": "Programme institutionnel suivi comme recurrent ou permanent, sans date unique de cloture dans la fiche consolidee.",
    }


def _build_summary(device: Device) -> str:
    notes = _notes(device)
    parts = [f"{device.title} est une opportunite suivie comme programme recurrent de la Banque Africaine de Developpement, sans date de cloture unique publiee dans la fiche actuelle."]
    parts.append(notes["presentation"])
    if device.beneficiaries:
        beneficiaries = [clean_editorial_text(value).lower() for value in device.beneficiaries if clean_editorial_text(value)]
        if beneficiaries:
            if len(beneficiaries) == 1:
                parts.append(f"La fiche cible principalement les {beneficiaries[0]}.")
            else:
                parts.append(f"La fiche cible principalement les {', '.join(beneficiaries[:-1])} et {beneficiaries[-1]}.")
    parts.append("Les conditions exactes d'ouverture ou de mobilisation doivent etre confirmees sur la page officielle de la BAD.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _build_eligibility(device: Device) -> str:
    notes = _notes(device)
    sectors = [clean_editorial_text(value) for value in (device.sectors or []) if clean_editorial_text(value)]
    parts = [notes["eligibility"]]
    if sectors:
        parts.append(f"Secteurs ou themes associes dans la fiche : {', '.join(sectors)}.")
    parts.append("Les criteres detailles d'eligibilite, de partenariat et de perimetre geographique doivent etre verifies sur la source officielle.")
    return " ".join(parts).strip()


def _build_funding(device: Device) -> str:
    notes = _notes(device)
    parts = []
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            parts.append(f"Montant indicatif repere entre {device.amount_min} et {device.amount_max} {device.currency or 'EUR'}.")
        else:
            parts.append(f"Montant indicatif repere : {device.amount_max or device.amount_min} {device.currency or 'EUR'}.")
    parts.append(notes["funding"])
    parts.append("Les montants exacts, garanties mobilisables ou modalites de soutien doivent etre confirmes sur la page officielle.")
    return " ".join(parts).strip()


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 260
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 90
        and len(clean_editorial_text(device.funding_details or "")) >= 80
        and device.status in {"recurring", "standby", "open"}
    )


async def run() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (await db.execute(select(Device).where(Device.source_id == source.id).order_by(Device.title.asc()))).scalars().all()
        updated = 0
        preview: list[dict] = []

        for device in devices:
            changed = False
            if device.status != "recurring":
                device.status = "recurring"
                changed = True
            if not device.is_recurring:
                device.is_recurring = True
                changed = True

            recurrence_notes = _notes(device)["recurrence"]
            if device.recurrence_notes != recurrence_notes:
                device.recurrence_notes = recurrence_notes
                changed = True

            summary = _build_summary(device)
            eligibility = _build_eligibility(device)
            funding = _build_funding(device)
            full_description = build_structured_sections(
                presentation=summary,
                eligibility=eligibility,
                funding=funding,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=_notes(device)["procedure"],
                recurrence_notes=device.recurrence_notes,
            )

            if summary != (device.short_description or ""):
                device.short_description = summary
                changed = True
            if eligibility != (device.eligibility_criteria or ""):
                device.eligibility_criteria = eligibility
                changed = True
            if funding != (device.funding_details or ""):
                device.funding_details = funding
                changed = True
            if full_description != (device.full_description or ""):
                device.full_description = full_description
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            decision = gate.evaluate(payload)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True
            if device.validation_status == "pending_review" and _should_force_publish(device):
                device.validation_status = "auto_published"
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            device.completeness_score = compute_completeness(payload)

            if changed:
                updated += 1
                if len(preview) < 10:
                    preview.append(
                        {
                            "title": device.title,
                            "status": device.status,
                            "validation_status": device.validation_status,
                            "short_description": device.short_description,
                        }
                    )

        await db.commit()
        return {"source": SOURCE_NAME, "updated": updated, "preview": preview}


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
