"""Apply the visible quality audit recommendations in bulk.

Usage:
    docker exec finveille-backend python -m app.data.apply_visible_quality_audit
    docker exec finveille-backend python -m app.data.apply_visible_quality_audit --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from uuid import UUID

from app.database import AsyncSessionLocal
from app.services.visible_quality_service import apply_quality_action, build_visible_quality_audit


ACTION_MAP = {
    "masquer": "hide",
    "reformuler": "rewrite",
}


async def run(*, apply: bool = False, limit: int = 200) -> dict:
    async with AsyncSessionLocal() as db:
        audit = await build_visible_quality_audit(db, limit=limit)
        items = audit.get("items", [])

        stats = {
            "dry_run": not apply,
            "audited_visible": audit.get("visible_total", 0),
            "to_fix": audit.get("to_fix_total", 0),
            "planned": len(items),
            "applied": 0,
            "by_action": {},
            "errors": [],
            "preview": [],
        }
        action_counts: Counter[str] = Counter()

        for item in items:
            recommendation = item.get("recommended_action")
            action = ACTION_MAP.get(recommendation)
            if not action:
                continue

            action_counts[action] += 1
            preview_item = {
                "id": item.get("id"),
                "title": item.get("title"),
                "source": item.get("source_name"),
                "issues": item.get("issues", []),
                "action": action,
            }
            if len(stats["preview"]) < 20:
                stats["preview"].append(preview_item)

            if not apply:
                continue

            try:
                await apply_quality_action(db, UUID(str(item["id"])), action)
                stats["applied"] += 1
            except Exception as exc:  # noqa: BLE001 - CLI report should keep going.
                stats["errors"].append({**preview_item, "error": str(exc)})

        stats["by_action"] = dict(action_counts)
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply visible quality audit recommendations.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    result = asyncio.run(run(apply=args.apply, limit=args.limit))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
