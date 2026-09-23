"""
Service de déduplication des dispositifs.

Stratégie :
  1. Groupement par `title_normalized + country` (même logique que le Deduplicator en collecte)
  2. Dans chaque groupe, on conserve la fiche la plus complète (completeness_score max)
     puis la plus ancienne en cas d'égalité.
  3. Les champs manquants du gagnant sont complétés par les doublons avant suppression.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.alert import AlertDelivery
from app.models.device_history import DeviceHistory
from app.models.relevance import DeviceRelevanceCache
from app.models.workspace import DevicePipeline, FavoriteDevice
from app.utils.text_utils import normalize_title

logger = logging.getLogger(__name__)

_DEVICE_REFERENCE_TABLES = {
    "device_pipeline", "favorite_devices", "device_history", "device_relevance_cache",
    "alert_deliveries",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _device_key(title_normalized: Optional[str], country: Optional[str]) -> str:
    """Clé de groupe : titre normalisé + pays."""
    return f"{(title_normalized or '').strip()}|{(country or '').strip()}"


def _merge_fields(canonical: Device, dup: Device) -> bool:
    """
    Copie les champs utiles de `dup` vers `canonical` s'ils sont absents.
    Retourne True si au moins un champ a été enrichi.
    """
    changed = False
    pairs = [
        ("amount_min",          dup.amount_min),
        ("amount_max",          dup.amount_max),
        ("close_date",          dup.close_date),
        ("open_date",           dup.open_date),
        ("full_description",    dup.full_description),
        ("eligibility_criteria", dup.eligibility_criteria),
        ("eligible_expenses",   dup.eligible_expenses),
        ("funding_rate",        dup.funding_rate),
        ("funding_details",     dup.funding_details),
    ]
    for attr, dup_val in pairs:
        if not getattr(canonical, attr) and dup_val:
            setattr(canonical, attr, dup_val)
            changed = True
    # Fusionner les tags (union sans doublon)
    if dup.tags:
        existing = set(canonical.tags or [])
        new_tags = existing | set(dup.tags)
        if new_tags != existing:
            canonical.tags = list(new_tags)
            changed = True
    return changed


# ---------------------------------------------------------------------------
# DedupService
# ---------------------------------------------------------------------------

class DedupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _transfer_references(self, canonical_id, duplicate_ids):
        """Move every known FK; refuse ambiguous unique-key collisions before changing data."""
        # Check the *live* schema too: a newly added FK must never be silently cascaded.
        tables = set((await self.db.execute(text("""
            SELECT DISTINCT conrelid::regclass::text
            FROM pg_constraint
            WHERE contype = 'f' AND confrelid = 'devices'::regclass
        """))).scalars())
        if tables != _DEVICE_REFERENCE_TABLES:
            raise ValueError(f"Relations de dispositif non prises en charge: {sorted(tables ^ _DEVICE_REFERENCE_TABLES)}")

        all_ids = [canonical_id, *duplicate_ids]
        for model, scope in (
            (DevicePipeline, lambda row: row.user_id),
            (FavoriteDevice, lambda row: row.user_id),
            (DeviceRelevanceCache, lambda row: (row.organization_id, row.funding_project_id)),
        ):
            rows = (await self.db.execute(
                select(model).where(model.device_id.in_(all_ids)).with_for_update()
            )).scalars().all()
            seen = set()
            for row in rows:
                key = scope(row)
                if key in seen:
                    raise ValueError(
                        f"Fusion reportée: deux relations {model.__tablename__} partagent le même périmètre {key}"
                    )
                seen.add(key)

        for model in (DevicePipeline, FavoriteDevice, DeviceHistory, DeviceRelevanceCache):
            await self.db.execute(
                update(model).where(model.device_id.in_(duplicate_ids)).values(device_id=canonical_id)
            )
        # Preserve confirmation even when both copies were already sent for
        # the same alert; the composite key permits only one canonical row.
        deliveries = (await self.db.execute(select(AlertDelivery).where(
            AlertDelivery.device_id.in_(all_ids),
        ).with_for_update())).scalars().all()
        canonical_alerts = {row.alert_id for row in deliveries if row.device_id == canonical_id}
        for row in deliveries:
            if row.device_id == canonical_id:
                continue
            if row.alert_id not in canonical_alerts:
                self.db.add(AlertDelivery(alert_id=row.alert_id, device_id=canonical_id, sent_at=row.sent_at))
                canonical_alerts.add(row.alert_id)
            await self.db.delete(row)
        await self.db.flush()

    # ------------------------------------------------------------------ #
    # Détection                                                            #
    # ------------------------------------------------------------------ #

    async def find_duplicate_groups(self) -> Dict[str, Any]:
        """
        Retourne tous les groupes de doublons détectés, triés par taille décroissante.
        """
        result = await self.db.execute(
            select(
                Device.id,
                Device.title,
                Device.title_normalized,
                Device.organism,
                Device.country,
                Device.status,
                Device.validation_status,
                Device.completeness_score,
                Device.source_url,
                Device.created_at,
            )
        )
        rows = result.all()

        # Groupement
        groups: Dict[str, List] = defaultdict(list)
        for row in rows:
            key = _device_key(row.title_normalized, row.country)
            if key == "|":          # titre ET pays vides → ignorer
                continue
            groups[key].append(row)

        # Ne garder que les groupes avec doublons
        dup_groups = []
        for key, devs in groups.items():
            if len(devs) < 2:
                continue
            # Trier : meilleure complétude d'abord, puis le plus ancien
            sorted_devs = sorted(
                devs,
                key=lambda d: (-(d.completeness_score or 0), d.created_at or datetime.min),
            )
            dup_groups.append({
                "key": key,
                "count": len(devs),
                "canonical_id": str(sorted_devs[0].id),   # celui qu'on garderait
                "devices": [
                    {
                        "id":                str(d.id),
                        "title":             d.title,
                        "organism":          d.organism,
                        "country":           d.country,
                        "status":            d.status,
                        "validation_status": d.validation_status,
                        "completeness_score": d.completeness_score,
                        "source_url":        d.source_url,
                        "created_at":        d.created_at.isoformat() if d.created_at else None,
                        "is_canonical":      d.id == sorted_devs[0].id,
                    }
                    for d in sorted_devs
                ],
            })

        dup_groups.sort(key=lambda g: g["count"], reverse=True)

        return {
            "total_groups":     len(dup_groups),
            "total_duplicates": sum(g["count"] - 1 for g in dup_groups),
            "groups":           dup_groups[:100],   # max 100 groupes retournés
        }

    # ------------------------------------------------------------------ #
    # Fusion automatique                                                   #
    # ------------------------------------------------------------------ #

    async def merge_duplicates_auto(self) -> Dict[str, Any]:
        """
        Fusionne automatiquement tous les groupes de doublons :
        - Conserve la fiche la plus complète (canonical)
        - Transfère les champs utiles des doublons vers le canonical
        - Supprime les doublons
        """
        # Charger toutes les fiches avec leurs données complètes
        result = await self.db.execute(select(
            Device.id, Device.title_normalized, Device.country,
            Device.completeness_score, Device.created_at,
        ))
        devices = result.all()

        # Groupement
        groups: Dict[str, List] = defaultdict(list)
        for d in devices:
            key = _device_key(d.title_normalized, d.country)
            if key == "|":
                continue
            groups[key].append(d)

        merged_groups = 0
        deleted_count = 0
        enriched_count = 0
        skipped_groups = 0

        for key, devs in groups.items():
            if len(devs) < 2:
                continue

            # Canonical = le plus complet, puis le plus ancien
            devs.sort(
                key=lambda d: (-(d.completeness_score or 0), d.created_at or datetime.min)
            )
            canonical = devs[0]
            duplicates = devs[1:]

            try:
                result = await self.merge_group(str(canonical.id), [str(d.id) for d in duplicates])
            except ValueError as exc:
                skipped_groups += 1
                logger.warning("[Dedup] Groupe %s conservé: %s", key, exc)
                continue
            merged_groups += 1
            deleted_count += result["deleted"]
            enriched_count += int(result["enriched"])

        return {
            "merged_groups":  merged_groups,
            "deleted":        deleted_count,
            "enriched":       enriched_count,
            "skipped_groups": skipped_groups,
            "message": (
                f"{deleted_count} doublon(s) supprimé(s) "
                f"dans {merged_groups} groupe(s) — "
                f"{enriched_count} fiche(s) enrichie(s) au passage."
            ),
        }

    # ------------------------------------------------------------------ #
    # Fusion manuelle d'un groupe                                          #
    # ------------------------------------------------------------------ #

    async def merge_group(self, canonical_id: str, duplicate_ids: List[str]) -> Dict[str, Any]:
        """
        Fusionne manuellement : conserve `canonical_id`, supprime `duplicate_ids`.
        Transfère les champs utiles avant suppression.
        """
        try:
            ids = list(dict.fromkeys([canonical_id, *(d for d in duplicate_ids if d != canonical_id)]))
            rows = (await self.db.execute(
                select(Device).where(Device.id.in_(ids)).order_by(Device.id).with_for_update()
            )).scalars().all()
            by_id = {str(device.id): device for device in rows}
            canonical = by_id.get(canonical_id)
            if canonical is None:
                raise ValueError(f"Dispositif {canonical_id} introuvable")
            duplicates = [by_id[device_id] for device_id in ids[1:] if device_id in by_id]
            if duplicates:
                await self._transfer_references(canonical.id, [device.id for device in duplicates])
            enriched = False
            for dup in duplicates:
                if _merge_fields(canonical, dup):
                    enriched = True
            if enriched:
                canonical.updated_at = datetime.now(timezone.utc)
            for dup in duplicates:
                await self.db.delete(dup)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        deleted = len(duplicates)
        return {
            "canonical_id": canonical_id,
            "deleted":      deleted,
            "enriched":     enriched,
            "message":      f"{deleted} doublon(s) fusionné(s) dans la fiche {canonical_id}.",
        }
