import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Google for Startups - programmes Afrique"


def _device_notes(device: Device) -> dict[str, str]:
    title = clean_editorial_text(device.title).lower()
    if "black founders fund" in title:
        return {
            "presentation": "Le Black Founders Fund Africa soutient des startups technologiques fondees par des entrepreneurs sous-representes, avec un appui financier sans dilution et un accompagnement operationnel.",
            "eligibility": "Le programme cible des startups technologiques africaines deja engagees dans leur phase de construction produit ou de traction, avec un leadership correspondant a l'orientation du fonds.",
            "funding": "La source mentionne un soutien en cash sans dilution, complete par des credits cloud, du mentorat et un accompagnement Google for Startups.",
            "procedure": "La candidature se prepare depuis la page officielle du programme Google for Startups. Il faut verifier l'ouverture de la prochaine cohorte, les pays eligibles et les criteres exacts avant depot.",
            "recurrence": "Programme Google for Startups organise par cohortes successives ou campagnes recurrentes, sans date unique conservee dans la fiche actuelle.",
        }
    return {
        "presentation": "Google for Startups Accelerator Africa accompagne des startups technologiques africaines avec un programme intensif de quelques mois, axe sur la croissance, la technique et la structuration.",
        "eligibility": "Le programme cible des startups africaines en phase de traction ou de croissance, avec un produit technologique deja actif et un besoin d'acceleration.",
        "funding": "Le soutien prend surtout la forme d'un accompagnement equity-free, de credits cloud, d'un mentorat Google et d'un appui technique avance plutot que d'une subvention classique en numeraire.",
        "procedure": "La candidature se fait sur la page officielle Google for Startups Accelerator Africa. Il faut verifier la prochaine cohorte ouverte, les pays couverts et les documents demandes avant soumission.",
        "recurrence": "Accelerateur opere par cohortes recurrentes ou promotions successives, sans date de cloture unique enregistree dans la fiche consolidee.",
    }


def _build_summary(device: Device) -> str:
    notes = _device_notes(device)
    beneficiaries = [clean_editorial_text(value).lower() for value in (device.beneficiaries or []) if clean_editorial_text(value)]
    parts = [f"{device.title} est un programme Google for Startups pour l'Afrique, suivi comme une opportunite recurrente plutot que comme un appel avec date unique."]
    parts.append(notes["presentation"])
    if beneficiaries:
        if len(beneficiaries) == 1:
            parts.append(f"La fiche cible principalement les {beneficiaries[0]}.")
        else:
            parts.append(f"La fiche cible principalement les {', '.join(beneficiaries[:-1])} et {beneficiaries[-1]}.")
    parts.append("La prochaine fenetre d'ouverture doit etre confirmee sur la page officielle du programme.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _build_eligibility(device: Device) -> str:
    notes = _device_notes(device)
    sectors = [clean_editorial_text(value) for value in (device.sectors or []) if clean_editorial_text(value)]
    parts = [notes["eligibility"]]
    if sectors:
        parts.append(f"Secteurs mis en avant dans la fiche : {', '.join(sectors)}.")
    parts.append("Les conditions detaillees d'eligibilite, les pays retenus et le niveau de maturite attendu doivent etre verifies sur la source officielle.")
    return " ".join(parts).strip()


def _build_funding(device: Device) -> str:
    notes = _device_notes(device)
    amount_bits = []
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            amount_bits.append(f"Montant indicatif repere entre {device.amount_min} et {device.amount_max} {device.currency or 'USD'}.")
        else:
            amount_bits.append(f"Montant indicatif repere : {device.amount_max or device.amount_min} {device.currency or 'USD'}.")
    amount_bits.append(notes["funding"])
    amount_bits.append("Les montants exacts, avantages non financiers et modalites de soutien doivent etre confirmes sur la page officielle.")
    return " ".join(part.strip() for part in amount_bits if part).strip()


def _build_procedure(device: Device) -> str:
    return _device_notes(device)["procedure"]


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 280
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

            recurrence_notes = _device_notes(device)["recurrence"]
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
                procedure=_build_procedure(device),
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
