import asyncio
from datetime import date

from sqlalchemy import select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    compute_completeness,
    sanitize_text,
)


SOURCE_NAME = "AFD - concours et appels a projets"
OPENDATA_MARKER = "opendata.afd.fr/explore/dataset/les-projets-de-l-afd/"


def _country_phrase(country: str | None) -> str:
    label = clean_editorial_text(country or "")
    if not label:
        return "dans le pays cible"
    normalized = unidecode(label.lower())
    if normalized in {"madagascar"}:
        return f"à {label}"
    if normalized in {"tunisie", "guinee", "mauritanie", "ethiopie", "cote d'ivoire"}:
        return f"en {label}"
    if normalized.startswith(("a", "e", "i", "o", "u", "y")):
        return f"en {label}"
    return f"au {label}"


def _trim_sentence(text: str | None) -> str:
    value = clean_editorial_text(text or "")
    value = value.strip(" .")
    if not value:
        return ""
    if not value.endswith((".", "!", "?")):
        value += "."
    return value


def _build_project_summary(device: Device) -> str:
    intro = _trim_sentence(device.short_description or device.title)
    parts: list[str] = []
    if intro:
        parts.append(intro)
    else:
        parts.append(f"Ce projet institutionnel de l'AFD est suivi {_country_phrase(device.country)}.")

    if device.close_date:
        when = device.close_date.strftime("%d/%m/%Y")
        if device.close_date < date.today():
            parts.append(f"La période actuellement connue s'est terminée le {when}.")
        else:
            parts.append(f"La clôture opérationnelle repérée dans le flux AFD est fixée au {when}.")
    else:
        parts.append("La source ne publie pas de date de clôture exploitable à ce stade.")

    parts.append(
        "Il s'agit d'un projet institutionnel financé ou appuyé par l'AFD, et non d'un appel à candidatures classique."
    )
    summary = " ".join(part.strip() for part in parts if part).strip()
    return summary[:500]


def _build_project_eligibility(device: Device) -> str:
    base = build_contextual_eligibility(
        text=device.short_description,
        beneficiaries=device.beneficiaries,
        country=device.country,
        geographic_scope=device.geographic_scope,
    )
    extra = (
        "Cette fiche décrit surtout un projet AFD déjà cadré avec des acteurs publics, institutionnels "
        "ou des opérateurs partenaires ; les modalités d'accès direct doivent être confirmées sur la source officielle."
    )
    return f"{base} {extra}".strip()


def _build_project_funding(device: Device) -> str:
    return build_contextual_funding(
        text=device.short_description,
        device_type="pret",
        amount_min=device.amount_min,
        amount_max=device.amount_max,
        currency=device.currency,
    )


def _build_project_procedure() -> str:
    return (
        "La consultation détaillée se fait depuis la page Open Data AFD ou la page projet associée. "
        "Cette fiche sert d'abord à suivre le projet, ses objectifs et ses dates publiques de référence."
    )


def _section_content(device: Device, key: str) -> str:
    sections = device.ai_rewritten_sections_json or device.content_sections_json or {}
    key_norm = key.lower()
    if isinstance(sections, dict):
        for current_key, value in sections.items():
            if key_norm in str(current_key).lower():
                return clean_editorial_text(value)
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            current_key = str(section.get("key") or section.get("title") or "").lower()
            if key_norm in current_key:
                return clean_editorial_text(section.get("content") or "")
    return ""


def _afd_sections_payload(
    *,
    presentation: str,
    eligibility: str,
    funding: str,
    calendar: str,
    procedure: str,
    checks: str,
) -> dict[str, str]:
    return {
        "presentation": presentation,
        "eligibilite": eligibility,
        "montant_avantages": funding,
        "calendrier": calendar,
        "demarche": procedure,
        "points_a_verifier": checks,
    }


def _calendar_text(device: Device) -> str:
    if device.open_date and device.close_date:
        return (
            f"Ouverture indiquee le {device.open_date.strftime('%d/%m/%Y')} et cloture indiquee le "
            f"{device.close_date.strftime('%d/%m/%Y')}."
        )
    if device.close_date:
        return f"Date de cloture indiquee par la source : {device.close_date.strftime('%d/%m/%Y')}."
    if device.status == "recurring":
        return "Opportunite recurrente ou publiee par edition, sans date limite unique exploitable dans la fiche actuelle."
    return "Calendrier a confirmer sur la source officielle de l'AFD."


def _generic_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    if len(existing) >= 120:
        return existing
    section_value = _section_content(device, "elig")
    if len(section_value) >= 120:
        return section_value
    beneficiaries = ", ".join(device.beneficiaries or []) if isinstance(device.beneficiaries, list) else ""
    audience = f"Le dispositif vise notamment {beneficiaries}" if beneficiaries else "Le dispositif vise les porteurs eligibles presentes par l'AFD"
    country = device.country or device.geographic_scope or "la zone ciblee"
    return (
        f"{audience}, avec une intervention ou un projet en lien avec {country}. "
        "La recevabilite doit etre confirmee sur la source officielle, notamment le type de structure, "
        "la localisation, la capacite operationnelle, les partenaires attendus et les pieces de candidature."
    )


def _generic_funding(device: Device) -> str:
    existing = clean_editorial_text(device.funding_details or "")
    if len(existing) >= 80 and "non communiqué" not in existing.lower():
        return existing
    section_value = _section_content(device, "funding") or _section_content(device, "montant")
    if len(section_value) >= 80 and "non communiqué" not in section_value.lower():
        return section_value
    if device.amount_min or device.amount_max:
        return build_contextual_funding(
            text=device.short_description,
            device_type=device.device_type,
            amount_min=device.amount_min,
            amount_max=device.amount_max,
            currency=device.currency,
        )
    return (
        "Montant ou avantage financier non communique dans la fiche actuelle. "
        "Le budget disponible, les depenses eligibles, les plafonds et les modalites de versement doivent etre confirmes sur la source officielle."
    )


def _generic_summary(device: Device) -> str:
    current = clean_editorial_text(device.short_description or "")
    if len(current) >= 140:
        return current[:500]
    presentation = _section_content(device, "presentation")
    base = presentation if len(presentation) >= 80 else clean_editorial_text(device.title or "Cette opportunite AFD")
    status = _calendar_text(device)
    return f"{base.rstrip('.')} . {status}".strip()[:500]


def _build_digital_challenge_summary(device: Device) -> str:
    return (
        "AFD Digital Challenge est une opportunité récurrente portée par l'AFD pour repérer des startups innovantes "
        "ayant un impact en Afrique. La source mentionne une dotation autour de 20 000 EUR ainsi qu'un accompagnement "
        "d'environ un an pour les lauréats."
    )


def _build_digital_challenge_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    if existing:
        return (
            f"{existing}. Les critères détaillés par édition doivent être confirmés sur la page officielle de l'AFD."
        )
    return (
        "Le challenge cible des startups ayant développé des solutions innovantes pour l'Afrique, à un stade déjà amorcé. "
        "Les critères détaillés de chaque édition doivent être confirmés sur la page officielle de l'AFD."
    )


def _build_digital_challenge_funding() -> str:
    return (
        "La source mentionne une dotation indicative autour de 20 000 EUR par lauréat, complétée par un accompagnement "
        "d'environ un an. Les montants exacts et les avantages associés doivent être confirmés pour chaque édition."
    )


def _build_digital_challenge_procedure() -> str:
    return (
        "La candidature se fait lors de l'ouverture d'une nouvelle édition sur les canaux officiels de l'AFD ou de ses "
        "partenaires. Il faut donc surveiller la page source pour confirmer le calendrier de dépôt."
    )


def _is_project_row(device: Device) -> bool:
    return OPENDATA_MARKER in (device.source_url or "")


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 120
        and len(clean_editorial_text(device.full_description or "")) >= 220
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 90
        and len(clean_editorial_text(device.funding_details or "")) >= 60
        and device.status in {"open", "expired", "standby", "recurring"}
    )


async def run() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id, Device.validation_status != "rejected")
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        auto_published = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            if _is_project_row(device):
                if device.device_type != "institutional_project":
                    device.device_type = "institutional_project"
                    changed = True
                if device.is_recurring:
                    device.is_recurring = False
                    changed = True
                if device.recurrence_notes:
                    device.recurrence_notes = None
                    changed = True

                new_summary = _build_project_summary(device)
                new_eligibility = _build_project_eligibility(device)
                new_funding = _build_project_funding(device)
                new_full = build_structured_sections(
                    presentation=new_summary,
                    eligibility=new_eligibility,
                    funding=new_funding,
                    open_date=device.open_date,
                    close_date=device.close_date,
                    procedure=_build_project_procedure(),
                    recurrence_notes=None,
                )
            elif clean_editorial_text(device.title).lower() == "afd digital challenge":
                if device.device_type != "subvention":
                    device.device_type = "subvention"
                    changed = True
                if device.status != "recurring":
                    device.status = "recurring"
                    changed = True
                if not device.is_recurring:
                    device.is_recurring = True
                    changed = True
                notes = "Concours AFD récurrent selon les éditions ; la source ne publie pas ici de date limite exploitable."
                if device.recurrence_notes != notes:
                    device.recurrence_notes = notes
                    changed = True

                new_summary = _build_digital_challenge_summary(device)
                new_eligibility = _build_digital_challenge_eligibility(device)
                new_funding = _build_digital_challenge_funding()
                new_full = build_structured_sections(
                    presentation=new_summary,
                    eligibility=new_eligibility,
                    funding=new_funding,
                    open_date=device.open_date,
                    close_date=device.close_date,
                    procedure=_build_digital_challenge_procedure(),
                    recurrence_notes=device.recurrence_notes,
                )
            else:
                has_weak_fields = (
                    len(clean_editorial_text(device.eligibility_criteria or "")) < 120
                    or len(clean_editorial_text(device.funding_details or "")) < 80
                    or not device.ai_rewritten_sections_json
                )
                if not has_weak_fields:
                    continue

                new_summary = _generic_summary(device)
                new_eligibility = _generic_eligibility(device)
                new_funding = _generic_funding(device)
                new_full = build_structured_sections(
                    presentation=new_summary,
                    eligibility=new_eligibility,
                    funding=new_funding,
                    open_date=device.open_date,
                    close_date=device.close_date,
                    procedure=_build_project_procedure(),
                    recurrence_notes=device.recurrence_notes,
                )

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
            sections_payload = _afd_sections_payload(
                presentation=new_summary,
                eligibility=new_eligibility,
                funding=new_funding,
                calendar=_calendar_text(device),
                procedure=_build_project_procedure(),
                checks=(
                    "Confirmer les beneficiaires, les montants, les modalites de candidature et le calendrier sur la source officielle AFD."
                ),
            )
            if device.content_sections_json != sections_payload:
                device.content_sections_json = sections_payload
                changed = True
            if device.ai_rewritten_sections_json != sections_payload:
                device.ai_rewritten_sections_json = sections_payload
                device.ai_rewrite_status = "done"
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

            if device.validation_status == "auto_published":
                auto_published += 1

            if changed:
                updated += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "status": device.status,
                            "device_type": device.device_type,
                            "validation_status": device.validation_status,
                            "source_url": device.source_url,
                        }
                    )

        await db.commit()

        return {
            "source": SOURCE_NAME,
            "updated": updated,
            "auto_published_after_cleanup": auto_published,
            "preview": preview,
        }


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
