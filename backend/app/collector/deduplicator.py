import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.device_identity import (
    Assessment,
    DuplicateTier,
    assess_pair,
    organism_key,
    is_generic_organism,
    title_key,
    url_variants,
)
from app.utils.text_utils import normalize_title

logger = logging.getLogger(__name__)

# Nombre maximal de fiches candidates examinées par niveau de recherche.
MAX_CANDIDATES = 30


def _as_mapping(device: Device) -> dict:
    return {
        "id": device.id,
        "title": device.title,
        "organism": device.organism,
        "country": device.country,
        "source_url": device.source_url,
    }


class Deduplicator:
    """Recherche d'une fiche déjà connue pour un élément collecté.

    Nettoyage du catalogue (octobre 2026) : l'ancien critère « titre
    normalisé + pays » fusionnait des aides territoriales distinctes qui
    partagent un intitulé générique et ratait les vraies variantes. La
    décision repose désormais sur ``device_identity.assess_pair`` :

    * CERTAIN  -> la fiche existante est renvoyée (mise à jour, pas de doublon) ;
    * PROBABLE -> aucune fusion : la fiche sera créée et le couple enregistré
                  en file de revue (``last_candidates``) ;
    * HOMONYME -> aucune fusion, aucune alerte (aides distinctes).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        #: couples (Device existant, Assessment) PROBABLES du dernier appel.
        self.last_candidates: list[tuple[Device, Assessment]] = []

    async def find_duplicate(self, normalized: dict) -> Optional[Device]:
        self.last_candidates = []

        # 1. Hash exact (même source, même contenu).
        if normalized.get("source_hash"):
            r = await self.db.execute(
                select(Device).where(Device.source_hash == normalized["source_hash"]).limit(1)
            )
            exact = r.scalar_one_or_none()
            if exact:
                logger.debug(f"[Dedup] Hash exact trouvé : {exact.id}")
                return exact

        candidate = {
            "title": normalized.get("title"),
            "organism": normalized.get("organism"),
            "country": normalized.get("country"),
            "source_url": normalized.get("source_url"),
        }
        seen: set = set()
        incoming_source = str(normalized.get("source_id") or "")

        # 2. Même page source (variantes http/https, www, slash final).
        variants = url_variants(candidate["source_url"])
        pools = []
        if variants:
            pools.append((await self.db.execute(
                select(Device).where(Device.source_url.in_(variants)).limit(MAX_CANDIDATES)
            )).scalars().all())

        # 3. Même intitulé (clé stricte) dans le même pays.
        title = candidate["title"] or ""
        if title and candidate["country"]:
            pools.append((await self.db.execute(
                select(Device).where(
                    Device.title_normalized == normalize_title(title),
                    Device.country == candidate["country"],
                ).limit(MAX_CANDIDATES)
            )).scalars().all())

        # Plusieurs fiches de même page : on mesure à quel point l'URL est une page
        # « liste » (titres différents) pour ne pas la prendre comme preuve.
        url_pool = pools[0] if variants else []
        distinct_titles = len({title_key(d.title) for d in url_pool}) if url_pool else 0

        def distinct_titles_for_url(_url: str) -> int:
            return distinct_titles

        for pool in pools:
            for existing in pool:
                if existing.id in seen:
                    continue
                seen.add(existing.id)
                assessment = assess_pair(
                    candidate, _as_mapping(existing), distinct_titles_for_url=distinct_titles_for_url,
                )
                if assessment.tier is DuplicateTier.CERTAIN:
                    logger.debug(f"[Dedup] Doublon certain {existing.id}: {assessment.reasons}")
                    return existing
                # Même source + même intitulé + même financeur précis = même élément
                # recollecté sous une URL différente (rien à créer).
                if (
                    incoming_source
                    and str(existing.source_id or "") == incoming_source
                    and title_key(existing.title) == title_key(title)
                    and organism_key(existing.organism) == organism_key(candidate["organism"])
                    and not is_generic_organism(existing.organism)
                ):
                    return existing
                if assessment.tier is DuplicateTier.PROBABLE:
                    self.last_candidates.append((existing, assessment))

        return None
