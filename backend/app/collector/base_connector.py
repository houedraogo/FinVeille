from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import asyncio
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionResult:
    source_id: str
    items: List[RawItem]
    success: bool
    error: Optional[str] = None
    items_count: int = 0

    def __post_init__(self):
        self.items_count = len(self.items)


class BaseConnector(ABC):
    """Classe abstraite — tous les connecteurs en héritent."""

    BOT_HEADERS = {
        "User-Agent": "Kafundo/1.0 Bot (veille financement; +https://kafundo.com/bot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }

    def __init__(self, source: dict):
        self.source = source
        self.source_id = str(source["id"])
        self.url = source["url"]
        self.config = source.get("config") or {}
        self.timeout = self.config.get("timeout", settings.DEFAULT_REQUEST_TIMEOUT)
        self.delay = self.config.get("delay", settings.DEFAULT_REQUEST_DELAY)

    @abstractmethod
    async def collect(self) -> CollectionResult:
        pass

    async def _get(self, url: str, extra_headers: dict = None) -> httpx.Response:
        headers = {**self.BOT_HEADERS}
        # Permettre un User-Agent personnalisé via la config (contourne les blocages 403)
        if self.config.get("user_agent"):
            headers["User-Agent"] = self.config["user_agent"]
        if extra_headers:
            headers.update(extra_headers)

        last_error = None
        for attempt in range(settings.MAX_RETRIES):
            if attempt > 0:
                wait = self.delay * (2 ** attempt)
                logger.debug(f"[{self.source_id}] Retry {attempt} — attente {wait:.1f}s")
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=True,
                ) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    await asyncio.sleep(self.delay)  # Politesse systématique
                    return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404, 410, 451):
                    raise  # Inutile de retry
                last_error = e
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e

        raise Exception(f"Échec après {settings.MAX_RETRIES} tentatives: {last_error}")

    def _build_absolute_url(self, href: str, base_url: str) -> str:
        if href.startswith("http"):
            return href
        from urllib.parse import urlparse, urljoin
        return urljoin(base_url, href)
