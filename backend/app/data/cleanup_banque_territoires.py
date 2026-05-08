import asyncio
from datetime import date
import re

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import clean_editorial_text, sanitize_text


SOURCE_NAME = "Banque des Territoires - dispositifs et appels"

NOISY_MARKERS = (
    "accueil",
    "lancer l'impression",
    "partager sur",
    "sommaire",
)


def _is_noisy_summary(text: str) -> bool:
    normalized = clean_editorial_text(text or "").lower()
    return any(marker in normalized for marker in NOISY_MARKERS)


def _extract_intro(device: Device) -> str:
    text = clean_editorial_text(device.full_description or "")
    if not text:
        return ""
    for noisy in (
        "Accueil Dispositifs nationaux",
        "Lancer l'impression",
        "Partager sur",
        "Partager cette page sur Facebook",
        "Partager cette page sur Linkedin",
        "Partager cette page sur Twitter",
        "Partager cette page sur Courriel",
        "En savoir plus",
        "Sommaire",
        "Introduction",
        "Programme",
        "Solutions",
        "Actualités",
        "Ressources",
        "Des questions?",
    ):
        text = text.replace(noisy, " ")
    text = re.sub(r"\s+", " ", text).strip()
    for marker in (
        "## Présentation",
        "## Presentation",
        "## Conditions d'attribution",
        "## Montant / avantages",
        "## Calendrier",
        "## Démarche",
        "## Demarche",
    ):
        text = text.replace(marker, "\n")
    sentences = [part.strip(" -") for part in text.split(".") if part.strip()]
    intro = ". ".join(sentences[:2]).strip()
    if intro and not intro.endswith("."):
        intro += "."
    return sanitize_text(intro)


def _build_summary(device: Device) -> str:
    title = sanitize_text(device.title or "Ce programme")
    if title.endswith("..."):
        title = title[:-3].rstrip()
    parts = [f"{title} est un programme porté par la Banque des Territoires".rstrip(".")]
    if device.close_date:
        when = device.close_date.strftime("%d/%m/%Y")
        if device.close_date < date.today():
            parts.append(f"La période connue s’est terminée le {when}")
        else:
            parts.append(f"La date limite actuellement repérée est le {when}")
    else:
        parts.append("Il s’agit d’un programme institutionnel sans fenêtre de clôture unique publiée à ce stade")
    parts.append("Les modalités opérationnelles et les conditions d’accès doivent être confirmées sur la page officielle")
    summary = ". ".join(part for part in parts if part).strip()
    if not summary.endswith("."):
        summary += "."
    return sanitize_text(summary)[:420]


def _build_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    if len(existing) >= 120:
        return existing
    title = sanitize_text(device.title or "ce programme")
    return (
        f"{title} s'adresse principalement aux collectivités territoriales, acteurs publics locaux, opérateurs territoriaux "
        "ou partenaires mobilisés dans le cadre de projets d'intérêt général. Selon le programme, des entreprises, associations, "
        "bailleurs, aménageurs ou structures d'accompagnement peuvent aussi intervenir comme partenaires. Les conditions exactes "
        "d'accès, de partenariat, de territoire cible et de sélection doivent être confirmées sur la page officielle."
    )


def _build_funding(device: Device) -> str:
    existing = clean_editorial_text(device.funding_details or "")
    if len(existing) >= 80:
        return existing
    return (
        "L'appui peut prendre la forme de financement, ingénierie, accompagnement, investissement ou mobilisation de partenaires "
        "selon le programme. Le montant précis, les enveloppes disponibles, les dépenses éligibles et les modalités d'intervention "
        "doivent être confirmés sur la source officielle de la Banque des Territoires."
    )


def _build_sections(device: Device, summary: str, eligibility: str, funding: str) -> dict[str, str]:
    if device.close_date:
        calendar = f"Date de référence indiquée par la source : {device.close_date.strftime('%d/%m/%Y')}."
    else:
        calendar = "Programme institutionnel sans fenêtre de clôture unique publiée sur la page source."
    return {
        "presentation": summary,
        "eligibilite": eligibility,
        "montant_avantages": funding,
        "calendrier": calendar,
        "demarche": (
            "Consulter la page officielle de la Banque des Territoires pour vérifier le périmètre du programme, "
            "les contacts utiles et les modalités de mobilisation."
        ),
        "points_a_verifier": (
            "Confirmer les bénéficiaires exacts, le territoire couvert, les montants mobilisables, les critères de sélection "
            "et les démarches opérationnelles avant toute décision."
        ),
    }


def _build_full_description(sections: dict[str, str]) -> str:
    return "\n\n".join(
        [
            f"## Presentation\n{sections['presentation']}",
            f"## Criteres d'eligibilite\n{sections['eligibilite']}",
            f"## Montant / avantages\n{sections['montant_avantages']}",
            f"## Calendrier\n{sections['calendrier']}",
            f"## Demarche\n{sections['demarche']}",
            f"## Points a verifier\n{sections['points_a_verifier']}",
        ]
    )


async def run() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (await db.execute(select(Device).where(Device.source_id == source.id))).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            if device.close_date and device.close_date < date.today() and device.status != "expired":
                device.status = "expired"
                device.is_recurring = False
                device.recurrence_notes = None
                changed = True

            if not device.close_date:
                if device.status != "recurring":
                    device.status = "recurring"
                    changed = True
                if not device.is_recurring:
                    device.is_recurring = True
                    changed = True
                notes = (
                    "Programme institutionnel porté par la Banque des Territoires, "
                    "sans fenêtre de clôture unique publiée sur la page source."
                )
                if device.recurrence_notes != notes:
                    device.recurrence_notes = notes
                    changed = True

            if device.device_type != "institutional_project":
                device.device_type = "institutional_project"
                changed = True

            new_summary = _build_summary(device)
            new_eligibility = _build_eligibility(device)
            new_funding = _build_funding(device)
            sections = _build_sections(device, new_summary, new_eligibility, new_funding)
            new_full = _build_full_description(sections)
            if new_summary != (device.short_description or ""):
                device.short_description = new_summary
                changed = True
            if new_eligibility != (device.eligibility_criteria or ""):
                device.eligibility_criteria = new_eligibility
                changed = True
            if new_funding != (device.funding_details or ""):
                device.funding_details = new_funding
                changed = True
            if new_full != (device.full_description or ""):
                device.full_description = new_full
                changed = True
            if device.content_sections_json != sections:
                device.content_sections_json = sections
                changed = True
            if device.ai_rewritten_sections_json != sections:
                device.ai_rewritten_sections_json = sections
                device.ai_rewrite_status = "done"
                changed = True

            payload = {
                "title": device.title,
                "organism": device.organism,
                "country": device.country,
                "device_type": device.device_type,
                "short_description": device.short_description,
                "full_description": device.full_description,
                "eligibility_criteria": device.eligibility_criteria,
                "funding_details": device.funding_details,
                "source_raw": device.source_raw,
                "close_date": device.close_date,
                "status": device.status,
                "is_recurring": device.is_recurring,
                "amount_min": device.amount_min,
                "amount_max": device.amount_max,
                "source_url": device.source_url,
                "recurrence_notes": device.recurrence_notes,
            }
            decision = gate.evaluate(payload)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True

            if (
                device.validation_status == "pending_review"
                and device.device_type == "institutional_project"
                and len(clean_editorial_text(device.short_description or "")) >= 120
                and device.status in {"recurring", "expired", "standby"}
            ):
                device.validation_status = "auto_published"
                changed = True

            if changed:
                updated += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "status": device.status,
                            "device_type": device.device_type,
                            "validation_status": device.validation_status,
                            "short_description": device.short_description,
                        }
                    )

        await db.commit()

        return {
            "source": SOURCE_NAME,
            "updated": updated,
            "preview": preview,
        }


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
