import logging
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.utils.hash_utils import compute_fingerprint
from app.utils.text_utils import normalize_title

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_duplicate(self, normalized: dict) -> Optional[Device]:
        """
        Cherche un doublon par :
        1. hash exact du contenu source (même page)
        2. fingerprint titre+organisme+pays (même dispositif, source différente)
        3. similarité du titre normalisé (variantes)
        """
        # 1. Hash exact (même source, même contenu)
        if normalized.get("source_hash"):
            r = await self.db.execute(
                select(Device).where(Device.source_hash == normalized["source_hash"]).limit(1)
            )
            exact = r.scalar_one_or_none()
            if exact:
                logger.debug(f"[Dedup] Hash exact trouvé : {exact.id}")
                return exact

        # 2. Fingerprint titre+organisme+pays
        title = normalized.get("title", "")
        organism = normalized.get("organism", "")
        country = normalized.get("country", "")

        if title and organism and country:
            fp = compute_fingerprint(title, organism, country)
            r = await self.db.execute(
                select(Device).where(
                    Device.title_normalized == normalize_title(title),
                    Device.country == country,
                ).limit(1)
            )
            similar = r.scalar_one_or_none()
            if similar:
                logger.debug(f"[Dedup] Titre+pays correspondant : {similar.id}")
                return similar

        return None
