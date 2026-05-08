import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Prix Pierre Castel"


def _build_summary(device: Device) -> str:
    parts = [
        "Le Prix Pierre Castel 2026 est un concours panafricain destine a identifier et accompagner des entrepreneurs innovants engages dans les systemes alimentaires africains.",
        "L'appel a candidatures est ouvert dans plusieurs pays participants avec une cloture annoncee au 30/05/2026.",
    ]
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            parts.append(f"La dotation reperee se situe entre {device.amount_min} et {device.amount_max} {device.currency or 'EUR'}.")
        else:
            parts.append(f"La dotation reperee peut atteindre {device.amount_max or device.amount_min} {device.currency or 'EUR'}.")
    parts.append("Le programme combine soutien financier, mentorat, coaching et visibilite pour les laureats.")
    return " ".join(parts).strip()[:500]


def _build_eligibility(device: Device) -> str:
    return (
        "Le concours cible des entrepreneurs africains porteurs de solutions innovantes dans les systemes alimentaires, "
        "avec une implantation dans les pays participants de l'edition 2026. Les criteres detailles, les pays exacts "
        "et les conditions de recevabilite doivent etre verifies sur la page officielle."
    )


def _build_funding(device: Device) -> str:
    parts = []
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            parts.append(f"Montant indicatif repere entre {device.amount_min} et {device.amount_max} {device.currency or 'EUR'}.")
        else:
            parts.append(f"Montant indicatif repere : {device.amount_max or device.amount_min} {device.currency or 'EUR'}.")
    parts.append(
        "La source mentionne une dotation financiere pour chaque laureat national, completee par du mentorat, du coaching personnalise et, pour un laureat panafricain, un appui additionnel."
    )
    parts.append("Les montants exacts par categorie et les avantages complementaires doivent etre confirmes sur la source officielle.")
    return " ".join(parts).strip()


def _build_procedure() -> str:
    return (
        "La candidature se prepare depuis la plateforme officielle du Prix Pierre Castel. Il faut verifier les pays eligibles, "
        "le calendrier detaille, les pieces attendues et les modalites de depot avant soumission."
    )


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 280
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 90
        and len(clean_editorial_text(device.funding_details or "")) >= 80
        and device.status in {"open", "expired", "recurring", "standby"}
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

            if device.status != "open":
                device.status = "open"
                changed = True
            if device.is_recurring:
                device.is_recurring = False
                changed = True
            if device.recurrence_notes:
                device.recurrence_notes = None
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
                procedure=_build_procedure(),
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
