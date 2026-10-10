"""Une fiche peut-elle être supprimée physiquement ? Source unique pour la fusion, la purge et la suppression.

Avant octobre 2026, deux listes de tables « référençant devices » étaient codées en dur à deux endroits
(``dedup_service`` et ``device_service``) et divergeaient du schéma dès qu'une table était ajoutée : la migration
b7d3a91c5e24 a ajouté ``device_archive_log`` et ``device_duplicate_candidates`` sans mettre ces listes à jour,
ce qui a fermé (en échec propre) les fusions et la purge administratives.

Cette liste est désormais UNIQUE. Le contrôle du schéma réel reste « fermé » : une nouvelle clé étrangère vers
``devices`` non déclarée ici fait échouer la suppression au lieu de cascader en silence.

Une fiche n'est jamais supprimable si :
* elle est archivée ;
* elle porte une ligne de ``device_archive_log`` (journal de restauration, y compris ``ai_hold``) ;
* elle est la fiche conservée (``merged_into_id``) d'un doublon archivé.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.archive_guard import DeviceDeletionForbidden
from app.models.catalog_cleanup import ARCHIVED_STATUS, DeviceArchiveLog
from app.models.device import Device

# Tables ayant une clé étrangère vers devices, avec ce que la suppression d'une fiche en fait.
#   - transférées vers la fiche conservée lors d'une fusion : device_pipeline, favorite_devices, device_history,
#     device_relevance_cache, alert_deliveries ;
#   - re-pointées / nettoyées explicitement : device_duplicate_candidates (file de revue) ;
#   - JAMAIS cascadées : device_archive_log (journal de restauration) — la fiche n'est alors pas supprimable.
DEVICE_REFERENCE_TABLES = frozenset({
    "device_pipeline", "favorite_devices", "device_history", "device_relevance_cache", "alert_deliveries",
    "device_archive_log", "device_duplicate_candidates",
})

REASON_ARCHIVED = "archived"
REASON_HAS_ARCHIVE_LOG = "has_archive_log"
REASON_MERGE_TARGET = "merge_target_of_archived"


async def assert_known_device_relations(db: AsyncSession) -> None:
    """Échoue si le schéma réel a une clé étrangère vers devices que le code ne sait pas traiter."""
    live = set((await db.execute(text("""
        SELECT DISTINCT conrelid::regclass::text
        FROM pg_constraint
        WHERE contype = 'f' AND confrelid = 'devices'::regclass
    """))).scalars().all())
    if live != DEVICE_REFERENCE_TABLES:
        raise ValueError(
            f"Relations de dispositif non prises en charge: {sorted(live ^ DEVICE_REFERENCE_TABLES)}"
        )


async def find_non_deletable(db: AsyncSession, device_ids: Iterable, *, allow_merge_target: bool = False) -> dict[str, str]:
    """``{id: motif}`` pour chaque fiche qui ne doit PAS être supprimée physiquement (vide = tout est permis)."""
    ids = list(dict.fromkeys(device_ids))
    if not ids:
        return {}
    has_log = exists().where(DeviceArchiveLog.device_id == Device.id)
    is_target = exists().where(DeviceArchiveLog.merged_into_id == Device.id)
    rows = (await db.execute(
        select(Device.id, Device.validation_status, has_log.label("has_log"), is_target.label("is_target"))
        .where(Device.id.in_(ids))
    )).all()
    blocked: dict[str, str] = {}
    for device_id, validation_status, has_log_, is_target_ in rows:
        if validation_status == ARCHIVED_STATUS:
            blocked[str(device_id)] = REASON_ARCHIVED
        elif has_log_:
            blocked[str(device_id)] = REASON_HAS_ARCHIVE_LOG
        elif is_target_ and not allow_merge_target:
            blocked[str(device_id)] = REASON_MERGE_TARGET
    return blocked


async def assert_deletable(
    db: AsyncSession, device_ids: Iterable, *, action: str = "Suppression", allow_merge_target: bool = False,
) -> None:
    blocked = await find_non_deletable(db, device_ids, allow_merge_target=allow_merge_target)
    if blocked:
        sample = ", ".join(f"{i[:8]}…={r}" for i, r in list(blocked.items())[:5])
        raise DeviceDeletionForbidden(
            f"{action} refusée: {len(blocked)} fiche(s) archivée(s) ou journalisée(s) ({sample}). "
            "Utiliser l'archivage/la restauration réversibles, jamais la suppression physique."
        )
