from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from unidecode import unidecode

from app.models.device import Device
from app.models.source import Source
from app.services.user_quality import USER_ADMIN_ONLY, USER_REJECT, compute_user_quality
from app.utils.text_utils import clean_editorial_text, looks_english_text


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
PUBLIC_USER_QUALITY_DECISIONS = {"publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
DEAD_URL_MARKERS = ("localhost", "127.0.0.1", "file://", "google.com/search")


@dataclass(frozen=True)
class VisibleQualityIssue:
    code: str
    label: str
    severity: str
    action: str


ISSUE_META: dict[str, VisibleQualityIssue] = {
    "dead_link": VisibleQualityIssue("dead_link", "Lien officiel à corriger", "high", "masquer"),
    "english_title": VisibleQualityIssue("english_title", "Titre anglais visible", "medium", "reformuler"),
    "english_text": VisibleQualityIssue("english_text", "Texte anglais visible", "medium", "reformuler"),
    "missing_procedure": VisibleQualityIssue("missing_procedure", "Démarche absente", "medium", "reformuler"),
    "missing_rewrite": VisibleQualityIssue("missing_rewrite", "Reformulation IA absente", "medium", "reformuler"),
    "weak_summary": VisibleQualityIssue("weak_summary", "Résumé trop faible", "medium", "reformuler"),
    "missing_target": VisibleQualityIssue("missing_target", "Public cible flou", "medium", "reformuler"),
    "missing_funding": VisibleQualityIssue("missing_funding", "Montant ou avantage flou", "low", "reformuler"),
    "expired_visible": VisibleQualityIssue("expired_visible", "Date passée encore visible", "high", "masquer"),
    "unqualified_type": VisibleQualityIssue("unqualified_type", "Type non publiable", "high", "masquer"),
    "admin_only_visible": VisibleQualityIssue("admin_only_visible", "Fiche admin exposée", "high", "masquer"),
    "no_source": VisibleQualityIssue("no_source", "Source officielle absente", "high", "masquer"),
}


def _norm(value: Any) -> str:
    return unidecode(clean_editorial_text(str(value or "")).lower())


def _text(value: Any) -> str:
    return clean_editorial_text(str(value or ""))


def _sections_text(sections: Any) -> str:
    if not isinstance(sections, list):
        return ""
    parts = []
    for section in sections:
        if isinstance(section, dict):
            parts.append(str(section.get("title") or ""))
            parts.append(str(section.get("content") or ""))
    return clean_editorial_text(" ".join(parts))


def _has_public_url(device: Device) -> bool:
    url = str(device.source_url or "").strip().lower()
    return url.startswith(("http://", "https://")) and not any(marker in url for marker in DEAD_URL_MARKERS)


def _looks_like_dead_link(device: Device, source: Source | None) -> bool:
    blob = _norm(" ".join([device.source_url or "", device.source_raw or "", device.short_description or "", device.full_description or ""]))
    if not _has_public_url(device):
        return True
    if any(marker in blob for marker in ("404", "401", "403", "url non publique", "impossible d'acceder", "token invalide")):
        return True
    return bool(source and (source.consecutive_errors or 0) >= 3)


def _has_procedure(device: Device) -> bool:
    blob = _norm(
        " ".join(
            [
                device.specific_conditions or "",
                device.required_documents or "",
                device.full_description or "",
                _sections_text(device.content_sections_json),
                _sections_text(device.ai_rewritten_sections_json),
            ]
        )
    )
    markers = ("comment candidater", "demarche", "postuler", "candidature", "formulaire", "deposer", "source officielle", "contact")
    return any(marker in blob for marker in markers)


def _has_rewrite(device: Device) -> bool:
    return device.ai_rewrite_status == "done" and bool(device.ai_rewritten_sections_json)


def _visible_filter():
    return and_(
        Device.validation_status.in_(list(PUBLIC_VALIDATION_STATUSES)),
        Device.status.in_(list(ACTIONABLE_STATUSES)),
        Device.device_type.notin_(list(NON_ACTIONABLE_TYPES)),
    )


def issues_for_visible_device(device: Device, source: Source | None = None) -> list[str]:
    issues: list[str] = []
    today = date.today()
    combined_text = " ".join(
        [
            device.title or "",
            device.short_description or "",
            device.full_description or "",
            device.eligibility_criteria or "",
            device.funding_details or "",
            _sections_text(device.ai_rewritten_sections_json),
        ]
    )

    if device.validation_status == "admin_only" or device.user_quality_decision in {USER_ADMIN_ONLY, USER_REJECT}:
        issues.append("admin_only_visible")
    if device.device_type in NON_ACTIONABLE_TYPES:
        issues.append("unqualified_type")
    if not _has_public_url(device):
        issues.append("no_source")
    elif _looks_like_dead_link(device, source):
        issues.append("dead_link")
    if device.close_date and device.close_date < today and device.status in {"open", "standby", "recurring"}:
        issues.append("expired_visible")
    if looks_english_text(device.title or ""):
        issues.append("english_title")
    if looks_english_text(combined_text):
        issues.append("english_text")
    if not _has_rewrite(device):
        issues.append("missing_rewrite")
    if len(_text(device.short_description or device.auto_summary)) < 100:
        issues.append("weak_summary")
    if not device.beneficiaries and len(_text(device.eligibility_criteria)) < 100:
        issues.append("missing_target")
    if not device.amount_min and not device.amount_max and len(_text(device.funding_details)) < 80:
        issues.append("missing_funding")
    if not _has_procedure(device):
        issues.append("missing_procedure")

    return list(dict.fromkeys(issues))


def _quality_action(issues: list[str]) -> str:
    if any(issue in issues for issue in ("dead_link", "no_source", "expired_visible", "unqualified_type", "admin_only_visible")):
        return "masquer"
    if any(issue in issues for issue in ("english_title", "english_text", "missing_procedure", "missing_rewrite", "weak_summary", "missing_target", "missing_funding")):
        return "reformuler"
    return "ok"


def _payload(device: Device, source: Source | None, issues: list[str]) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "title": device.title,
        "organism": device.organism,
        "country": device.country,
        "type": device.device_type,
        "status": device.status,
        "close_date": device.close_date.isoformat() if device.close_date else None,
        "source_name": source.name if source else device.organism,
        "source_url": device.source_url,
        "validation_status": device.validation_status,
        "user_quality_score": device.user_quality_score or 0,
        "user_quality_decision": device.user_quality_decision,
        "ai_rewrite_status": device.ai_rewrite_status,
        "issues": issues,
        "issue_labels": [ISSUE_META[issue].label for issue in issues if issue in ISSUE_META],
        "recommended_action": _quality_action(issues),
        "updated_at": device.updated_at.isoformat() if device.updated_at else None,
    }


async def build_visible_quality_audit(db: AsyncSession, *, limit: int = 80) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .where(_visible_filter())
            .order_by(Device.updated_at.desc().nullslast())
        )
    ).all()

    issue_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []

    for device, source in rows:
        issues = issues_for_visible_device(device, source)
        if not issues:
            continue
        issue_counts.update(issues)
        action = _quality_action(issues)
        action_counts[action] += 1
        source_counts[source.name if source else device.organism or "Sans source"] += 1
        if len(items) < limit:
            items.append(_payload(device, source, issues))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "visible_total": len(rows),
        "to_fix_total": sum(action_counts.values()),
        "issue_counts": dict(issue_counts),
        "action_counts": dict(action_counts),
        "top_sources": dict(source_counts.most_common(15)),
        "items": items,
        "issue_labels": {key: meta.label for key, meta in ISSUE_META.items()},
    }


async def apply_quality_action(db: AsyncSession, device_id: UUID, action: str) -> dict[str, Any]:
    row = (
        await db.execute(
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .where(Device.id == device_id)
        )
    ).first()
    if not row:
        raise ValueError("Fiche introuvable")
    device, source = row

    if action == "publish":
        quality = compute_user_quality({column.name: getattr(device, column.name) for column in Device.__table__.columns})
        device.validation_status = "auto_published"
        device.user_quality_score = quality.score
        device.user_quality_decision = quality.decision
        device.user_quality_reasons = quality.reasons
        tags = set(device.tags or [])
        tags.discard("visibility:admin_only")
        tags.discard("visibility:rejected")
        tags.add("visibility:published_by_quality_action")
        device.tags = sorted(tags)
    elif action == "hide":
        device.validation_status = "admin_only"
        device.user_quality_decision = USER_ADMIN_ONLY
        device.user_quality_score = min(device.user_quality_score or 55, 55)
        tags = set(device.tags or [])
        tags.add("visibility:admin_only")
        tags.add("quality_action:hidden")
        device.tags = sorted(tags)
    elif action == "delete":
        device.validation_status = "rejected"
        device.user_quality_decision = USER_REJECT
        device.user_quality_score = 0
        tags = set(device.tags or [])
        tags.add("visibility:rejected")
        tags.add("quality_action:rejected")
        device.tags = sorted(tags)
    elif action == "rewrite":
        device.ai_rewrite_status = "pending"
        tags = set(device.tags or [])
        tags.add("quality_action:rewrite_requested")
        device.tags = sorted(tags)
    else:
        raise ValueError("Action inconnue")

    analysis = dict(device.decision_analysis or {})
    analysis["quality_action"] = action
    analysis["quality_action_at"] = datetime.now(timezone.utc).isoformat()
    device.decision_analysis = analysis
    device.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device)

    issues = issues_for_visible_device(device, source)
    return {
        "device": _payload(device, source, issues),
        "message": {
            "publish": "Fiche publiée côté utilisateur.",
            "hide": "Fiche masquée côté utilisateur.",
            "delete": "Fiche rejetée et retirée du catalogue utilisateur.",
            "rewrite": "Fiche ajoutée à la file de reformulation IA.",
        }[action],
    }
