from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


ADMIN_ONLY_STATUS = "admin_only"
ADMIN_ONLY_TAGS = {
    "visibility:admin_only",
    "quality:institutional_signal",
    "not_user_actionable",
}


def _source_name(device: Device) -> str:
    return device.source.name if device.source else ""


def _is_world_bank(device: Device) -> bool:
    name = _source_name(device).lower()
    organism = (device.organism or "").lower()
    return "banque mondiale" in name or "world bank" in organism


def _is_afd_institutional(device: Device) -> bool:
    name = _source_name(device).lower()
    if "afd" not in name:
        return False
    return device.device_type == "institutional_project" or (
        device.source_url or ""
    ).startswith("https://opendata.afd.fr/")


def _mark_admin_only(device: Device, reason: str) -> bool:
    changed = False

    if device.device_type != "institutional_project":
        device.device_type = "institutional_project"
        changed = True

    if device.validation_status != ADMIN_ONLY_STATUS:
        device.validation_status = ADMIN_ONLY_STATUS
        changed = True

    current_tags = set(device.tags or [])
    next_tags = sorted(current_tags | ADMIN_ONLY_TAGS | {f"admin_only_reason:{reason}"})
    if device.tags != next_tags:
        device.tags = next_tags
        changed = True

    reasons = [
        "signal institutionnel",
        "non exposé dans le parcours utilisateur",
        "pas une opportunité de candidature directe",
    ]
    if device.ai_readiness_label != "utilisable_avec_prudence":
        device.ai_readiness_label = "utilisable_avec_prudence"
        changed = True
    if device.ai_readiness_score is None or device.ai_readiness_score > 55:
        device.ai_readiness_score = 55
        changed = True
    if device.ai_readiness_reasons != reasons:
        device.ai_readiness_reasons = reasons
        changed = True

    analysis = dict(device.decision_analysis or {})
    analysis.update(
        {
            "go_no_go": "no_go",
            "recommended_priority": "faible",
            "why_interesting": "Signal institutionnel utile pour la veille stratégique, mais ce n'est pas une opportunité de candidature directe.",
            "why_cautious": "La fiche décrit un projet ou une enveloppe institutionnelle. Elle doit rester côté admin ou veille, pas dans les recommandations utilisateur.",
            "points_to_confirm": "Rechercher un appel à projets, un appel d'offres ou un guichet opérationnel lié à ce projet avant toute action.",
            "recommended_action": "Ne pas proposer cette fiche comme opportunité utilisateur ; la conserver comme signal de veille admin.",
            "urgency_level": "faible",
            "difficulty_level": "haute",
            "effort_level": "haute",
            "eligibility_score": 0,
            "strategic_interest": 35,
            "model": "local-admin-only-institutional-cleanup-v1",
        }
    )
    if device.decision_analysis != analysis:
        device.decision_analysis = analysis
        device.decision_analyzed_at = datetime.now(timezone.utc)
        changed = True

    return changed


async def run(dry_run: bool = True) -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .join(Source, Device.source_id == Source.id)
                .where(
                    (Source.name.ilike("%Banque Mondiale%"))
                    | (Source.name.ilike("%AFD%"))
                    | (Device.organism.ilike("%World Bank%"))
                )
            )
        ).scalars().all()

        stats = {
            "dry_run": dry_run,
            "scanned": len(devices),
            "world_bank_admin_only": 0,
            "afd_admin_only": 0,
            "afd_kept_user_actionable": 0,
            "changed": 0,
        }

        for device in devices:
            if _is_world_bank(device):
                stats["world_bank_admin_only"] += 1
                if _mark_admin_only(device, "world_bank_project"):
                    stats["changed"] += 1
            elif _is_afd_institutional(device):
                stats["afd_admin_only"] += 1
                if _mark_admin_only(device, "afd_opendata_project"):
                    stats["changed"] += 1
            elif "afd" in _source_name(device).lower():
                stats["afd_kept_user_actionable"] += 1

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Marque Banque Mondiale et projets AFD institutionnels en admin_only.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements. Par defaut: dry-run.")
    args = parser.parse_args()
    print(asyncio.run(run(dry_run=not args.apply)))


if __name__ == "__main__":
    main()
