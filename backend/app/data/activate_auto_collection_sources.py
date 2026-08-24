"""Active la collecte automatique pour les sources manuelles exploitables.

Le basculement est volontairement conservateur: les sources qualifiees comme
manuelles, les PDF et les pages avec revue manuelle obligatoire restent en
manual. La premiere vague cible les pages de programmes, appels et listings.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AUTO_HTML_SOURCE_KINDS = {
    "call_page",
    "listing",
    "official_national_aid",
    "official_news_page",
    "official_operator_program",
    "program_announcement",
    "program_category",
    "program_followup",
    "program_page",
    "regional_program",
    "single_call_page",
    "single_program_page",
}

LISTING_SOURCE_KINDS = {"call_page", "listing", "official_news_page"}


def _is_http_url(url: str | None) -> bool:
    return bool(url and str(url).strip().lower().startswith(("http://", "https://")))


def _auto_config(source: Source) -> dict[str, Any]:
    config = dict(source.config or {})
    source_kind = str(config.get("source_kind") or "").strip()
    config.setdefault("auto_collection_enabled_at", datetime.now(timezone.utc).isoformat())
    config.setdefault("previous_collection_mode", source.collection_mode)
    config.setdefault("detail_fetch", True)
    config.setdefault("detail_max_chars", 7000)
    config.setdefault("title_selector", "h1, h2, h3, .entry-title, .post-title, .card-title, .title")
    config.setdefault("description_selector", "p, .description, .summary, .excerpt, .content")

    if source_kind in LISTING_SOURCE_KINDS:
        config.setdefault("list_selector", "article, .post, .card, .views-row, .elementor-post, li")
        config.setdefault("link_selector", "article a, .post a, .card a, h1 a, h2 a, h3 a, a")
        config.setdefault("pagination", {"max_pages": 2})
    else:
        config.pop("list_selector", None)
        config.pop("link_selector", None)
        config.setdefault("pagination", {"max_pages": 1})

    return config


def _eligible(source: Source) -> bool:
    config = source.config or {}
    source_kind = str(config.get("source_kind") or "").strip()
    if not source.is_active or source.collection_mode != "manual":
        return False
    if not _is_http_url(source.url):
        return False
    if config.get("publication_policy") == "manual_review_required":
        return False
    if config.get("auto_collection_blocked_reason"):
        return False
    if source_kind not in AUTO_HTML_SOURCE_KINDS:
        return False
    return True


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Source)
                .where(Source.is_active.is_(True), Source.collection_mode == "manual")
                .order_by(Source.level.asc(), Source.name.asc())
            )
        ).scalars().all()

        candidates = [source for source in rows if _eligible(source)]
        if limit:
            candidates = candidates[:limit]

        stats: dict[str, Any] = {
            "dry_run": not apply,
            "candidates": len(candidates),
            "by_source_kind": {},
            "sample": [],
        }

        for source in candidates:
            config = source.config or {}
            source_kind = str(config.get("source_kind") or "<none>")
            stats["by_source_kind"][source_kind] = stats["by_source_kind"].get(source_kind, 0) + 1
            if len(stats["sample"]) < 30:
                stats["sample"].append(
                    {
                        "id": str(source.id),
                        "name": source.name,
                        "source_kind": source_kind,
                        "url": source.url,
                    }
                )
            if apply:
                source.collection_mode = "html"
                source.config = _auto_config(source)
                source.updated_at = datetime.now(timezone.utc)

        if apply:
            await db.commit()
        else:
            await db.rollback()

        return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
