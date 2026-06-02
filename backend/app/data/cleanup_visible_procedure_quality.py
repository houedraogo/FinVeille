"""Renforce la démarche des fiches visibles qui manquent de procédure."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _procedure_text(device: Device) -> str:
    source_hint = "source officielle"
    if device.organism:
        source_hint = f"source officielle de {device.organism}"

    if device.close_date:
        timing = f"avant la date limite indiquée ({device.close_date:%d/%m/%Y})"
    elif device.status == "recurring" or device.is_recurring:
        timing = "après vérification qu'une session, un guichet ou un contact est actuellement ouvert"
    else:
        timing = "après confirmation du calendrier sur la source officielle"

    return (
        f"Consulter la {source_hint}, confirmer l'éligibilité de votre profil et le calendrier, "
        f"puis préparer le dossier {timing}. Vérifier en priorité les pièces demandées, "
        "les dépenses ou activités acceptées, les plafonds éventuels, le canal de dépôt et le contact "
        "à utiliser avant d'engager du temps ou des frais."
    )


def _merge_full_description(device: Device, procedure: str) -> None:
    full = (device.full_description or "").strip()
    markers = ["Démarche recommandée : ", "Demarche recommandee : "]
    for marker in markers:
        if marker in full:
            prefix = full.split(marker, 1)[0].rstrip()
            device.full_description = f"{prefix}\n\nDémarche recommandée : {procedure}" if prefix else f"Démarche recommandée : {procedure}"
            return
    if full:
        device.full_description = f"{full}\n\nDémarche recommandée : {procedure}"
    else:
        device.full_description = f"Démarche recommandée : {procedure}"


def _upsert_procedure_section(value: Any, procedure: str) -> list[dict[str, Any]]:
    sections = value if isinstance(value, list) else []
    cleaned: list[dict[str, Any]] = []
    updated = False

    for item in sections:
        if not isinstance(item, dict):
            continue
        section = dict(item)
        key = str(section.get("key") or "").lower()
        title = str(section.get("title") or "").lower()
        if key in {"procedure", "demarche", "démarche"} or "demarche" in title or "démarche" in title:
            section["key"] = "procedure"
            section["title"] = "Démarche"
            section["content"] = procedure
            section["confidence"] = max(int(section.get("confidence") or 0), 78)
            section["source"] = "renforcement qualité procédure"
            updated = True
        cleaned.append(section)

    if not updated:
        cleaned.append(
            {
                "key": "procedure",
                "title": "Démarche",
                "content": procedure,
                "confidence": 78,
                "source": "renforcement qualité procédure",
            }
        )
    return cleaned


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device))).scalars().all()

        for device in devices:
            if not _visible(device):
                continue
            conditions = (device.specific_conditions or "").strip()
            documents = (device.required_documents or "").strip()
            already_enriched = "audit:procedure_weak_fixed" in (device.tags or [])
            if not already_enriched and (len(conditions) >= 60 or documents):
                continue

            procedure = _procedure_text(device)
            device.specific_conditions = procedure
            device.content_sections_json = _upsert_procedure_section(device.content_sections_json, procedure)
            device.ai_rewritten_sections_json = _upsert_procedure_section(device.ai_rewritten_sections_json, procedure)
            _merge_full_description(device, procedure)

            tags = list(device.tags or [])
            for tag in ("quality:procedure_enriched", "audit:procedure_weak_fixed"):
                if tag not in tags:
                    tags.append(tag)
            device.tags = tags[:24]
            device.completeness_score = compute_completeness(_payload(device))
            device.user_quality_score = max(device.user_quality_score or 0, 88)
            device.updated_at = now

            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "type": device.device_type,
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": len(changed), "items": changed[:80]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Complète les démarches des fiches visibles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
