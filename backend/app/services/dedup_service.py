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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.utils.text_utils import normalize_title

logger = logging.getLogger(__name__)


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
        result = await self.db.execute(select(Device))
        devices: List[Device] = list(result.scalars().all())

        # Groupement
        groups: Dict[str, List[Device]] = defaultdict(list)
        for d in devices:
            key = _device_key(d.title_normalized, d.country)
            if key == "|":
                continue
            groups[key].append(d)

        merged_groups = 0
        deleted_count = 0
        enriched_count = 0
        ids_to_delete: List = []

        for key, devs in groups.items():
            if len(devs) < 2:
                continue

            # Canonical = le plus complet, puis le plus ancien
            devs.sort(
                key=lambda d: (-(d.completeness_score or 0), d.created_at or datetime.min)
            )
            canonical = devs[0]
            duplicates = devs[1:]

            enriched = False
            for dup in duplicates:
                if _merge_fields(canonical, dup):
                    enriched = True
                ids_to_delete.append(dup.id)
                deleted_count += 1

            if enriched:
                canonical.updated_at = datetime.now(timezone.utc)
                enriched_count += 1

            merged_groups += 1

        if ids_to_delete:
            await self.db.execute(
                delete(Device).where(Device.id.in_(ids_to_delete))
            )
            await self.db.commit()
            logger.info(
                f"[Dedup] {deleted_count} doublons supprimés "
                f"({merged_groups} groupes, {enriched_count} fiches enrichies)"
            )

        return {
            "merged_groups":  merged_groups,
            "deleted":        deleted_count,
            "enriched":       enriched_count,
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
        # Charger le canonical
        r = await self.db.execute(select(Device).where(Device.id == canonical_id))
        canonical = r.scalar_one_or_none()
        if not canonical:
            raise ValueError(f"Dispositif {canonical_id} introuvable")

        enriched = False
        deleted = 0
        for dup_id in duplicate_ids:
            r2 = await self.db.execute(select(Device).where(Device.id == dup_id))
            dup = r2.scalar_one_or_none()
            if dup and str(dup.id) != canonical_id:
                if _merge_fields(canonical, dup):
                    enriched = True
                await self.db.delete(dup)
                deleted += 1

        if enriched:
            canonical.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        return {
            "canonical_id": canonical_id,
            "deleted":      deleted,
            "enriched":     enriched,
            "message":      f"{deleted} doublon(s) fusionné(s) dans la fiche {canonical_id}.",
        }
