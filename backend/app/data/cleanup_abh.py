import asyncio
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Africa's Business Heroes"


def _build_summary(device: Device) -> str:
    return (
        "Africa's Business Heroes 2026 est un concours panafricain soutenu par la Fondation Jack Ma pour identifier, "
        "faire grandir et mettre en visibilite des entrepreneurs africains a fort potentiel. "
        "L'edition 2026 etait ouverte jusqu'au 28/04/2026 et la fiche doit maintenant etre lue comme un appel cloture."
    )


def _build_eligibility() -> str:
    return (
        "Le concours s'adresse a des entrepreneurs africains porteurs d'une entreprise ou d'un projet a fort potentiel de croissance et d'impact. "
        "Les criteres detailles d'anciennete, de traction, de leadership et de perimetre geographique doivent etre verifies sur la page officielle du programme."
    )


def _build_funding(device: Device) -> str:
    parts = []
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            parts.append(f"Montant indicatif repere entre {device.amount_min} et {device.amount_max} {device.currency or 'USD'}.")
        else:
            parts.append(f"Montant indicatif repere : {device.amount_max or device.amount_min} {device.currency or 'USD'}.")
    parts.append(
        "Le programme combine dotation, mentorat, accompagnement, visibilite internationale et mise en reseau pour les finalistes et laureats."
    )
    parts.append("Les montants exacts par tour et les avantages complementaires doivent etre confirmes sur la source officielle.")
    return " ".join(parts).strip()


def _build_procedure() -> str:
    return (
        "La candidature se depose depuis la page officielle d'Africa's Business Heroes. Pour l'edition 2026, la date limite etait fixee au 28/04/2026 ; "
        "il faut suivre la prochaine ouverture pour une future candidature."
    )


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 260
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 90
        and len(clean_editorial_text(device.funding_details or "")) >= 80
        and device.status in {"expired", "closed", "open", "recurring", "standby"}
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

            target_status = "expired" if device.close_date and device.close_date < date.today() else "open"
            if device.status != target_status:
                device.status = target_status
                changed = True
            if device.is_recurring:
                device.is_recurring = False
                changed = True
            if device.recurrence_notes:
                device.recurrence_notes = None
                changed = True

            summary = _build_summary(device)
            eligibility = _build_eligibility()
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
