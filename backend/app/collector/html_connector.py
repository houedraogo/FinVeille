import logging
from typing import List
from bs4 import BeautifulSoup
from app.collector.base_connector import BaseConnector, CollectionResult, RawItem

logger = logging.getLogger(__name__)


class HTMLConnector(BaseConnector):
    """
    Collecte depuis une page HTML statique.

    config attendu dans source.config :
    {
        "list_selector": "CSS selector de la liste des items",
        "item_title_selector": "h2, h3, .title",
        "item_link_selector": "a",
        "item_description_selector": ".description",  (optionnel)
        "pagination": {
            "next_selector": "a.next-page",
            "max_pages": 5
        }
    }
    """

    async def collect(self) -> CollectionResult:
        items = []
        current_url = self.url
        max_pages = (self.config.get("pagination") or {}).get("max_pages", 1)

        try:
            for page_num in range(max_pages):
                page_items = await self._collect_page(current_url)
                items.extend(page_items)

                if page_num < max_pages - 1:
                    next_url = await self._get_next_url(current_url)
                    if not next_url or next_url == current_url:
                        break
                    current_url = next_url

            logger.info(f"[HTML][{self.source_id}] {len(items)} items depuis {self.url}")
            return CollectionResult(source_id=self.source_id, items=items, success=True)

        except Exception as e:
            logger.error(f"[HTML][{self.source_id}] Erreur : {e}")
            return CollectionResult(source_id=self.source_id, items=[], success=False, error=str(e))

    async def _collect_page(self, url: str) -> List[RawItem]:
        response = await self._get(url)
        soup = BeautifulSoup(response.text, "lxml")
        items = []

        list_sel = self.config.get("list_selector")
        title_sel = self.config.get("item_title_selector") or self.config.get("title_selector") or "h2, h3, .title, .card-title"
        link_sel = self.config.get("item_link_selector") or self.config.get("link_selector") or "a"
        desc_sel = self.config.get("item_description_selector") or self.config.get("description_selector")
        detail_enabled = bool(self.config.get("detail_fetch"))
        detail_sel = self.config.get("detail_content_selector")
        detail_max_chars = int(self.config.get("detail_max_chars", 6000))

        if list_sel:
            containers = soup.select(list_sel)
        elif self.config.get("link_selector"):
            containers = soup.select(link_sel)
        else:
            containers = [soup]

        for container in containers:
            title_el = container if getattr(container, "name", None) in {"a", "article", "div", "li"} and container.name == "a" else container.select_one(title_sel)
            if not title_el:
                continue
            title = title_el.get_text(separator=" ", strip=True)
            if not title or len(title) < 5:
                continue

            link = url
            link_el = container if getattr(container, "name", None) == "a" else container.select_one(link_sel)
            if link_el and link_el.get("href"):
                link = self._build_absolute_url(link_el["href"], url)

            description = ""
            if desc_sel:
                desc_el = None if getattr(container, "name", None) == "a" else container.select_one(desc_sel)
                if desc_el:
                    description = desc_el.get_text(separator=" ", strip=True)

            if not description:
                description = container.get_text(separator=" ", strip=True)[:1500]

            if detail_enabled and link and link != url:
                detail_text = await self._fetch_detail_text(link, detail_sel, detail_max_chars)
                if detail_text:
                    description = detail_text

            items.append(RawItem(
                title=title,
                url=link,
                raw_content=description,
                source_id=self.source_id,
            ))

        return items

    async def _fetch_detail_text(self, url: str, detail_selector: str | None, max_chars: int) -> str:
        try:
            response = await self._get(url)
            soup = BeautifulSoup(response.text, "lxml")
            if detail_selector:
                nodes = soup.select(detail_selector)
                if nodes:
                    text = " ".join(node.get_text(separator=" ", strip=True) for node in nodes)
                    return text[:max_chars]
            main = soup.find("main") or soup.find("article") or soup.body or soup
            return main.get_text(separator=" ", strip=True)[:max_chars]
        except Exception as exc:
            logger.debug(f"[HTML][{self.source_id}] Detail fetch error for {url}: {exc}")
            return ""

    async def _get_next_url(self, current_url: str) -> str | None:
        pagination = self.config.get("pagination") or {}
        next_sel = pagination.get("next_selector")
        if not next_sel:
            return None
        response = await self._get(current_url)
        soup = BeautifulSoup(response.text, "lxml")
        el = soup.select_one(next_sel)
        if el and el.get("href"):
            return self._build_absolute_url(el["href"], current_url)
        return None
