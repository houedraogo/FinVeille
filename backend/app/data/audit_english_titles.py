from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}

ENGLISH_MARKERS = {
    "application",
    "applications",
    "apply",
    "award",
    "business",
    "call",
    "cohort",
    "development",
    "education",
    "enterprise",
    "fellowship",
    "for",
    "fund",
    "funding",
    "grant",
    "grants",
    "innovation",
    "network",
    "open",
    "opportunity",
    "program",
    "programme",
    "project",
    "research",
    "support",
    "the",
    "women",
}

FRENCH_MARKERS = {
    "accompagnement",
    "aide",
    "appel",
    "appui",
    "afrique",
    "candidatures",
    "challenge",
    "concours",
    "cofinancement",
    "digitale",
    "energie",
    "entrepreneurs",
    "entreprises",
    "formation",
    "financement",
    "fonds",
    "initiative",
    "investissement",
    "jeunes",
    "mondial",
    "numerique",
    "participation",
    "prix",
    "programme",
    "projet",
    "startup",
    "startups",
    "subvention",
    "subventions",
    "transition",
}

AFRICA_HINTS = {
    "africa",
    "afrique",
    "benin",
    "burkina",
    "cameroun",
    "cote d ivoire",
    "ghana",
    "guinee",
    "ivoire",
    "kenya",
    "madagascar",
    "mali",
    "niger",
    "nigeria",
    "ouest",
    "rwanda",
    "senegal",
    "togo",
    "tunisie",
}


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("'", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"[a-z]+", _norm(value)))


def looks_english_title(title: str | None) -> bool:
    tokens = _tokens(title)
    if not tokens:
        return False
    english_hits = len(tokens & ENGLISH_MARKERS)
    french_hits = len(tokens & FRENCH_MARKERS)
    normalized = _norm(title)

    # Brand names often contain English words while the title is already usable in French.
    brand_safe_patterns = (
        r"\bprogramme .*(fellowship|challenge|fund|greencatalyst)\b",
        r"\bfonds .*(foundation|fund)\b",
        r"\bprix .*(awards|award)\b",
        r"\bpeeb awards\b",
        r"\bafd digital challenge\b",
        r"\bgsma innovation fund\b",
        r"\bfid fund for innovation in development\b",
        r"\bechoing green fellowship\b",
        r"\brainer arnhold fellowship\b",
    )
    if french_hits >= 1 and any(re.search(pattern, normalized) for pattern in brand_safe_patterns):
        return False
    if normalized.startswith("programme ") and french_hits >= 1 and english_hits <= 2:
        return False

    if english_hits >= 2 and english_hits > french_hits:
        return True
    patterns = (
        r"\b(call for applications|applications are open|funding opportunity|open for applications)\b",
        r"\b(grants?|awards?|fellowship|challenge|program|project)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns) and french_hits <= 1


def is_africa_related(device: Device) -> bool:
    blob = " ".join(
        [
            device.country or "",
            device.region or "",
            device.zone or "",
            device.organism or "",
            " ".join(device.keywords or []),
            " ".join(device.tags or []),
            device.title or "",
        ]
    )
    normalized = _norm(blob)
    return any(hint in normalized for hint in AFRICA_HINTS)


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Import manuel / historique"


async def run(sample_limit: int = 30) -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
                .order_by(Device.created_at.desc())
            )
        ).scalars().all()

        by_source: dict[str, dict[str, int]] = {}
        public_samples = []
        admin_samples = []

        totals = {
            "total": len(devices),
            "public_total": 0,
            "admin_only_total": 0,
            "africa_total": 0,
            "english_title_total": 0,
            "public_english_title_total": 0,
            "africa_english_title_total": 0,
            "africa_public_english_title_total": 0,
        }

        for device in devices:
            source_name = _source_name(device)
            bucket = by_source.setdefault(
                source_name,
                {
                    "total": 0,
                    "public_total": 0,
                    "admin_only_total": 0,
                    "english_titles": 0,
                    "public_english_titles": 0,
                    "africa_english_titles": 0,
                    "africa_public_english_titles": 0,
                },
            )

            is_public = device.validation_status in PUBLIC_VALIDATION_STATUSES
            is_admin_only = device.validation_status == "admin_only"
            is_africa = is_africa_related(device)
            is_english = looks_english_title(device.title)

            bucket["total"] += 1
            if is_public:
                totals["public_total"] += 1
                bucket["public_total"] += 1
            if is_admin_only:
                totals["admin_only_total"] += 1
                bucket["admin_only_total"] += 1
            if is_africa:
                totals["africa_total"] += 1
            if is_english:
                totals["english_title_total"] += 1
                bucket["english_titles"] += 1
            if is_public and is_english:
                totals["public_english_title_total"] += 1
                bucket["public_english_titles"] += 1
            if is_africa and is_english:
                totals["africa_english_title_total"] += 1
                bucket["africa_english_titles"] += 1
            if is_africa and is_public and is_english:
                totals["africa_public_english_title_total"] += 1
                bucket["africa_public_english_titles"] += 1
                if len(public_samples) < sample_limit:
                    public_samples.append(
                        {
                            "id": str(device.id),
                            "title": device.title,
                            "source": source_name,
                            "country": device.country,
                            "status": device.status,
                            "device_type": device.device_type,
                            "validation_status": device.validation_status,
                        }
                    )
            elif is_africa and is_english and len(admin_samples) < sample_limit:
                admin_samples.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "source": source_name,
                        "country": device.country,
                        "status": device.status,
                        "device_type": device.device_type,
                        "validation_status": device.validation_status,
                    }
                )

        source_rows = [
            {"source": source, **values}
            for source, values in sorted(
                by_source.items(),
                key=lambda item: (
                    item[1]["africa_public_english_titles"],
                    item[1]["public_english_titles"],
                    item[1]["english_titles"],
                    item[1]["total"],
                ),
                reverse=True,
            )
            if values["english_titles"] > 0
        ]

        validation_rows = (
            await db.execute(
                select(Device.validation_status, func.count(Device.id))
                .where(Device.validation_status != "rejected")
                .group_by(Device.validation_status)
                .order_by(func.count(Device.id).desc())
            )
        ).all()

        return {
            "audit_date": date.today().isoformat(),
            **totals,
            "validation_statuses": [
                {"status": status, "count": int(count)} for status, count in validation_rows
            ],
            "top_sources": source_rows[:20],
            "public_africa_english_title_samples": public_samples,
            "admin_only_africa_english_title_samples": admin_samples,
        }


def main() -> None:
    result = asyncio.run(run(sample_limit=50))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
