"""Contrôle qualité progressif des fiches publiées jamais évaluées.

L'audit a montré que ~90 % du catalogue synchronisé n'avait jamais reçu de
décision qualité (user_quality_decision NULL passe le filtre de visibilité).
Le calcul (compute_user_quality) est DÉTERMINISTE : aucun appel IA, donc
aucun coût. En revanche appliquer une décision « admin_only / reject » masque
la fiche aux utilisateurs : l'application est donc progressive (``limit`` par
passage), explicite, et ne change jamais ``validation_status`` — seuls les
champs ``user_quality_*`` sont écrits. Sans ``apply`` : rapport seul.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.user_quality import compute_user_quality

PUBLIC_VALIDATION = ("auto_published", "approved", "validated", "manually_published")


def _as_dict(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in device.__table__.columns}


async def evaluate_unrated(
    db: AsyncSession, *, limit: int = 200, apply: bool = False, offset_id: Optional[Any] = None,
) -> dict[str, Any]:
    query = (
        select(Device)
        .where(Device.user_quality_decision.is_(None), Device.validation_status.in_(PUBLIC_VALIDATION))
        .order_by(Device.id)
        .limit(limit)
    )
    if offset_id is not None:
        query = query.where(Device.id > offset_id)
    devices = (await db.execute(query)).scalars().all()
    decisions: Counter = Counter()
    reasons: Counter = Counter()
    would_hide = 0
    for device in devices:
        quality = compute_user_quality(_as_dict(device))
        decisions[quality.decision] += 1
        for reason in quality.reasons:
            reasons[reason] += 1
        if quality.decision in ("admin_only", "reject"):
            would_hide += 1
        if apply:
            device.user_quality_score = quality.score
            device.user_quality_decision = quality.decision
            device.user_quality_reasons = quality.reasons
    if apply:
        await db.commit()
    return {
        "evaluated": len(devices),
        "applied": apply,
        "decisions": dict(decisions),
        "would_hide_from_users": would_hide,
        "top_reasons": dict(reasons.most_common(8)),
        "last_id": str(devices[-1].id) if devices else None,
    }
