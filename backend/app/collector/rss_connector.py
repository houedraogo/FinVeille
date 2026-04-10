import feedparser
import logging
from app.collector.base_connector import BaseConnector, CollectionResult, RawItem

logger = logging.getLogger(__name__)


class RSSConnector(BaseConnector):
    """Collecte depuis un flux RSS ou Atom."""

    async def collect(self) -> CollectionResult:
        try:
            response = await self._get(self.url)
            feed = feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                raise Exception(f"Flux RSS invalide : {feed.bozo_exception}")

            items = []
            for entry in feed.entries:
                title = getattr(entry, "title", "").strip()
                if not title:
                    continue

                link = getattr(entry, "link", self.url)

                # Contenu principal
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content = entry.summary or ""

                items.append(RawItem(
                    title=title,
                    url=link,
                    raw_content=content,
                    source_id=self.source_id,
                    metadata={
                        "published": str(getattr(entry, "published", "")),
                        "updated": str(getattr(entry, "updated", "")),
                        "author": getattr(entry, "author", ""),
                        "tags": [t.get("term", "") for t in getattr(entry, "tags", [])],
                        "feed_title": getattr(feed.feed, "title", ""),
                    },
                ))

            logger.info(f"[RSS][{self.source_id}] {len(items)} items collectés")
            return CollectionResult(source_id=self.source_id, items=items, success=True)

        except Exception as e:
            logger.error(f"[RSS][{self.source_id}] Erreur : {e}")
            return CollectionResult(source_id=self.source_id, items=[], success=False, error=str(e))
