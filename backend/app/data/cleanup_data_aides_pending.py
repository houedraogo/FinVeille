import asyncio
from datetime import date
import sys
from urllib.parse import urlparse

from sqlalchemy import select

from app.collector.normalizer import (
    DATA_AIDES_RECURRING_BLOCKERS,
    DATA_AIDES_RECURRING_HOSTS,
)
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import clean_editorial_text, sanitize_text


SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises"


def _append_once(base: str | None, addition: str) -> str:
    current = clean_editorial_text(base or "")
    marker = sanitize_text(addition).lower()
    if marker in sanitize_text(current).lower():
        return current
    if not current:
        return addition
    separator = "" if current.endswith((".", "!", "?")) else "."
    return f"{current}{separator} {addition}".strip()


def _has_close_proof(device: Device) -> bool:
    return bool(device.close_date)


def _should_be_recurring(device: Device) -> bool:
    blob = sanitize_text(
        " ".join(
            part
            for part in (
                device.title or "",
                device.short_description or "",
                device.full_description or "",
                device.eligibility_criteria or "",
                device.funding_details or "",
                device.recurrence_notes or "",
            )
            if part
        )
    ).lower()
    if device.close_date:
        return False
    if device.is_recurring or device.status == "recurring":
        return True
    recurring_markers = (
        "au fil de l'eau",
        "sans date limite",
        "date limite unique",
        "dispositif permanent",
        "mobilisable selon",
        "fonctionne sans",
        "credit-bail",
        "crédit-bail",
        "diagnostic",
        "diag ",
        "garantie",
        "pret",
        "prêt",
        "exoneration",
        "exonération",
    )
    return any(marker in blob for marker in recurring_markers)


def _explain_standby(device: Device) -> str:
    if device.close_date:
        return ""
    return (
        "Date limite non communiquee par la source publique. "
        "La fiche reste exploitable avec verification de l'ouverture effective sur la source officielle."
    )


def _normalize_status(device: Device) -> bool:
    changed = False
    today = date.today()

    if device.close_date and device.close_date < today and device.status != "expired":
        device.status = "expired"
        device.is_recurring = False
        device.recurrence_notes = None
        changed = True
    elif device.close_date and device.close_date >= today and device.status in {"standby", "unknown"}:
        device.status = "open"
        device.is_recurring = False
        changed = True
    elif _should_be_recurring(device) and device.status != "recurring":
        device.status = "recurring"
        device.is_recurring = True
        device.recurrence_notes = (
            "Dispositif permanent ou mobilisable sans fenetre de cloture unique publiee par la source."
        )
        changed = True
    elif device.status == "standby" and not _has_close_proof(device):
        note = _explain_standby(device)
        if note and note != (device.recurrence_notes or ""):
            device.recurrence_notes = note
            changed = True

    return changed


def _normalize_type(device: Device) -> bool:
    title_blob = sanitize_text(f"{device.title or ''} {device.short_description or ''} {device.funding_details or ''}").lower()
    before = device.device_type
    if device.device_type in {None, "", "autre", "concours"}:
        if "reduction d'impot" in title_blob or "réduction d'impôt" in title_blob or "credit d'impot" in title_blob or "crédit d'impôt" in title_blob:
            device.device_type = "credit_impot"
        elif "exoneration" in title_blob or "exonération" in title_blob or "cotisation" in title_blob:
            device.device_type = "exoneration"
        elif "garantie" in title_blob:
            device.device_type = "garantie"
        elif "pret" in title_blob or "prêt" in title_blob or "credit-bail" in title_blob or "crédit-bail" in title_blob:
            device.device_type = "pret"
        elif "subvention" in title_blob or "aide" in title_blob:
            device.device_type = "subvention"
    return before != device.device_type


def _strengthen_business_fields(device: Device) -> bool:
    changed = False
    eligibility = clean_editorial_text(device.eligibility_criteria or "")
    funding = clean_editorial_text(device.funding_details or "")

    if len(eligibility) < 120:
        addition = (
            "Les bénéficiaires et conditions détaillées doivent être confirmés sur la fiche officielle, "
            "notamment la taille de structure, le secteur d'activité, la localisation et les éventuelles exclusions."
        )
        device.eligibility_criteria = _append_once(eligibility, addition)
        changed = True

    funding_lower = sanitize_text(funding).lower()
    if len(funding) < 80 or (
        not device.amount_min
        and not device.amount_max
        and not any(marker in funding_lower for marker in ("eur", "euro", "€", "subvention", "pret", "prêt", "investissement", "a confirmer", "à confirmer"))
    ):
        if device.device_type == "garantie":
            addition = "L'avantage financier prend la forme d'une garantie ou d'une quotité de couverture ; le montant exact doit être confirmé sur la source officielle."
        elif device.device_type == "credit_impot":
            addition = "L'avantage financier prend la forme d'une réduction ou d'un crédit d'impôt ; l'assiette et le plafond doivent être confirmés sur la source officielle."
        elif device.device_type == "exoneration":
            addition = "L'avantage financier prend la forme d'une exonération ou réduction de charges ; le montant exact dépend de la situation de l'entreprise."
        elif device.device_type == "pret":
            addition = "Le financement prend la forme d'un prêt ou d'un crédit ; le montant, la durée et le taux doivent être confirmés sur la source officielle."
        else:
            addition = "Le montant ou l'avantage financier doit être confirmé sur la source officielle avant toute décision."
        device.funding_details = _append_once(funding, addition)
        changed = True

    return changed


async def cleanup_prudent() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                    Device.validation_status != "rejected",
                )
            )
        ).scalars().all()

        stats = {
            "scanned": len(devices),
            "updated": 0,
            "status_fixed": 0,
            "type_fixed": 0,
            "business_fields_fixed": 0,
            "ai_rewrite_reset": 0,
        }
        preview: list[dict] = []

        for device in devices:
            before = {
                "status": device.status,
                "type": device.device_type,
                "eligibility": device.eligibility_criteria,
                "funding": device.funding_details,
            }

            status_fixed = _normalize_status(device)
            type_fixed = _normalize_type(device)
            business_fixed = _strengthen_business_fields(device)

            if not (status_fixed or type_fixed or business_fixed):
                continue

            device.short_description = _build_summary(device)

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
            }
            decision = gate.evaluate(payload)
            device.validation_status = decision.validation_status

            # La fiche a change : on force une reformulation coherente au prochain backfill IA.
            device.ai_rewrite_status = "pending"
            device.ai_rewritten_sections_json = None
            device.ai_rewrite_model = None
            device.ai_rewrite_checked_at = None

            stats["updated"] += 1
            stats["status_fixed"] += int(status_fixed)
            stats["type_fixed"] += int(type_fixed)
            stats["business_fields_fixed"] += int(business_fixed)
            stats["ai_rewrite_reset"] += 1

            if len(preview) < 25:
                preview.append(
                    {
                        "title": device.title,
                        "status_before": before["status"],
                        "status_after": device.status,
                        "type_before": before["type"],
                        "type_after": device.device_type,
                        "validation_status": device.validation_status,
                    }
                )

        await db.commit()

    return {"source": SOURCE_NAME, "stats": stats, "preview": preview}


def _build_summary(device: Device) -> str:
    current = clean_editorial_text(device.short_description or "")
    parts: list[str] = []
    if current:
        parts.append(current.rstrip("."))
    else:
        parts.append(f"{sanitize_text(device.title or 'Cette opportunité')} est référencée via l’API Aides Entreprises")

    current_lower = current.lower()

    if device.status == "recurring":
        if "date limite unique" not in current_lower and "sans date limite" not in current_lower:
            parts.append("Le dispositif fonctionne sans date limite unique publiée à ce stade")
    elif device.close_date:
        when = device.close_date.strftime("%d/%m/%Y")
        if device.status == "expired" or device.close_date < date.today():
            if when not in current_lower:
                parts.append(f"La période connue s’est terminée le {when}")
        else:
            if when not in current_lower:
                parts.append(f"La date limite actuellement repérée est le {when}")
    else:
        if "date limite" not in current_lower:
            parts.append("La source publique ne communique pas encore de date limite exploitable")

    if device.device_type == "garantie":
        if "garantie" not in current_lower or "financement" not in current_lower:
            parts.append("Il s’agit d’un mécanisme de garantie destiné à faciliter le financement de l’entreprise")
    elif device.device_type == "pret":
        if "solution de financement" not in current_lower and "financement" not in current_lower:
            parts.append("Il s’agit d’une solution de financement mobilisable selon les conditions précisées par l’organisme")
    elif device.device_type == "exoneration":
        if "avantage fiscal" not in current_lower and "abattement" not in current_lower:
            parts.append("Le dispositif relève d’un avantage fiscal ou d’un abattement applicable sous conditions")
    elif device.device_type == "investissement":
        if "fonds propres" not in current_lower and "projets d’investissement" not in current_lower:
            parts.append("Le dispositif vise un appui en fonds propres ou un soutien aux projets d’investissement")

    if len(" ".join(parts)) < 135:
        if device.status == "expired":
            parts.append("La fiche reste utile pour l’historique, mais le dispositif n’est plus mobilisable dans sa version connue.")
        elif device.status == "recurring":
            parts.append("La mobilisation dépend des conditions précisées par l’organisme au moment de la demande.")
        elif device.status == "standby":
            parts.append("Il convient de vérifier les modalités exactes et l’ouverture effective directement sur la source officielle.")
        elif device.status == "open":
            parts.append("Les conditions détaillées et les modalités d’accès doivent être confirmées sur la source officielle.")

    summary = ". ".join(part for part in parts if part).strip()
    if not summary.endswith("."):
        summary += "."
    return sanitize_text(summary)[:360]


def _looks_like_recurring(device: Device) -> bool:
    if device.close_date is not None:
        return False
    host = (urlparse(device.source_url or "").netloc or "").lower()
    if host not in DATA_AIDES_RECURRING_HOSTS:
        return False

    blob = sanitize_text(
        " ".join(
            part
            for part in (
                device.title or "",
                device.short_description or "",
                device.full_description or "",
                device.source_raw or "",
            )
            if part
        )
    ).lower()
    if any(marker in blob for marker in DATA_AIDES_RECURRING_BLOCKERS):
        return False

    return any(
        marker in blob
        for marker in (
            "garantie",
            "diagnostic",
            "diag ",
            "diag-",
            "prêt",
            "pret",
            "crédit-bail",
            "credit-bail",
            "pass pi",
            "fonds direct",
        )
    )


async def run() -> dict:
    gate = DeviceQualityGate()

    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                    Device.validation_status == "pending_review",
                )
            )
        ).scalars().all()

        updated = 0
        auto_published = 0
        remained_pending = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            if device.close_date and device.close_date < date.today() and device.status in {"open", "standby"}:
                device.status = "expired"
                device.is_recurring = False
                device.recurrence_notes = None
                changed = True

            if device.status in {"open", "standby"} and _looks_like_recurring(device):
                device.status = "recurring"
                device.is_recurring = True
                device.recurrence_notes = (
                    "Classe automatiquement comme dispositif permanent : "
                    "la source publique présente une offre continue sans date limite exploitable."
                )
                changed = True

            if len(clean_editorial_text(device.short_description or "")) < 90:
                device.short_description = _build_summary(device)
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
            }
            decision = gate.evaluate(payload)

            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True

            if changed:
                updated += 1

            if device.validation_status == "auto_published":
                auto_published += 1
            else:
                remained_pending += 1

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
            "auto_published": auto_published,
            "remained_pending": remained_pending,
            "preview": preview,
        }


async def cleanup_weak_summaries() -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                )
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            current = clean_editorial_text(device.short_description or "")
            if len(current) >= 120:
                continue

            new_summary = _build_summary(device)
            if new_summary == device.short_description:
                continue

            device.short_description = new_summary
            updated += 1

            if len(preview) < 20:
                preview.append(
                    {
                        "title": device.title,
                        "status": device.status,
                        "short_description": device.short_description,
                    }
                )

        await db.commit()

        return {
            "source": SOURCE_NAME,
            "updated_weak_summaries": updated,
            "preview": preview,
        }


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if mode == "weak":
        result = asyncio.run(cleanup_weak_summaries())
    elif mode == "prudent":
        result = asyncio.run(cleanup_prudent())
    else:
        result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
