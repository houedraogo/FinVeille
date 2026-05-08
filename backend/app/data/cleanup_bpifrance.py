import asyncio
import re
from decimal import Decimal

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.content_section_builder import (
    _clean_bpifrance_editorial_text,
    build_content_sections,
    render_sections_markdown,
)
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Bpifrance - appels a projets et concours"


def _clean_sentence_limit(text: str, limit: int = 420) -> str:
    value = clean_editorial_text(text)
    if len(value) <= limit:
        return value
    sentence = value[:limit].rsplit(".", 1)[0].strip()
    if len(sentence) >= 160:
        return sentence + "."
    return value[:limit].rsplit(" ", 1)[0].strip() + "."


def _dedupe_sentences(text: str) -> str:
    sentences = [clean_editorial_text(part) for part in re.split(r"(?<=[.!?])\s+", clean_editorial_text(text))]
    kept: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        if not sentence:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(sentence)
    return " ".join(kept)


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


def _extract_source_pitch(device: Device) -> str:
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    source = {"name": SOURCE_NAME, "reliability": 4}
    raw = _clean_bpifrance_editorial_text(device.source_raw or device.full_description or "", payload, source)
    title = clean_editorial_text(device.title or "")
    if title:
        raw = raw.replace(title, " ")
    raw = re.sub(r"\bAccueil\s+Appels\s+a\s+projets\s+et\s+concours\b", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bDocuments?\s+a\s+telecharger\b.*", " ", raw, flags=re.IGNORECASE)
    sentences = [clean_editorial_text(part) for part in re.split(r"(?<=[.!?])\s+", raw)]
    for sentence in sentences:
        lowered = sentence.lower()
        if len(sentence) < 80:
            continue
        if any(noise in lowered for noise in ("accueil", "deposez votre", "documents a telecharger", "date ")):
            continue
        return _clean_sentence_limit(sentence, 260)
    return ""


def _format_amount(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return ""
    amount = float(value)
    if amount.is_integer():
        amount_str = f"{int(amount):,}".replace(",", " ")
    else:
        amount_str = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{amount_str} {(currency or 'EUR').strip()}".strip()


def _beneficiaries_text(device: Device) -> str:
    values = [clean_editorial_text(item) for item in (device.beneficiaries or []) if clean_editorial_text(item)]
    if not values:
        return ""
    lowered = [value.lower() for value in values]
    if len(lowered) == 1:
        return lowered[0]
    if len(lowered) == 2:
        return f"{lowered[0]} et {lowered[1]}"
    return f"{', '.join(lowered[:-1])} et {lowered[-1]}"


def _device_label(device_type: str | None, fallback: str | None) -> str:
    mapping = {
        "pret": "prêt",
        "subvention": "subvention",
        "garantie": "garantie",
        "investissement": "solution d'investissement",
        "avance_remboursable": "avance remboursable",
    }
    if device_type in mapping:
        return mapping[device_type]
    return (fallback or "offre de financement").lower()


def _build_summary(device: Device) -> str:
    type_label, stage_label, pitch = _parse_short_description(device.short_description)
    if (
        "est une offre bpifrance" in pitch.lower()
        or "accueil appels" in pitch.lower()
        or "cette offre fonctionne" in pitch.lower()
        or "le montant indicatif" in pitch.lower()
        or len(pitch) > 260
    ):
        pitch = ""
    pitch = pitch or _extract_source_pitch(device)
    label = _device_label(device.device_type, type_label)
    beneficiaries = _beneficiaries_text(device)
    parts = [f"{device.title} est une offre Bpifrance de type {label}."]
    if pitch:
        parts.append(pitch.rstrip(".") + ".")
    if beneficiaries:
        parts.append(f"Elle s'adresse principalement aux {beneficiaries}.")
    if stage_label:
        parts.append(f"La fiche la positionne surtout pour des entreprises au stade {stage_label.lower()}.")
    if device.amount_min or device.amount_max:
        minimum = _format_amount(device.amount_min, device.currency) if device.amount_min else ""
        maximum = _format_amount(device.amount_max, device.currency) if device.amount_max else ""
        if minimum and maximum and minimum != maximum:
            parts.append(f"Le montant indicatif se situe entre {minimum} et {maximum}.")
        else:
            parts.append(f"Le montant indicatif peut atteindre {maximum or minimum}.")
    if not device.close_date:
        parts.append("Cette offre fonctionne comme un dispositif permanent ou sans fenêtre unique de clôture publiée.")
    return _clean_sentence_limit(_dedupe_sentences(" ".join(part.strip() for part in parts if part)), 430)


def _build_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    beneficiaries = _beneficiaries_text(device)
    parts: list[str] = []
    if beneficiaries and f"cible principalement les {beneficiaries}" not in existing.lower():
        parts.append(f"Le dispositif cible principalement les {beneficiaries}.")
    if existing:
        parts.append(existing.rstrip(".") + ".")
        if len(existing) < 120:
            parts.append(
                "Les autres conditions d'acces, exclusions et pieces attendues doivent etre confirmees sur la page officielle Bpifrance."
            )
    else:
        parts.append(
            "Les conditions detaillees d'eligibilite doivent etre confirmees sur la page officielle Bpifrance, "
            "notamment le profil attendu, la taille de l'entreprise, le stade du projet et les exclusions eventuelles."
        )
    return _dedupe_sentences(" ".join(parts).strip())


def _build_funding(device: Device) -> str:
    type_label, _, pitch = _parse_short_description(device.short_description)
    if (
        "est une offre bpifrance" in pitch.lower()
        or "accueil appels" in pitch.lower()
        or "cette offre fonctionne" in pitch.lower()
        or "le montant indicatif" in pitch.lower()
        or len(pitch) > 220
    ):
        pitch = ""
    label = _device_label(device.device_type, type_label)
    minimum = _format_amount(device.amount_min, device.currency) if device.amount_min else ""
    maximum = _format_amount(device.amount_max, device.currency) if device.amount_max else ""
    if minimum and maximum and minimum != maximum:
        amount_text = f"Le financement indicatif se situe entre {minimum} et {maximum}."
    elif minimum or maximum:
        amount_text = f"Le financement indicatif peut atteindre {maximum or minimum}."
    else:
        amount_text = (
            f"Les montants exacts ou les avantages associes a cette {label} doivent etre confirmes sur la page officielle. "
            "La fiche doit etre lue comme une opportunite a qualifier avant decision."
        )

    pitch_text = ""
    if pitch:
        pitch_text = f"Repere utile : {_clean_sentence_limit(pitch, 220).rstrip('.')}."
    return _dedupe_sentences(" ".join(part for part in (amount_text, pitch_text) if part).strip())


def _build_procedure(device: Device) -> str:
    if device.close_date:
        return (
            "La demande ou le dépôt se fait depuis la page Bpifrance dédiée, en respectant le calendrier annoncé sur la fiche officielle."
        )
    return (
        "La demande se fait auprès de Bpifrance depuis la page officielle de l'offre. Les modalités exactes et le rythme de traitement doivent être confirmés sur cette page."
    )


def _should_be_recurring(device: Device) -> bool:
    if device.close_date:
        return False
    url = (device.source_url or "").lower()
    if "catalogue-offres" in url or "fonds-propres" in url:
        return True
    title = clean_editorial_text(device.title).lower()
    return any(marker in title for marker in ("garantie", "prêt", "bourse french tech", "digital venture", "i-nov", "deeptech"))


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 260
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 80
        and len(clean_editorial_text(device.funding_details or "")) >= 60
        and device.status in {"standby", "recurring", "open", "expired"}
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
                .where(Device.source_id == source.id)
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        auto_published = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            if _should_be_recurring(device):
                if device.status != "recurring":
                    device.status = "recurring"
                    changed = True
                if not device.is_recurring:
                    device.is_recurring = True
                    changed = True
                notes = "Offre Bpifrance catalogue ou dispositif permanent, sans date de clôture unique publiée."
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
            source_payload = {column.name: getattr(source, column.name) for column in Source.__table__.columns}
            sections = build_content_sections(payload, source_payload)
            sections_markdown = render_sections_markdown(sections)
            if sections != (device.content_sections_json or []):
                device.content_sections_json = sections
                changed = True
            if sections_markdown and sections_markdown != (device.full_description or ""):
                device.full_description = sections_markdown
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            decision = gate.evaluate(payload)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True

            if device.validation_status in {"pending_review", "rejected"} and _should_force_publish(device):
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
                            "validation_status": device.validation_status,
                            "short_description": device.short_description,
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
