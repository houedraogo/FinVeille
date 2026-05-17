from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
PUBLIC_STATUSES = {"open", "recurring"}


def _is_public(device: Device) -> bool:
    return device.validation_status in PUBLIC_VALIDATION_STATUSES and device.status in PUBLIC_STATUSES


def _burkina_filter(device: Device) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            device.title,
            device.country,
            device.region,
            device.zone,
            device.short_description,
            device.full_description,
            device.source_raw,
        )
    ).lower()
    return "burkina" in text or device.country == "Burkina Faso"


def _text_blob(device: Device) -> str:
    return " ".join(
        str(value or "")
        for value in (
            device.title,
            device.short_description,
            device.full_description,
            device.eligibility_criteria,
            device.funding_details,
            device.recurrence_notes,
            device.source_raw,
        )
    ).lower()


def _staleness_flags(device: Device) -> list[str]:
    text = _text_blob(device)
    flags: list[str] = []
    today = date.today()

    if device.status == "open" and device.close_date and device.close_date < today:
        flags.append("open_date_passee")
    if device.status == "recurring" and any(marker in text for marker in ("appel 2025", "edition 2025", "édition 2025", "2025 est expire", "2025 est expiré")):
        flags.append("recurrent_mais_appel_2025")
    if device.status == "recurring" and not device.close_date and any(marker in text for marker in ("appel a candidatures", "appel à candidatures", "date limite", "deadline")):
        flags.append("recurrent_avec_fenetre_probable")
    if "burkina24.com" in (device.source_url or "") or "digitalmagazine.bf" in (device.source_url or ""):
        flags.append("source_media_a_verifier")
    if device.device_type in {"autre", "institutional_project"}:
        flags.append("type_peu_actionnable")
    if not device.source_url:
        flags.append("source_absente")

    return flags


def _check_url(url: str | None) -> dict[str, Any]:
    if not url:
        return {"ok": False, "status": None, "error": "missing_url"}
    request = Request(
        url,
        method="GET",
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; KafundoQualityBot/1.0; +https://kafundo.com)",
            "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", None)
            return {"ok": bool(status and 200 <= status < 400), "status": status, "error": None}
    except HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc.reason)}
    except URLError as exc:
        return {"ok": False, "status": None, "error": str(exc.reason)}
    except Exception as exc:  # noqa: BLE001 - audit script should report every failure.
        return {"ok": False, "status": None, "error": str(exc)}


async def run(check_urls: bool = False) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES))
                .where(Device.status.in_(PUBLIC_STATUSES))
                .order_by(Device.status.asc(), Device.close_date.asc().nullslast(), Device.title.asc())
            )
        ).scalars().all()

        rows: list[dict[str, Any]] = []
        for device in devices:
            if not _burkina_filter(device):
                continue

            flags = _staleness_flags(device)
            url_status = _check_url(device.source_url) if check_urls else None
            if url_status and not url_status["ok"]:
                flags.append("url_non_fonctionnelle")

            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "organism": device.organism,
                    "source": device.source.name if device.source else None,
                    "country": device.country,
                    "type": device.device_type,
                    "status": device.status,
                    "close_date": device.close_date.isoformat() if device.close_date else None,
                    "source_url": device.source_url,
                    "flags": flags,
                    "url_status": url_status,
                    "short_description": (device.short_description or "")[:240],
                }
            )

        flagged = [row for row in rows if row["flags"]]
        return {
            "public_burkina_total": len(rows),
            "flagged_total": len(flagged),
            "flag_counts": {
                flag: sum(1 for row in flagged if flag in row["flags"])
                for flag in sorted({flag for row in flagged for flag in row["flags"]})
            },
            "flagged_rows": flagged,
            "all_rows": rows,
        }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Audit des opportunites Burkina visibles cote utilisateur.")
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(check_urls=args.check_urls)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
