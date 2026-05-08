import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "CNC - aides et financements"


def _parse_short_description(text: str | None) -> tuple[str, str, str]:
    raw = clean_editorial_text(text or "")
    if not raw:
        return "", "", ""
    parts = [part.strip() for part in raw.split("|")]
    type_label = ""
    stage_label = ""
    pitch = ""
    for part in parts:
        lowered = part.lower()
        if lowered.startswith("type :"):
            type_label = part.split(":", 1)[1].strip()
        elif lowered.startswith("stade :"):
            stage_label = part.split(":", 1)[1].strip()
        else:
            pitch = part.strip()
    return type_label, stage_label, pitch


def _format_amount(device: Device) -> str:
    if device.amount_min is None and device.amount_max is None:
        return ""

    def _fmt(value) -> str:
        amount = float(value)
        if amount.is_integer():
            return f"{int(amount):,}".replace(",", " ")
        return f"{amount:,.2f}".replace(",", " ").replace(".", ",")

    if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
        return f"entre {_fmt(device.amount_min)} EUR et {_fmt(device.amount_max)} EUR"
    amount = device.amount_max or device.amount_min
    return f"jusqu'à {_fmt(amount)} EUR"


def _beneficiaries_text(device: Device) -> str:
    values = [clean_editorial_text(item) for item in (device.beneficiaries or []) if clean_editorial_text(item)]
    lowered = [value.lower() for value in values]
    if not lowered:
        return ""
    if len(lowered) == 1:
        return lowered[0]
    if len(lowered) == 2:
        return f"{lowered[0]} et {lowered[1]}"
    return f"{', '.join(lowered[:-1])} et {lowered[-1]}"


def _build_summary(device: Device) -> str:
    _, stage_label, pitch = _parse_short_description(device.short_description)
    beneficiaries = _beneficiaries_text(device)
    amount = _format_amount(device)
    parts = [f"{device.title} est une aide CNC récurrente destinée aux professionnels de la création et des industries culturelles."]
    if pitch:
        parts.append(pitch.rstrip(".") + ".")
    if beneficiaries:
        parts.append(f"Elle s'adresse principalement aux {beneficiaries}.")
    if stage_label:
        parts.append(f"La fiche la positionne plutôt pour des projets au stade {stage_label.lower()}.")
    if amount:
        parts.append(f"Le niveau d'aide repéré se situe {amount}.")
    parts.append("Le CNC publie ce dispositif sans date nationale unique de clôture dans la fiche actuelle, avec un fonctionnement par sessions ou selon le calendrier officiel du guichet.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _build_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    beneficiaries = _beneficiaries_text(device)
    parts = []
    if beneficiaries:
        parts.append(f"Le dispositif cible principalement les {beneficiaries}.")
    if existing:
        parts.append(existing.rstrip(".") + ".")
    parts.append("Les critères détaillés, pièces à fournir et éventuelles conditions sectorielles doivent être confirmés sur la page officielle du CNC.")
    return " ".join(parts).strip()


def _build_funding(device: Device) -> str:
    _, _, pitch = _parse_short_description(device.short_description)
    amount = _format_amount(device)
    parts = []
    if amount:
        parts.append(f"Le soutien financier peut aller {amount}.")
    else:
        parts.append("Le montant exact de l'aide doit être confirmé sur la fiche officielle du CNC.")
    if pitch:
        parts.append(f"Repère utile : {pitch.rstrip('.')}.")
    return " ".join(parts).strip()


def _build_procedure(device: Device) -> str:
    title = clean_editorial_text(device.title).lower()
    if "sessions" in clean_editorial_text(device.short_description or "").lower():
        return "La demande se prépare selon les sessions ou relèves annoncées par le CNC sur la page officielle du dispositif. Il faut vérifier le prochain calendrier avant dépôt."
    if "crédit d'impôt" in title:
        return "La mobilisation du dispositif se fait dans le cadre fiscal et administratif prévu par le CNC et les services compétents. Il faut confirmer la procédure exacte sur la page officielle."
    return "La demande se prépare depuis la page officielle du CNC. Il faut confirmer le calendrier, les pièces et les modalités de dépôt avant candidature."


def _recurrence_notes(device: Device) -> str:
    short = clean_editorial_text(device.short_description or "").lower()
    if "3 sessions" in short or "sessions avr" in short:
        return "Dispositif récurrent avec plusieurs sessions annuelles mentionnées dans la fiche."
    if "crédit d'impôt" in clean_editorial_text(device.title).lower():
        return "Dispositif fiscal récurrent sans fenêtre unique de clôture nationale."
    return "Dispositif CNC récurrent ou fonctionnant par sessions, sans date de clôture nationale unique publiée."


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
            notes = _recurrence_notes(device)
            if device.recurrence_notes != notes:
                device.recurrence_notes = notes
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
            if device.validation_status in {"pending_review", "rejected"}:
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
