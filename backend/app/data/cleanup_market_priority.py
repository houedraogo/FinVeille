from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.user_quality import USER_ADMIN_ONLY, USER_REJECT, compute_user_quality
from app.utils.text_utils import clean_editorial_text, looks_english_text


TARGET_TERMS = {
    "burkina faso",
    "benin",
    "cote d'ivoire",
    "cote d ivoire",
    "afrique de l'ouest",
    "west africa",
    "uemoa",
    "cedeao",
    "ecowas",
}

ACTIONABLE_TYPES = {
    "subvention",
    "pret",
    "avance_remboursable",
    "garantie",
    "credit_impot",
    "exoneration",
    "aap",
    "appel a projets",
    "appel a projet",
    "appel_a_projets",
    "ami",
    "accompagnement",
    "concours",
    "investissement",
}

DEAD_SOURCE_MARKERS = (
    "aucun contenu exploitable trouve",
    "aucun contenu editorial exploitable",
    "javascript dynamique",
    "structure html trop pauvre",
    "token invalide ou expire",
    "impossible d'acceder a l'url",
    "url non publique",
    "page non publique",
    "404",
    "401",
    "403",
    "activation deconseillee",
)

ENGLISH_MARKERS = (
    "call for applications",
    "funding opportunity",
    "applications open",
    "opens applications",
    "grant opportunity",
    "innovation fund",
    "deadline",
    "entrepreneurs are invited",
)

INSTITUTIONAL_TITLE_MARKERS = (
    "project",
    "program",
    "programme",
    "support to",
    "additional financing",
    "emergency",
)

ACTION_MARKERS = (
    "candidature",
    "postuler",
    "postulez",
    "appel a projets",
    "appel a projet",
    "concours",
    "formulaire",
    "deposer",
    "apply",
    "applications",
    "open call",
)


def _norm(value: Any) -> str:
    text = clean_editorial_text(str(value or "")).strip().lower()
    return unidecode(text).replace("'", " ")


def _device_payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _append_tags(device: Device, *new_tags: str) -> None:
    tags = set(device.tags or [])
    tags.update(tag for tag in new_tags if tag)
    device.tags = sorted(tags)


def _is_target_market(device: Device) -> bool:
    values = [
        device.country,
        device.region,
        device.zone,
        device.geographic_scope,
        " ".join(device.keywords or []),
        " ".join(device.tags or []),
    ]
    normalized = " ".join(_norm(value) for value in values if value)
    return any(_norm(term) in normalized for term in TARGET_TERMS)


def _source_blob(device: Device) -> str:
    return _norm(
        " ".join(
            [
                device.title or "",
                device.short_description or "",
                device.full_description or "",
                device.eligibility_criteria or "",
                device.funding_details or "",
                device.source_raw or "",
            ]
        )
    )


def _has_rewritten_french_public_text(device: Device) -> bool:
    sections = device.ai_rewritten_sections_json
    if not isinstance(sections, list) or not sections:
        return False
    content = " ".join(str(section.get("content") or "") for section in sections if isinstance(section, dict))
    normalized = _norm(content)
    return len(normalized) >= 300 and any(word in normalized for word in ("pour qui", "candidater", "date limite", "montant", "verifier"))


def _has_english_public_text(device: Device, quality_reasons: list[str]) -> bool:
    if _has_rewritten_french_public_text(device):
        return False
    title = device.title or ""
    summary = device.short_description or device.auto_summary or ""
    normalized = _norm(" ".join([title, summary]))
    return looks_english_text(title) or "anglais_a_traduire" in quality_reasons or any(marker in normalized for marker in ENGLISH_MARKERS)


def _has_dead_source(device: Device, source: Source | None) -> bool:
    tags = set(device.tags or [])
    if any(tag in tags for tag in ("quality:source_dead", "quality:source_404", "quality:source_401", "quality:source_403")):
        return True
    if not device.source_url or not str(device.source_url).startswith(("http://", "https://")):
        return True
    if any(marker in str(device.source_url).lower() for marker in ("localhost", "google.com/search", "file://")):
        return True
    if any(marker in _source_blob(device) for marker in DEAD_SOURCE_MARKERS):
        return True
    if source and (not source.is_active or (source.consecutive_errors or 0) >= 3):
        return True
    return False


def _launch_market_hide_reason(device: Device, source: Source | None) -> str | None:
    source_name = _norm(source.name if source else device.organism)
    organism = _norm(device.organism)
    device_type = _norm(device.device_type)
    status = _norm(device.status)
    blob = _source_blob(device)

    quality = compute_user_quality(_device_payload(device))
    if quality.decision == USER_REJECT:
        return "quality_reject"
    if _has_dead_source(device, source):
        return "unreliable_or_dead_source"
    if status in {"expired", "closed"}:
        return "expired_or_closed"
    if _has_english_public_text(device, quality.reasons or []):
        return "english_title_or_content"
    if device_type in {"autre", "institutional_project"}:
        return "institutional_or_unqualified_type"
    if "world bank" in source_name or "world bank" in organism or "banque mondiale" in organism:
        is_project_signal = any(marker in _norm(device.title) for marker in INSTITUTIONAL_TITLE_MARKERS)
        has_action_signal = any(_norm(marker) in blob for marker in ACTION_MARKERS)
        if is_project_signal and not has_action_signal:
            return "world_bank_non_candidatable"
        if device_type not in ACTIONABLE_TYPES or "action_non_claire" in quality.reasons:
            return "world_bank_non_candidatable"
    if device_type not in ACTIONABLE_TYPES:
        return "not_actionable_for_launch_market"
    if quality.decision == USER_ADMIN_ONLY:
        return "not_actionable_for_launch_market"
    return None


def _visible_now(device: Device) -> bool:
    return (
        device.validation_status in {"auto_published", "approved", "validated"}
        and device.user_quality_decision not in {USER_ADMIN_ONLY, USER_REJECT}
    )


def _apply_visibility_decision(device: Device, reason: str) -> str:
    reject = reason in {"quality_reject", "unreliable_or_dead_source"}
    device.validation_status = "rejected" if reject else "admin_only"
    device.user_quality_decision = USER_REJECT if reject else USER_ADMIN_ONLY
    device.user_quality_score = 0 if reject else min(device.user_quality_score or 55, 55)

    reasons = set(device.user_quality_reasons or [])
    reasons.add(reason)
    device.user_quality_reasons = sorted(reasons)
    _append_tags(
        device,
        "visibility:rejected" if reject else "visibility:admin_only",
        f"launch_market:{reason}",
    )

    analysis = dict(device.decision_analysis or {})
    analysis["launch_market_visibility"] = "rejected" if reject else "admin_only"
    analysis["launch_market_reason"] = reason
    analysis["launch_market_checked_at"] = datetime.now(timezone.utc).isoformat()
    device.decision_analysis = analysis
    device.updated_at = datetime.now(timezone.utc)
    return "rejected" if reject else "admin_only"


async def run(*, apply: bool = False) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "dry_run": not apply,
        "scanned_target_market": 0,
        "visible_before": 0,
        "visible_would_hide": 0,
        "would_hide": 0,
        "hidden_admin_only": 0,
        "rejected": 0,
        "restored": 0,
        "visible_after_estimate": 0,
        "by_reason": Counter(),
        "by_country": Counter(),
        "by_source": Counter(),
        "samples": [],
    }

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Device, Source)
                .outerjoin(Source, Source.id == Device.source_id)
                .where(Device.validation_status != "rejected")
            )
        ).all()

        for device, source in rows:
            if not _is_target_market(device):
                continue

            stats["scanned_target_market"] += 1
            if _visible_now(device):
                stats["visible_before"] += 1
                visible_now = True
            else:
                visible_now = False

            reason = _launch_market_hide_reason(device, source)
            if (
                apply
                and not reason
                and device.validation_status == "admin_only"
                and "launch_market:not_actionable_for_launch_market" in set(device.tags or [])
            ):
                quality = compute_user_quality(_device_payload(device))
                if quality.decision not in {USER_ADMIN_ONLY, USER_REJECT}:
                    device.validation_status = "auto_published"
                    device.user_quality_decision = quality.decision
                    device.user_quality_score = quality.score
                    device.user_quality_reasons = quality.reasons
                    tags = set(device.tags or [])
                    tags.discard("visibility:admin_only")
                    tags.discard("launch_market:not_actionable_for_launch_market")
                    tags.add("visibility:restored_for_launch_market")
                    device.tags = sorted(tags)
                    analysis = dict(device.decision_analysis or {})
                    analysis["launch_market_visibility"] = "restored"
                    analysis["launch_market_reason"] = "actionable_type_variant"
                    analysis["launch_market_checked_at"] = datetime.now(timezone.utc).isoformat()
                    device.decision_analysis = analysis
                    device.updated_at = datetime.now(timezone.utc)
                    stats["restored"] += 1
            if not reason:
                continue

            stats["would_hide"] += 1
            if visible_now:
                stats["visible_would_hide"] += 1
            stats["by_reason"][reason] += 1
            stats["by_country"][device.country or "Non renseigne"] += 1
            stats["by_source"][source.name if source else device.organism or "Sans source"] += 1
            if len(stats["samples"]) < 15:
                stats["samples"].append(
                    {
                        "title": device.title,
                        "country": device.country,
                        "source": source.name if source else device.organism,
                        "type": device.device_type,
                        "status": device.status,
                        "reason": reason,
                    }
                )

            if apply and device.validation_status not in {"admin_only", "rejected"}:
                outcome = _apply_visibility_decision(device, reason)
                if outcome == "rejected":
                    stats["rejected"] += 1
                else:
                    stats["hidden_admin_only"] += 1

        if apply:
            await db.commit()
        else:
            await db.rollback()

    stats["visible_after_estimate"] = max(0, stats["visible_before"] - stats["visible_would_hide"])
    stats["by_reason"] = dict(stats["by_reason"])
    stats["by_country"] = dict(stats["by_country"])
    stats["by_source"] = dict(stats["by_source"].most_common(20))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les fiches prioritaires du marche Afrique de l'Ouest.")
    parser.add_argument("--apply", action="store_true", help="Applique les decisions au lieu de faire un audit.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
