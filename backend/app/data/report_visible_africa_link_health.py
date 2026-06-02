"""Audit strict des liens visibles Afrique."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.data.report_visible_link_health import _check, _visible


AFRICA_COUNTRIES = {
    "afrique",
    "afrique du sud",
    "bénin",
    "benin",
    "burkina faso",
    "cameroun",
    "côte d'ivoire",
    "cote d'ivoire",
    "ghana",
    "guinée",
    "guinee",
    "kenya",
    "madagascar",
    "mali",
    "maroc",
    "mauritanie",
    "niger",
    "république démocratique du congo",
    "republique democratique du congo",
    "rwanda",
    "sénégal",
    "senegal",
    "togo",
    "tunisie",
    "éthiopie",
    "ethiopie",
}


def _is_africa(device: Device) -> bool:
    fields = [device.country, device.region, device.zone, device.geographic_scope]
    text = " ".join(str(value or "").lower() for value in fields)
    return any(country in text for country in AFRICA_COUNTRIES)


async def run() -> dict[str, Any]:
    import httpx

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.country, Device.title))).scalars().all()

    visible = [device for device in devices if _visible(device) and _is_africa(device)]

    semaphore = asyncio.Semaphore(8)
    timeout = httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=8.0)
    headers = {"User-Agent": "Mozilla/5.0 Kafundo Africa link audit/1.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        results = await asyncio.gather(*[_check(client, semaphore, device) for device in visible])

    by_action: dict[str, int] = {}
    by_country: dict[str, dict[str, int]] = {}
    for result in results:
        by_action[result.action] = by_action.get(result.action, 0) + 1
        country = result.country or "Sans pays"
        by_country.setdefault(country, {})
        by_country[country][result.action] = by_country[country].get(result.action, 0) + 1

    failing = [result for result in results if not result.ok]
    strict_review = [
        result
        for result in failing
        if result.action in {"fix_or_hide", "retry_or_review"} or result.error in {"ConnectError", "timeout"}
    ]

    return {
        "checked": len(results),
        "ok": len(results) - len(failing),
        "failing": len(failing),
        "by_action": by_action,
        "by_country": by_country,
        "strict_review": len(strict_review),
        "strict_review_items": [asdict(item) for item in strict_review],
        "all_failing_items": [asdict(item) for item in failing],
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
