from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_decision_quality import _issues_for
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import clean_editorial_text


VC4A_SOURCE = "VC4A - startup programs and opportunities"
LOCAL_MODEL = "local-quality-residual-cleanup-v1"


def _section(key: str, title: str, content: str, confidence: int = 80) -> dict:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": "quality_residual_cleanup",
    }


def _build_vc4a_sections(device: Device) -> list[dict]:
    deadline = (
        f"La date limite identifiée est le {device.close_date.strftime('%d/%m/%Y')}."
        if device.close_date
        else "La source ne publie pas de date limite exploitable à ce stade."
    )
    type_label = {
        "subvention": "financement ou dotation",
        "concours": "concours ou challenge",
        "accompagnement": "programme d'accompagnement",
    }.get(device.device_type or "", "opportunité")
    amount = (
        f"Le montant maximal repéré est de {device.amount_max} {device.currency or ''}."
        if device.amount_max
        else "Le montant exact ou les avantages associés doivent être confirmés sur la page officielle."
    )
    return [
        _section(
            "presentation",
            "Présentation",
            (
                f"{device.title} est un {type_label} repéré via VC4A. "
                f"{clean_editorial_text(device.short_description or '')}"
            ),
            85,
        ),
        _section(
            "eligibility",
            "Critères d'éligibilité",
            clean_editorial_text(
                device.eligibility_criteria
                or "L'opportunité s'adresse principalement à des startups, entrepreneurs ou porteurs de projets correspondant au thème du programme."
            ),
            75,
        ),
        _section(
            "funding",
            "Montant / avantages",
            clean_editorial_text(device.funding_details or amount),
            75,
        ),
        _section(
            "calendar",
            "Calendrier",
            deadline,
            90 if device.close_date else 70,
        ),
        _section(
            "procedure",
            "Démarche",
            "Ouvrir la page officielle, vérifier les critères et déposer la candidature via VC4A ou le site partenaire indiqué.",
            75,
        ),
    ]


def _compact_long_description(device: Device, max_len: int = 5600) -> bool:
    text = clean_editorial_text(device.full_description or "")
    if len(text) <= max_len:
        return False

    sections = device.ai_rewritten_sections_json or device.content_sections_json
    if isinstance(sections, list) and sections:
        compact = "\n\n".join(
            f"## {clean_editorial_text(str(section.get('title') or section.get('key') or 'Section'))}\n"
            f"{clean_editorial_text(str(section.get('content') or ''))}"
            for section in sections
            if clean_editorial_text(str(section.get("content") or ""))
        )
        if compact and len(compact) < len(text):
            device.full_description = compact[:max_len].rsplit(" ", 1)[0].rstrip() + "."
            return True

    device.full_description = text[:max_len].rsplit(" ", 1)[0].rstrip() + "."
    return True


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
            )
        ).scalars().all()

        stats = {
            "vc4a_rewrites_added": 0,
            "long_descriptions_compacted": 0,
            "scanned": len(devices),
        }
        preview: list[dict] = []

        for device in devices:
            source_name = device.source.name if device.source else ""
            issues = _issues_for(device)
            changed = False

            if "reformulation_ia_absente" in issues and source_name == VC4A_SOURCE:
                sections = _build_vc4a_sections(device)
                device.ai_rewritten_sections_json = sections
                device.ai_rewrite_status = "done"
                device.ai_rewrite_model = LOCAL_MODEL
                device.ai_rewrite_checked_at = datetime.now(timezone.utc)
                stats["vc4a_rewrites_added"] += 1
                changed = True

            if "texte_trop_long" in issues and _compact_long_description(device):
                stats["long_descriptions_compacted"] += 1
                changed = True

            if changed and len(preview) < 12:
                preview.append(
                    {
                        "title": device.title,
                        "source": source_name,
                        "issues_before": issues,
                    }
                )

        await db.commit()
        stats["preview"] = preview
        return stats


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
