"""Quand une fiche a-t-elle le droit de consommer de l'IA ?

Constat de l'audit (octobre 2026) : 1 208 fiches rejetées ou « admin
uniquement » avaient déjà été réécrites par l'IA, 1 138 analysées, et
1 030 réécritures attendaient encore pour des fiches archivables — soit des
dépenses sans aucune valeur pour l'utilisateur final.

Règle : aucune réécriture/analyse automatique pour une fiche rejetée,
archivée, « admin uniquement », en attente de revue ou explicitement
suspendue (ai_rewrite_status = 'on_hold'). Une action manuelle explicite
d'un administrateur reste possible (``force=True`` côté appelant).
"""
from __future__ import annotations

from typing import Mapping, Optional

from sqlalchemy import and_, or_

from app.models.catalog_cleanup import AI_HELD_STATUS, ARCHIVED_STATUS
from app.models.device import Device

# Statuts de validation pour lesquels aucun traitement IA automatique n'est autorisé.
HELD_VALIDATION_STATUSES = frozenset({ARCHIVED_STATUS, "rejected", "admin_only", "pending_review"})


def ai_hold_reason(device: Mapping[str, object]) -> Optional[str]:
    """Motif de suspension IA pour une fiche (dict), ou None si elle est éligible."""
    if str(device.get("ai_rewrite_status") or "") == AI_HELD_STATUS:
        return "ai_on_hold"
    validation = str(device.get("validation_status") or "")
    if validation in HELD_VALIDATION_STATUSES:
        return f"validation_{validation}"
    return None


def initial_ai_rewrite_status(validation_status: Optional[str], *, out_of_scope: bool = False) -> str:
    """Statut IA à la création : une fiche non publiable n'entre pas dans la file."""
    if out_of_scope or (validation_status or "") in HELD_VALIDATION_STATUSES:
        return AI_HELD_STATUS
    return "pending"


def ai_eligible_condition():
    """Condition SQLAlchemy : fiches autorisées à entrer dans une file de traitement IA."""
    return and_(
        or_(Device.validation_status.is_(None), Device.validation_status.notin_(sorted(HELD_VALIDATION_STATUSES))),
        or_(Device.ai_rewrite_status.is_(None), Device.ai_rewrite_status != AI_HELD_STATUS),
    )
