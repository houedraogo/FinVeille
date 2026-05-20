from __future__ import annotations

import argparse
import asyncio
import json
import ssl
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


def _norm(value: str | None) -> str:
    return (
        (value or "")
        .lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("’", "'")
        .replace("Ã©", "e")
        .replace("Ã¨", "e")
        .replace("Ãª", "e")
        .replace("Ã ", "a")
        .replace("Ã§", "c")
        .replace("Ã´", "o")
        .replace("â€™", "'")
    )


def _device_blob(device: Device) -> str:
    return _norm(
        " ".join(
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
        )
    )


def _targets_country(device: Device, country_terms: list[str]) -> bool:
    blob = _device_blob(device)
    return any(_norm(term) in blob for term in country_terms)


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Sans source"


def _flags(device: Device) -> list[str]:
    blob = _device_blob(device)
    flags: list[str] = []
    today = date.today()
    source_url = device.source_url or ""

    if device.status == "open" and device.close_date and device.close_date < today:
        flags.append("open_date_passee")
    if device.status == "open" and not device.close_date and not device.is_recurring:
        flags.append("open_sans_date")
    if device.device_type in {"autre", "institutional_project"}:
        flags.append("type_peu_actionnable")
    if any(domain in source_url for domain in ("burkina24.com", "digitalmagazine.bf", "startupmedias.africa")):
        flags.append("source_indirecte_media")
    if not source_url:
        flags.append("source_absente")
    if device.status == "recurring" and not device.close_date and any(
        marker in blob for marker in ("appel a candidatures", "appel a projets", "date limite", "deadline")
    ):
        flags.append("recurrent_avec_fenetre_probable")
    if "les criteres detailles ne sont pas" in blob or "doivent etre confirm" in blob:
        flags.append("texte_generique")

    return flags


def _check_url(url: str | None) -> dict[str, Any]:
    if not url:
        return {"ok": False, "status": None, "error": "missing_url"}
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 KafundoQualityAudit/1.0"})
        with urlopen(req, timeout=12) as response:
            return {"ok": 200 <= response.status < 400, "status": response.status, "error": None, "final_url": response.geturl()}
    except HTTPError as exc:
        return {"ok": 200 <= exc.code < 400, "status": exc.code, "error": str(exc), "final_url": url}
    except (URLError, TimeoutError, ssl.SSLError, Exception) as exc:
        return {"ok": False, "status": None, "error": str(exc), "final_url": url}


async def run(country_terms: list[str], check_urls: bool) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Device)
            .options(selectinload(Device.source))
            .where(Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES), Device.status.in_(PUBLIC_STATUSES))
            .order_by(Device.status.asc(), Device.close_date.asc().nulls_last(), Device.title.asc())
        )
        devices = [device for device in result.scalars().all() if _targets_country(device, country_terms)]

    rows: list[dict[str, Any]] = []
    flagged_rows: list[dict[str, Any]] = []
    flag_counts: dict[str, int] = {}
    for device in devices:
        flags = _flags(device)
        url_status = _check_url(device.source_url) if check_urls else None
        if url_status and not url_status["ok"]:
            flags.append("url_non_fonctionnelle")
        for flag in set(flags):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        row = {
            "id": str(device.id),
            "title": device.title,
            "organism": device.organism,
            "source": _source_name(device),
            "country": device.country,
            "type": device.device_type,
            "status": device.status,
            "close_date": device.close_date.isoformat() if device.close_date else None,
            "source_url": device.source_url,
            "flags": flags,
            "url_status": url_status,
            "short_description": (device.short_description or "")[:240],
        }
        rows.append(row)
        if flags:
            flagged_rows.append(row)

    return {
        "country_terms": country_terms,
        "public_total": len(rows),
        "flagged_total": len(flagged_rows),
        "flag_counts": flag_counts,
        "flagged_rows": flagged_rows,
        "all_rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+")
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.terms, args.check_urls)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
