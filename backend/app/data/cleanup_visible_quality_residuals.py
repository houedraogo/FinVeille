"""Finish residual issues from the visible quality audit.

This script is intentionally conservative for launch readiness:
- entries still marked needs_review after AI rewriting are hidden from users;
- actionable African entries with residual English text are rewritten locally in French;
- entries with no amount are kept only with an explicit "to confirm" funding note.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.visible_quality_service import build_visible_quality_audit
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


TITLE_TRANSLATIONS = {
    "Home Grown Solutions Accelerator for Pandemic Resilience – 2026": "Accélérateur Home Grown Solutions 2026 pour la résilience sanitaire",
    "Exclusive Cloudvisor for VC4A startups": "Offre Cloudvisor pour startups accompagnées par VC4A",
}


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _country(device: Device) -> str:
    return clean_editorial_text(device.country or device.zone or "Afrique")


def _beneficiaries(device: Device) -> str:
    values = [clean_editorial_text(value) for value in (device.beneficiaries or []) if value]
    return ", ".join(values) or "startups, PME, entrepreneurs ou structures éligibles selon la source officielle"


def _funding_fallback(device: Device) -> str:
    dtype = str(device.device_type or "").lower()
    if dtype == "concours":
        return (
            "La source officielle ne précise pas encore un montant certain dans la fiche Kafundo. "
            "L’avantage peut inclure une dotation, un accompagnement, de la visibilité ou un accès à des partenaires. "
            "Le montant exact et les conditions doivent être confirmés sur la page officielle avant toute candidature."
        )
    if dtype == "accompagnement":
        return (
            "L’avantage principal est un accompagnement : expertise, mentorat, accès à un réseau, services ou appui à la croissance. "
            "Un soutien financier peut exister selon le programme, mais il doit être confirmé sur la source officielle."
        )
    return (
        "Le montant exact n’est pas communiqué de façon fiable dans la fiche actuelle. "
        "Vérifiez sur la source officielle le niveau de financement, les dépenses éligibles et les éventuelles contreparties."
    )


def _sections(device: Device) -> list[dict[str, Any]]:
    title = clean_editorial_text(device.title or "Opportunité")
    country = _country(device)
    beneficiaries = _beneficiaries(device)
    funding = clean_editorial_text(device.funding_details or _funding_fallback(device))
    close_date = device.close_date.strftime("%d/%m/%Y") if device.close_date else None
    calendar = (
        f"Date limite indiquée : {close_date}. Vérifiez la date sur la source officielle avant de préparer votre dossier."
        if close_date
        else "Aucune date limite unique n’est confirmée dans la fiche. Vérifiez la fenêtre de candidature sur la source officielle."
    )

    presentation = clean_editorial_text(
        f"{title} est une opportunité à suivre pour {country}. "
        "Elle peut aider une structure éligible à accéder à un accompagnement, un financement ou un appui opérationnel."
    )
    eligibility = clean_editorial_text(
        f"Public cible à confirmer : {beneficiaries}. "
        "Les critères précis peuvent dépendre du pays, du secteur, du stade du projet et des documents demandés."
    )
    procedure = clean_editorial_text(
        "Consultez la source officielle, vérifiez les critères et la date limite, puis préparez les informations demandées avant de candidater."
    )
    checks = clean_editorial_text(
        "Confirmez les critères d’éligibilité, le montant ou l’avantage exact, les pièces requises et la procédure officielle."
    )

    return [
        {"key": "why_this_opportunity", "title": "Pourquoi regarder cette opportunité ?", "content": presentation, "confidence": 82, "source": "quality_residual_cleanup"},
        {"key": "eligibility", "title": "Pour qui ?", "content": eligibility, "confidence": 78, "source": "quality_residual_cleanup"},
        {"key": "funding", "title": "Ce que vous pouvez obtenir", "content": funding, "confidence": 76, "source": "quality_residual_cleanup"},
        {"key": "calendar", "title": "Date limite ou disponibilité", "content": calendar, "confidence": 80, "source": "quality_residual_cleanup"},
        {"key": "procedure", "title": "Comment candidater", "content": procedure, "confidence": 76, "source": "quality_residual_cleanup"},
        {"key": "checks", "title": "Points à vérifier", "content": checks, "confidence": 72, "source": "quality_residual_cleanup"},
    ]


def _rewrite_clean(device: Device) -> None:
    if device.title in TITLE_TRANSLATIONS:
        device.title = TITLE_TRANSLATIONS[device.title]
    existing_funding = clean_editorial_text(device.funding_details or "")
    device.funding_details = existing_funding if len(existing_funding) >= 80 else _funding_fallback(device)
    sections = _sections(device)
    device.short_description = sections[0]["content"]
    device.eligibility_criteria = sections[1]["content"]
    device.full_description = build_structured_sections(
        presentation=sections[0]["content"],
        eligibility=sections[1]["content"],
        funding=sections[2]["content"],
        close_date=device.close_date,
        open_date=device.open_date,
        procedure=sections[4]["content"],
        recurrence_notes=device.recurrence_notes,
    )
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = "quality-residual-cleanup-v1"
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    device.language = "fr"
    device.completeness_score = compute_completeness(_payload(device))


def _hide(device: Device) -> None:
    device.validation_status = "admin_only"
    device.user_quality_decision = "admin_only"
    device.user_quality_score = min(device.user_quality_score or 55, 55)
    tags = set(device.tags or [])
    tags.add("visibility:admin_only")
    tags.add("quality_residual:hidden_after_needs_review")
    device.tags = sorted(tags)


async def run(*, apply: bool = False, limit: int = 80) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        audit = await build_visible_quality_audit(db, limit=limit)
        stats = {"dry_run": not apply, "scanned": audit["to_fix_total"], "cleaned": 0, "hidden": 0, "preview": []}

        for item in audit["items"]:
            row = (
                await db.execute(
                    select(Device, Source)
                    .outerjoin(Source, Source.id == Device.source_id)
                    .where(Device.id == UUID(str(item["id"])))
                )
            ).first()
            if not row:
                continue
            device, source = row
            issues = set(item.get("issues") or [])
            before = {
                "title": device.title,
                "source": source.name if source else device.organism,
                "issues": sorted(issues),
                "ai_rewrite_status": device.ai_rewrite_status,
            }

            blocking_issues = {"expired_visible", "dead_link", "no_source", "unqualified_type", "admin_only_visible"}
            if issues & blocking_issues:
                _hide(device)
                stats["hidden"] += 1
                action = "hide"
            elif device.ai_rewrite_status == "needs_review" and "missing_rewrite" in issues:
                _hide(device)
                stats["hidden"] += 1
                action = "hide"
            else:
                _rewrite_clean(device)
                stats["cleaned"] += 1
                action = "clean"

            analysis = dict(device.decision_analysis or {})
            analysis["quality_residual_cleanup"] = {
                "action": action,
                "issues": sorted(issues),
                "at": datetime.now(timezone.utc).isoformat(),
            }
            device.decision_analysis = analysis
            device.updated_at = datetime.now(timezone.utc)

            if len(stats["preview"]) < 20:
                stats["preview"].append({**before, "action": action, "after_title": device.title})

        if apply:
            await db.commit()
        else:
            await db.rollback()
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean residual visible quality issues.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
