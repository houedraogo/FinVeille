import logging
import os
import re
from html import unescape
from urllib.parse import parse_qs, urlencode, urlparse

from app.collector.base_connector import BaseConnector, CollectionResult, RawItem

logger = logging.getLogger(__name__)

PUBLIC_URL_RE = re.compile(r"https?://[^\s<>'\")]+", re.IGNORECASE)
BLOCKED_PUBLIC_URL_HOSTS = {
    "api.aides-entreprises.fr",
    "aides-entreprises.fr",
    "www.aides-entreprises.fr",
    "data.aides-entreprises.fr",
    "entreprise.api.gouv.fr",
}


class APIConnector(BaseConnector):
    """
    Collecte depuis une API REST JSON.

    config attendu :
    {
        "api_key_header": "X-API-Key",
        "api_key_value": "xxx",
        "items_path": "results",
        "title_field": "intitule",
        "url_field": "url",
        "description_field": "description",
        "url_template": "https://example.com/detail/{id}",
        "raw_content_fields": ["description", "conditions"],
        "preferred_url_fields": ["links.0.url"],
        "pagination": {
            "type": "page",
            "page_param": "page",
            "size_param": "per_page",
            "size_value": 50,
            "offset_param": "start"
        }
    }

    Note : si items_path pointe vers un dict (ex. World Bank),
    les valeurs du dict sont utilisées comme liste d'items.
    """

    async def collect(self) -> CollectionResult:
        headers = self._build_headers()

        pagination = self.config.get("pagination") or {}
        page = 1
        offset = 0
        all_items = []
        pagination_type = pagination.get("type", "page")

        try:
            while True:
                params = {}
                if pagination:
                    size_val = pagination.get("size_value", 20)
                    if pagination_type == "offset":
                        params[pagination.get("offset_param", "start")] = offset
                        params[pagination.get("size_param", "rows")] = size_val
                    else:
                        params[pagination.get("page_param", "page")] = page
                        params[pagination.get("size_param", "per_page")] = size_val

                parsed = urlparse(self.url)
                existing = parse_qs(parsed.query, keep_blank_values=True)
                base_params = {key: value[0] for key, value in existing.items()}
                merged = {**base_params, **params}
                clean_base = parsed._replace(query="").geturl()
                url = f"{clean_base}?{urlencode(merged)}" if merged else clean_base
                response = await self._get(url, extra_headers=headers)
                data = response.json()

                page_items = self._extract_items(data)
                if self.config.get("detail_url_template"):
                    page_items = await self._enrich_items_with_detail(page_items, headers)
                if not page_items:
                    break

                all_items.extend(page_items)

                size_val = pagination.get("size_value", 20) if pagination else 20
                if not pagination or len(page_items) < size_val:
                    break
                if page >= 20:
                    logger.warning(f"[API][{self.source_id}] Limite 20 pages atteinte")
                    break
                page += 1
                offset += size_val

            logger.info(f"[API][{self.source_id}] {len(all_items)} items collectés")
            return CollectionResult(source_id=self.source_id, items=all_items, success=True)
        except Exception as exc:
            logger.error(f"[API][{self.source_id}] Erreur : {exc}")
            return CollectionResult(source_id=self.source_id, items=[], success=False, error=str(exc))

    def _build_headers(self) -> dict:
        headers = {}
        if self.config.get("api_key_header"):
            api_key_value = self.config.get("api_key_value", "")
            api_key_env = self.config.get("api_key_env")
            if api_key_env and not api_key_value:
                api_key_value = os.getenv(api_key_env, "")
            headers[self.config["api_key_header"]] = api_key_value

        for header_conf in self.config.get("api_headers", []):
            header_name = header_conf.get("name")
            if not header_name:
                continue
            header_value = header_conf.get("value", "")
            header_env = header_conf.get("env")
            if header_env and not header_value:
                header_value = os.getenv(header_env, "")
            if header_value:
                headers[header_name] = header_value
        return headers

    def _get_nested_value(self, item: dict, field_path: str):
        """Récupère une valeur avec support dot-notation et index de listes."""
        value = item
        for key in str(field_path).split("."):
            if isinstance(value, dict):
                value = value.get(key, "")
                continue
            if isinstance(value, list):
                if key.isdigit():
                    index = int(key)
                    if 0 <= index < len(value):
                        value = value[index]
                        continue
                return ""
            return ""

        if isinstance(value, dict):
            return value.get(
                "cdata",
                value.get("text", value.get("texte", value.get("value", value.get("Name", str(value))))),
            )
        return value or ""

    def _stringify_value(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in ("text", "texte", "label", "title", "name", "value", "cdata", "Name"):
                nested = value.get(key)
                if nested:
                    return self._stringify_value(nested)
            return ""
        if isinstance(value, list):
            parts = [self._stringify_value(item) for item in value]
            return " ".join(part for part in parts if part).strip()
        return unescape(str(value)).strip()

    def _extract_public_url(self, value) -> str:
        text = self._stringify_value(value)
        if not text:
            return ""

        match = PUBLIC_URL_RE.search(text)
        if not match:
            return ""

        candidate = match.group(0).strip().rstrip(").,;")
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate
        return ""

    def _extract_external_public_url(self, value) -> str:
        candidate = self._extract_public_url(value)
        if not candidate:
            return ""
        parsed = urlparse(candidate)
        host = (parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            stripped = host[4:]
        else:
            stripped = host
        if host in BLOCKED_PUBLIC_URL_HOSTS or stripped in BLOCKED_PUBLIC_URL_HOSTS:
            return ""
        return candidate

    def _walk_values(self, value):
        if isinstance(value, dict):
            for nested in value.values():
                yield nested
                yield from self._walk_values(nested)
        elif isinstance(value, list):
            for nested in value:
                yield nested
                yield from self._walk_values(nested)

    def _find_fallback_public_url(self, item: dict) -> str:
        if not self.config.get("scan_all_public_urls"):
            return ""
        for nested in self._walk_values(item):
            candidate = self._extract_external_public_url(nested)
            if candidate:
                return candidate
        return ""

    def _compose_raw_content(self, item: dict, field_paths: list[str]) -> str:
        parts: list[str] = []
        seen: set[str] = set()

        for field_path in field_paths:
            if not field_path:
                continue
            value = self._get_nested_value(item, field_path)
            text = self._stringify_value(value)
            if not text:
                continue
            normalized = " ".join(text.split())
            if normalized in seen:
                continue
            seen.add(normalized)
            parts.append(text)

        return "\n\n".join(parts).strip()

    def _extract_items(self, data) -> list:
        items_path = self.config.get("items_path", "")
        raw = data

        if items_path:
            for key in items_path.split("."):
                if isinstance(raw, dict):
                    raw = raw.get(key, [])
                else:
                    break

        if isinstance(raw, dict):
            raw = list(raw.values())

        if not isinstance(raw, list):
            return []

        title_field = self.config.get("title_field", "title")
        url_field = self.config.get("url_field", "url")
        description_field = self.config.get("description_field", "description")
        url_template = self.config.get("url_template", "")
        raw_content_fields = self.config.get("raw_content_fields") or [description_field]
        preferred_url_fields = self.config.get("preferred_url_fields") or []

        items = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            title = self._get_nested_value(item, title_field)
            if not title:
                continue

            url_fallback = self.config.get("url_fallback", self.url)
            if url_template:
                item_url = url_template
                for key, value in item.items():
                    if isinstance(value, str):
                        item_url = item_url.replace(f"{{{key}}}", value)
            elif url_field:
                item_url = self._get_nested_value(item, url_field) or url_fallback
            else:
                item_url = url_fallback

            preferred_url = ""
            for field_path in preferred_url_fields:
                candidate = self._extract_public_url(self._get_nested_value(item, field_path))
                if candidate:
                    preferred_url = candidate
                    break
            if not preferred_url:
                preferred_url = self._find_fallback_public_url(item)

            raw_content = self._compose_raw_content(item, raw_content_fields)
            if not raw_content:
                raw_content = self._stringify_value(self._get_nested_value(item, description_field))

            items.append(
                RawItem(
                    title=str(title),
                    url=str(preferred_url or item_url),
                    raw_content=str(raw_content),
                    source_id=self.source_id,
                    metadata=item,
                )
            )
        return items

    async def _enrich_items_with_detail(self, items: list[RawItem], headers: dict) -> list[RawItem]:
        detail_template = self.config.get("detail_url_template", "")
        detail_desc_field = self.config.get("detail_description_field") or self.config.get("description_field", "description")
        detail_path = self.config.get("detail_path", "")
        detail_raw_content_fields = self.config.get("detail_raw_content_fields") or self.config.get("raw_content_fields") or [detail_desc_field]
        preferred_url_fields = self.config.get("preferred_url_fields") or []
        if not detail_template:
            return items

        enriched_items: list[RawItem] = []
        for item in items:
            metadata = item.metadata if isinstance(item.metadata, dict) else {}
            detail_url = self._format_template(detail_template, metadata)
            if not detail_url or "{" in detail_url:
                enriched_items.append(item)
                continue

            try:
                response = await self._get(detail_url, extra_headers=headers)
                detail_data = response.json()
                detail_item = self._extract_detail_payload(detail_data, detail_path)
                if isinstance(detail_item, dict):
                    merged_metadata = {**metadata, **detail_item}
                    raw_content = self._compose_raw_content(detail_item, detail_raw_content_fields)
                    if not raw_content:
                        raw_content = self._stringify_value(self._get_nested_value(detail_item, detail_desc_field)) or item.raw_content

                    preferred_url = ""
                    for field_path in preferred_url_fields:
                        candidate = self._extract_public_url(self._get_nested_value(detail_item, field_path))
                        if candidate:
                            preferred_url = candidate
                            break
                    if not preferred_url:
                        preferred_url = self._find_fallback_public_url(detail_item)

                    enriched_items.append(
                        RawItem(
                            title=item.title,
                            url=preferred_url or item.url,
                            raw_content=str(raw_content or ""),
                            source_id=item.source_id,
                            metadata=merged_metadata,
                        )
                    )
                    continue
            except Exception as exc:
                logger.debug(f"[API][{self.source_id}] Detail fetch error for '{item.title}': {exc}")

            enriched_items.append(item)

        return enriched_items

    def _extract_detail_payload(self, data, detail_path: str):
        raw = data
        if detail_path:
            for key in detail_path.split("."):
                if isinstance(raw, dict):
                    raw = raw.get(key)
                else:
                    return None
        if isinstance(raw, list):
            if not raw:
                return None
            first = raw[0]
            return first if isinstance(first, dict) else None
        return raw

    def _format_template(self, template: str, item: dict) -> str:
        result = template
        for key, value in item.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
