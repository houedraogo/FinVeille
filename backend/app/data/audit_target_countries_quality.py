from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device


TARGET_TERMS = (
    "benin",
    "bénin",
    "burkina",
    "cote d'ivoire",
    "côte d'ivoire",
    "cote d ivoire",
    "afrique de l'ouest",
    "uemoa",
)


def _norm(value: str | None) -> str:
    text = (value or "").lower()
    return (
        text.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("’", "'")
    )


def _targets_device(device: Device) -> bool:
    blob = " ".join(
        [
            device.country or "",
            device.region or "",
            device.zone or "",
            " ".join(device.keywords or []),
        ]
    )
    normalized = _norm(blob)
    return any(_norm(term) in normalized for term in TARGET_TERMS)


def _text(device: Device) -> str:
    return " ".join(
        [
            device.title or "",
            device.short_description or "",
            device.full_description or "",
            device.eligibility_criteria or "",
            device.funding_details or "",
        ]
    )


def _looks_english(text: str) -> bool:
    normalized = f" {_norm(text)} "
    markers = [
        " the ",
        " and ",
        " funding ",
        " applicants ",
        " deadline ",
        " project ",
        " business ",
        " women ",
        " entrepreneurs ",
    ]
    french_markers = [" le ", " la ", " les ", " des ", " pour ", " avec ", " projet "]
    return sum(marker in normalized for marker in markers) >= 3 and sum(marker in normalized for marker in french_markers) < 3


def _issues(device: Device) -> list[str]:
    issues: list[str] = []
    full_len = len(device.full_description or "")
    short_len = len(device.short_description or "")
    eligibility_len = len(device.eligibility_criteria or "")
    funding_len = len(device.funding_details or "")
    text = _text(device)
    normalized = _norm(text)

    if device.device_type in {"autre", "", None}:
        issues.append("type_a_qualifier")
    if full_len < 180 and short_len < 120:
        issues.append("description_pauvre")
    if eligibility_len < 60:
        issues.append("criteres_pauvres")
    if funding_len < 50 and not device.amount_max:
        issues.append("montant_ou_avantage_pauvre")
    if not device.close_date and not device.is_recurring and device.status == "open":
        issues.append("open_sans_date")
    if device.validation_status not in {"auto_published", "approved", "validated"}:
        issues.append("non_publie_ou_a_revoir")
    if _looks_english(text):
        issues.append("texte_anglais")
    if re.search(r"\b(etat|ministre|ministere|commune|mairie|collectivite|institution publique)\b", normalized):
        if not re.search(r"\b(entreprise|pme|startup|entrepreneur|association|ong|cooperative)\b", normalized):
            issues.append("beneficiaire_institutionnel")
    if "les criteres detailles ne sont pas" in normalized or "doivent etre confirm" in normalized:
        issues.append("texte_generique")

    return issues


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

    target_devices = [device for device in devices if _targets_device(device)]
    issue_counts: Counter[str] = Counter()
    source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict] = []

    for device in target_devices:
        issues = _issues(device)
        if not issues:
            continue
        source_name = device.source.name if device.source else "Sans source"
        issue_counts.update(issues)
        source_counts[source_name].update(issues)
        rows.append(
            {
                "id": str(device.id),
                "title": device.title,
                "source": source_name,
                "country": device.country,
                "region": device.region,
                "status": device.status,
                "type": device.device_type,
                "issues": issues,
                "full_len": len(device.full_description or ""),
                "eligibility_len": len(device.eligibility_criteria or ""),
                "funding_len": len(device.funding_details or ""),
            }
        )

    by_source = [
        {"source": source, "count": sum(counter.values()), "issues": dict(counter)}
        for source, counter in source_counts.items()
    ]
    by_source.sort(key=lambda item: item["count"], reverse=True)

    return {
        "target_total": len(target_devices),
        "problem_total": len(rows),
        "issue_counts": dict(issue_counts),
        "sources": by_source[:30],
        "items": rows[:120],
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
