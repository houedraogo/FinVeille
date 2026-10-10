"""Quarantaine et file de revue des doublons (accès base).

* ``is_quarantined`` / ``quarantine`` : une fiche hors périmètre n'est ni créée
  ni réexaminée à chaque collecte. Les règles structurelles (``scope_*``) sont
  déterministes : elles s'appliquent toujours. Une quarantaine manuelle n'est
  levée que si le contenu de la source a changé (hash différent).
* ``record_duplicate_candidate`` : enregistre un doublon PROBABLE pour revue
  humaine (jamais de fusion automatique).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog_cleanup import DeviceRejection, DuplicateCandidate
from app.services.device_identity import Assessment, DuplicateTier, canonical_url


def _uuid(value) -> Optional[UUID]:
    if value is None or isinstance(value, UUID):
        return value
    return UUID(str(value))


async def is_quarantined(
    db: AsyncSession, *, source_id, source_url: Optional[str], content_hash: Optional[str] = None
) -> Optional[DeviceRejection]:
    """Renvoie la décision de quarantaine applicable, ou None."""
    url = canonical_url(source_url)
    if not url:
        return None
    row = (await db.execute(
        select(DeviceRejection).where(
            DeviceRejection.source_id == _uuid(source_id),
            DeviceRejection.canonical_url == url,
        ).limit(1)
    )).scalar_one_or_none()
    if row is None:
        return None
    if row.rule.startswith("scope_"):
        return row
    if row.content_hash and content_hash and row.content_hash != content_hash:
        return None  # contenu modifié à la source : réexamen autorisé
    return row


async def quarantine(
    db: AsyncSession,
    *,
    source_id,
    source_url: Optional[str],
    title: Optional[str],
    content_hash: Optional[str],
    rule: str,
    reason: Optional[str],
    decided_by: str = "system",
) -> Optional[DeviceRejection]:
    """Enregistre (une seule fois) la mise en quarantaine d'une fiche refusée."""
    url = canonical_url(source_url)
    if not url:
        return None
    existing = await is_quarantined(db, source_id=source_id, source_url=source_url)
    if existing is not None:
        return existing
    row = (await db.execute(
        select(DeviceRejection).where(
            DeviceRejection.source_id == _uuid(source_id), DeviceRejection.canonical_url == url
        ).limit(1)
    )).scalar_one_or_none()
    if row is None:
        row = DeviceRejection(source_id=_uuid(source_id), canonical_url=url)
        db.add(row)
    row.title = title
    row.content_hash = content_hash
    row.rule = rule
    row.reason = reason
    row.decided_by = decided_by
    await db.flush()
    return row


async def record_duplicate_candidate(
    db: AsyncSession, device_id, other_device_id, assessment: Assessment
) -> Optional[DuplicateCandidate]:
    """Enregistre un couple PROBABLE (ordre canonique, idempotent)."""
    if assessment.tier is not DuplicateTier.PROBABLE:
        return None
    a, b = sorted((_uuid(device_id), _uuid(other_device_id)), key=str)
    if a == b:
        return None
    existing = (await db.execute(
        select(DuplicateCandidate).where(
            DuplicateCandidate.device_id == a, DuplicateCandidate.other_device_id == b
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    row = DuplicateCandidate(
        device_id=a, other_device_id=b, tier=assessment.tier.value, reasons=list(assessment.reasons), status="open"
    )
    db.add(row)
    await db.flush()
    return row
