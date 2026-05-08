import argparse
import asyncio
import json
import re
from datetime import date
from urllib.parse import urlparse

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    sanitize_text,
)


SOURCE_NAME = "Import manuel / historique"


def _is_google_search(url: str | None) -> bool:
    host = (urlparse(url or "").netloc or "").lower()
    path = (urlparse(url or "").path or "").lower()
    return "google." in host and path.startswith("/search")


def _parse_inline_markers(text: str) -> dict[str, str]:
    cleaned = clean_editorial_text(text)
    markers: dict[str, str] = {}
    for chunk in cleaned.split("|"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        key_norm = sanitize_text(key).lower().strip()
        value_norm = clean_editorial_text(value).strip()
        if key_norm and value_norm:
            markers[key_norm] = value_norm
    return markers


def _stage_phrase(stage: str) -> str:
    stage_norm = sanitize_text(stage).lower()
    mapping = {
        "idee": "au stade idée",
        "idée": "au stade idée",
        "mvp": "au stade MVP",
        "amorcage": "en amorçage",
        "amorçage": "en amorçage",
        "pre-amorcage": "en pré-amorçage",
        "pré-amorçage": "en pré-amorçage",
        "early revenue": "en phase de premiers revenus",
        "croissance": "en phase de croissance",
    }
    return mapping.get(stage_norm, f"au stade {stage}")


def _status_sentence(device: Device) -> str:
    if device.close_date:
        when = device.close_date.strftime("%d/%m/%Y")
        if device.close_date < date.today() or device.status == "expired":
            return f"La période connue s'est terminée le {when}"
        return f"La date limite actuellement repérée est le {when}"
    if device.status == "recurring":
        return "Le dispositif fonctionne sans fenêtre de clôture unique publiée à ce stade"
    if device.status == "standby":
        return "La date limite doit être confirmée directement sur la source officielle"
    return ""


def _ticket_sentence(device: Device) -> str:
    funding = clean_editorial_text(device.funding_details or "")
    if funding and len(funding) >= 50 and "montant indicatif" in sanitize_text(funding).lower():
        return funding.rstrip(".")
    if device.amount_min or device.amount_max:
        generated = build_contextual_funding(
            text="",
            device_type=device.device_type,
            amount_min=device.amount_min,
            amount_max=device.amount_max,
            currency=device.currency,
        )
        return clean_editorial_text(generated).rstrip(".")
    return ""


def _investment_summary(device: Device, markers: dict[str, str]) -> str:
    stage = markers.get("stade", "")
    title = clean_editorial_text(device.title or "Ce fonds d'investissement")
    criteria = clean_editorial_text(device.eligibility_criteria or "")
    parts = [f"{title} cible des entreprises innovantes"]
    if stage:
        parts[0] += f" { _stage_phrase(stage) }"
    if criteria and len(criteria) <= 140:
        parts.append(criteria.rstrip("."))
    ticket = _ticket_sentence(device)
    if ticket:
        parts.append(ticket)
    status = _status_sentence(device)
    if status:
        parts.append(status)
    return ". ".join(part.strip().rstrip(".") for part in parts if part).strip() + "."


def _generic_summary(device: Device, markers: dict[str, str]) -> str:
    current = clean_editorial_text(device.short_description or "")
    parts: list[str] = []
    if current and not current.startswith("## "):
        parts.append(current.rstrip("."))
    else:
        parts.append(clean_editorial_text(device.title or "Cette opportunité").rstrip("."))

    stage = markers.get("stade", "")
    if stage and "stade" not in sanitize_text(current).lower():
        parts.append(f"Le dispositif vise des structures { _stage_phrase(stage) }")

    ticket = _ticket_sentence(device)
    if ticket and sanitize_text(ticket).lower() not in sanitize_text(" ".join(parts)).lower():
        parts.append(ticket)

    status = _status_sentence(device)
    if status:
        parts.append(status)

    return ". ".join(part for part in parts if part).strip() + "."


def _build_summary(device: Device) -> str:
    base_text = " ".join(
        value
        for value in (
            clean_editorial_text(device.short_description or ""),
            clean_editorial_text(device.full_description or ""),
        )
        if value
    )
    markers = _parse_inline_markers(base_text)

    if device.device_type == "investissement":
        summary = _investment_summary(device, markers)
    else:
        summary = _generic_summary(device, markers)

    if len(sanitize_text(summary)) < 120:
        additions = [
            _ticket_sentence(device),
            _status_sentence(device),
            "Les conditions exactes doivent etre confirmees sur la source officielle avant prise de contact.",
        ]
        for addition in additions:
            addition = clean_editorial_text(addition).rstrip(".")
            if addition and addition.lower() not in summary.lower():
                summary = f"{summary.rstrip('.')} . {addition}."
            if len(sanitize_text(summary)) >= 120:
                break
    return sanitize_text(summary)[:420]


def _build_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    if "## " in existing:
        existing = ""
    if len(existing) >= 120 and not existing.startswith("## ") and "## " not in existing:
        return existing
    if existing and not existing.startswith("## ") and "## " not in existing:
        beneficiaries = ", ".join(device.beneficiaries or []) if isinstance(device.beneficiaries, list) else ""
        scope = device.country or device.geographic_scope or "la zone indiquee"
        audience = f"Le dispositif cible notamment {beneficiaries}" if beneficiaries else "Le dispositif cible les structures correspondant au profil indique"
        return (
            f"{existing.rstrip('.')}. {audience}, avec un projet ou une activite sur {scope}. "
            "La recevabilite doit etre confirmee sur la source officielle, notamment le stade de maturite, "
            "le secteur, la localisation, le niveau de traction et les pieces attendues."
        )
    generated = build_contextual_eligibility(
        text=" ".join(
            part for part in (device.short_description or "", "") if part
        ),
        beneficiaries=device.beneficiaries,
        country=device.country,
        geographic_scope=device.geographic_scope,
    )
    if len(clean_editorial_text(generated)) >= 120:
        return generated
    scope = device.country or device.geographic_scope or "la zone indiquee"
    return (
        f"Les criteres detailles doivent etre confirmes sur la source officielle. "
        f"La fiche vise des porteurs ou organisations ayant un projet coherent avec {scope}, "
        "le type de financement recherche et les priorites publiees par l'organisme."
    )


def _build_funding(device: Device) -> str:
    existing = clean_editorial_text(device.funding_details or "")
    if len(existing) >= 80 and not existing.startswith("## ") and "## " not in existing:
        return existing
    return build_contextual_funding(
        text=" ".join(
            part for part in (device.short_description or "", device.full_description or "") if part
        ),
        device_type=device.device_type,
        amount_min=device.amount_min,
        amount_max=device.amount_max,
        currency=device.currency,
    )


def _sections_payload(device: Device, summary: str, eligibility: str, funding: str, procedure: str) -> dict[str, str]:
    calendar = _status_sentence(device)
    if not calendar:
        calendar = "Le calendrier doit etre confirme sur la source officielle."
    points = "Verifier les conditions d'eligibilite, le calendrier, les montants et les modalites exactes sur la source officielle."
    if _is_google_search(device.source_url):
        points = "La source actuelle renvoie vers une recherche Google : remplacer par une URL officielle avant usage commercial."
    return {
        "presentation": summary,
        "eligibilite": eligibility,
        "montant_avantages": funding,
        "calendrier": calendar,
        "demarche": procedure,
        "points_a_verifier": points,
    }


def _looks_duplicate(left: str, right: str) -> bool:
    left_norm = re.sub(r"[^a-z0-9]+", " ", sanitize_text(clean_editorial_text(left)).lower()).strip()
    right_norm = re.sub(r"[^a-z0-9]+", " ", sanitize_text(clean_editorial_text(right)).lower()).strip()
    if len(left_norm) < 120 or len(right_norm) < 120:
        return False
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    return overlap >= 0.82


def _build_procedure(device: Device) -> str:
    organism = clean_editorial_text(device.organism or "")
    if _is_google_search(device.source_url):
        return (
            "La source enregistrée renvoie actuellement vers une recherche Google : "
            "la page officielle de candidature ou d'investissement doit être confirmée avant usage."
        )
    if organism:
        return f"La prise de contact et la vérification détaillée se font auprès de {organism} via la source officielle."
    return "La prise de contact et la vérification détaillée se font via la source officielle."


def _should_force_publish(device: Device) -> bool:
    if _is_google_search(device.source_url):
        return False
    summary_ok = len(clean_editorial_text(device.short_description or "")) >= 120
    full_ok = len(clean_editorial_text(device.full_description or "")) >= 220
    business_ok = bool(device.amount_min or device.amount_max) or len(clean_editorial_text(device.eligibility_criteria or "")) >= 70
    stable_status = device.status in {"recurring", "standby", "expired"} or bool(device.close_date)
    return summary_ok and full_ok and business_ok and stable_status


async def run(apply: bool = False, limit: int | None = None) -> dict:
    gate = DeviceQualityGate()

    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        query = select(Device).where(Device.source_id == source.id).order_by(Device.validation_status.desc(), Device.title.asc())
        if limit:
            query = query.limit(limit)
        devices = (await db.execute(query)).scalars().all()

        stats = {
            "total": len(devices),
            "updated": 0,
            "auto_published": 0,
            "pending_review": 0,
            "rejected": 0,
            "rescued_from_rejected": 0,
            "google_search_left_pending": 0,
        }
        preview: list[dict] = []

        for device in devices:
            before_validation = device.validation_status
            before_summary = clean_editorial_text(device.short_description or "")
            changed = False

            if device.status == "open" and device.close_date is None:
                device.status = "standby"
                changed = True
            if device.status == "standby" and not device.close_date:
                note = "Date limite non communiquee par la source officielle ou a confirmer avant candidature."
                if device.recurrence_notes != note:
                    device.recurrence_notes = note
                    changed = True

            summary = _build_summary(device)
            eligibility = _build_eligibility(device)
            funding = _build_funding(device)
            if _looks_duplicate(eligibility, funding):
                if device.device_type == "investissement":
                    funding = (
                        "Intervention en investissement, fonds propres ou accompagnement financier a confirmer sur la source officielle. "
                        "Le ticket, le niveau de dilution, le stade vise et les conditions d'entree doivent etre verifies avant prise de contact."
                    )
                elif device.device_type == "garantie":
                    funding = (
                        "Garantie ou couverture de risque a confirmer sur la source officielle. "
                        "Le plafond, la quotite garantie et les conditions d'acces doivent etre verifies avant mobilisation."
                    )
                elif device.device_type == "pret":
                    funding = (
                        "Financement sous forme de pret ou avance a confirmer sur la source officielle. "
                        "Le montant, la duree, les garanties et les conditions de remboursement doivent etre verifies."
                    )
                else:
                    funding = (
                        "Financement, dotation ou avantage a confirmer sur la source officielle. "
                        "Le montant, les depenses eligibles, le calendrier et les justificatifs attendus doivent etre verifies."
                    )
                changed = True
            procedure = _build_procedure(device)
            full_description = build_structured_sections(
                presentation=summary,
                eligibility=eligibility,
                funding=funding,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=procedure,
                recurrence_notes=device.recurrence_notes,
            )
            sections_payload = _sections_payload(device, summary, eligibility, funding, procedure)

            if summary != (device.short_description or ""):
                device.short_description = summary
                changed = True
            if eligibility and eligibility != (device.eligibility_criteria or ""):
                device.eligibility_criteria = eligibility
                changed = True
            if funding and funding != (device.funding_details or ""):
                device.funding_details = funding
                changed = True
            if full_description and full_description != (device.full_description or ""):
                device.full_description = full_description
                changed = True
            if device.content_sections_json != sections_payload:
                device.content_sections_json = sections_payload
                changed = True
            if device.ai_rewritten_sections_json != sections_payload:
                device.ai_rewritten_sections_json = sections_payload
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

            if _is_google_search(device.source_url):
                if device.validation_status != "pending_review":
                    device.validation_status = "pending_review"
                    changed = True
                stats["google_search_left_pending"] += 1
            elif _should_force_publish(device):
                if device.validation_status != "auto_published":
                    device.validation_status = "auto_published"
                    changed = True

            if changed:
                stats["updated"] += 1
                if before_validation == "rejected" and device.validation_status != "rejected":
                    stats["rescued_from_rejected"] += 1
                if len(preview) < 20:
                    preview.append(
                        {
                            "title": device.title,
                            "device_type": device.device_type,
                            "before_validation": before_validation,
                            "after_validation": device.validation_status,
                            "before": before_summary[:140],
                            "after": clean_editorial_text(device.short_description or "")[:220],
                            "source_url": device.source_url,
                        }
                    )

            stats[device.validation_status] = stats.get(device.validation_status, 0) + 1

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "source": SOURCE_NAME, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie la source Import manuel / historique.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
