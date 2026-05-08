import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text


JANGGO_TITLE = "Janngo Capital - investissement early-stage en Afrique"
JANGGO_PRESENTATION = (
    "Janngo Capital investit dans des startups africaines ou liees a l'Afrique, "
    "avec une attention particuliere aux modeles technologiques capables de repondre "
    "a des besoins essentiels et de changer d'echelle."
)
JANGGO_ELIGIBILITY = (
    "La cible principale est une startup a fort potentiel, deja structuree autour "
    "d'un produit, d'une equipe fondatrice et d'une ambition de croissance regionale "
    "ou panafricaine. Les criteres exacts d'investissement doivent etre confirmes "
    "aupres de Janngo Capital."
)
JANGGO_FUNDING = (
    "Le financement prend la forme d'un investissement en capital. Le ticket exact, "
    "les conditions d'entree au capital et les modalites d'accompagnement doivent "
    "etre confirmes directement avec le fonds."
)


def _set_if_changed(device: Device, field: str, value) -> bool:
    if getattr(device, field) == value:
        return False
    setattr(device, field, value)
    return True


def _fix_mojibake(value: str | None) -> str:
    text = value or ""
    replacements = {
        "d?": "d'",
        "l?": "l'",
        "qu?": "qu'",
        "n?": "n'",
        "Ã©": "é",
        "Ã¨": "è",
        "Ãª": "ê",
        "Ã ": "à",
        "Ã¢": "â",
        "Ã´": "ô",
        "Ã®": "î",
        "Ã§": "ç",
        "â€™": "'",
        "â€“": "-",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    (Device.status == "closed")
                    | (Device.source_url.ilike("%janngo.com/investments%"))
                    | (Device.title.ilike("%?%"))
                    | (Device.short_description.ilike("%?%"))
                    | (Device.eligibility_criteria.ilike("%?%"))
                    | (Device.funding_details.ilike("%?%"))
                )
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            changed = False
            before = {
                "title": device.title,
                "status": device.status,
                "type": device.device_type,
                "validation_status": device.validation_status,
            }

            if device.status == "closed" and device.close_date is None:
                changed |= _set_if_changed(device, "status", "expired")
                changed |= _set_if_changed(device, "is_recurring", False)

            title_norm = clean_editorial_text(device.title or "").lower()
            source_url = (device.source_url or "").lower()

            if "janngo.com/investments" in source_url or title_norm == "investments – janngo":
                full_description = build_structured_sections(
                    presentation=JANGGO_PRESENTATION,
                    eligibility=JANGGO_ELIGIBILITY,
                    funding=JANGGO_FUNDING,
                    procedure=(
                        "La prise de contact se fait depuis la page officielle Janngo Capital. "
                        "Le dossier, le stade attendu et les conditions d'investissement doivent "
                        "etre confirmes directement avec l'equipe du fonds."
                    ),
                    recurrence_notes="Fonds d'investissement sans fenetre de cloture publique unique.",
                )
                changed |= _set_if_changed(device, "title", JANGGO_TITLE)
                changed |= _set_if_changed(device, "device_type", "investissement")
                changed |= _set_if_changed(device, "aid_nature", "capital")
                changed |= _set_if_changed(device, "country", "Afrique")
                changed |= _set_if_changed(device, "geographic_scope", "continental")
                changed |= _set_if_changed(device, "short_description", JANGGO_PRESENTATION)
                changed |= _set_if_changed(device, "full_description", full_description)
                changed |= _set_if_changed(device, "eligibility_criteria", JANGGO_ELIGIBILITY)
                changed |= _set_if_changed(device, "funding_details", JANGGO_FUNDING)
                changed |= _set_if_changed(device, "status", "recurring")
                changed |= _set_if_changed(device, "is_recurring", True)
                changed |= _set_if_changed(
                    device,
                    "recurrence_notes",
                    "Fonds d'investissement sans fenetre de cloture publique unique.",
                )
                changed |= _set_if_changed(device, "language", "fr")
                changed |= _set_if_changed(device, "validation_status", "auto_published")

            fixed_title = _fix_mojibake(device.title)
            fixed_short = _fix_mojibake(device.short_description)
            fixed_eligibility = _fix_mojibake(device.eligibility_criteria)
            fixed_funding = _fix_mojibake(device.funding_details)

            if fixed_title and fixed_title != (device.title or ""):
                changed |= _set_if_changed(device, "title", fixed_title)
            if fixed_short and fixed_short != (device.short_description or ""):
                changed |= _set_if_changed(device, "short_description", fixed_short)
            if fixed_eligibility and fixed_eligibility != (device.eligibility_criteria or ""):
                changed |= _set_if_changed(device, "eligibility_criteria", fixed_eligibility)
            if fixed_funding and fixed_funding != (device.funding_details or ""):
                changed |= _set_if_changed(device, "funding_details", fixed_funding)

            if changed:
                updated += 1
                if len(preview) < 20:
                    preview.append(
                        {
                            "before": before,
                            "after": {
                                "title": device.title,
                                "status": device.status,
                                "type": device.device_type,
                                "validation_status": device.validation_status,
                            },
                        }
                    )

        await db.commit()

    return {"updated": updated, "preview": preview}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
