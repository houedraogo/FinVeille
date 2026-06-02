"""Corrige les points bloquants remontes par l'audit complet des fiches."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import compute_completeness, generate_slug, normalize_title


CARBURANT_ID = "a6d02f0f-5fdf-411c-8aae-560650b57dca"
MOJIBAKE_IDS = {
    "272b33b8-f391-4a11-9c25-ebea59103e03",
    "7d3d6e27-54e5-497f-8f8c-b7258680a774",
}
JANGGO_KEEP_ID = "4f71c640-3f81-40eb-8f19-be71305c72cf"
JANGGO_HIDE_ID = "790aa9bd-f663-44bb-8b77-7313527bf81e"

IMPOTS_ACTUALITE_URL = "https://www.impots.gouv.fr/actualite/carburants-aide-pour-les-travailleurs-grands-rouleurs"


def _append_tags(device: Device, *tags: str) -> None:
    current = list(device.tags or [])
    for tag in tags:
        if tag not in current:
            current.append(tag)
    device.tags = current[:24]


def _fix_text(value: str | None) -> str | None:
    if value is None:
        return None
    replacements = {
        "Ã©": "é",
        "Ã¨": "è",
        "Ãª": "ê",
        "Ã«": "ë",
        "Ã ": "à",
        "Ã¢": "â",
        "Ã´": "ô",
        "Ã®": "î",
        "Ã¯": "ï",
        "Ã§": "ç",
        "Ã¹": "ù",
        "Ã»": "û",
        "Ã‰": "É",
        "Ã€": "À",
        " Ã ": " à ",
        "Â·": "·",
        "Â«": "«",
        "Â»": "»",
        "Â°": "°",
        "Â": "",
        "â€™": "'",
        "â€œ": '"',
        "â€�": '"',
        "â€“": "-",
        "â€”": "-",
        "â€¦": "...",
        "Å“": "œ",
    }
    text = value
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _fix_json(value: Any) -> Any:
    if isinstance(value, str):
        return _fix_text(value)
    if isinstance(value, list):
        return [_fix_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _fix_json(item) for key, item in value.items()}
    return value


def _refresh_scores(device: Device) -> None:
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    device.completeness_score = compute_completeness(payload)
    device.title_normalized = normalize_title(device.title)
    device.slug = device.slug or generate_slug(device.title)
    device.updated_at = datetime.now(timezone.utc)


async def _get_or_create_impots_source(db) -> Source:
    source = (
        await db.execute(select(Source).where(Source.name == "impots.gouv.fr - aide carburant grands rouleurs"))
    ).scalar_one_or_none()
    if source:
        source.url = IMPOTS_ACTUALITE_URL
        source.consecutive_errors = 0
        source.last_success_at = datetime.now(timezone.utc)
        source.updated_at = datetime.now(timezone.utc)
        return source

    source = Source(
        name="impots.gouv.fr - aide carburant grands rouleurs",
        organism="Direction générale des Finances publiques",
        country="France",
        region="France",
        source_type="institution_publique",
        level=1,
        url=IMPOTS_ACTUALITE_URL,
        collection_mode="manual",
        check_frequency="weekly",
        reliability=5,
        category="public",
        is_active=True,
        consecutive_errors=0,
        last_success_at=datetime.now(timezone.utc),
        config={"source_kind": "official_news_page", "market": "france_aide_carburant"},
        notes="Page officielle impots.gouv.fr de l'aide carburant grands rouleurs 2026.",
    )
    db.add(source)
    await db.flush()
    return source


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {
        "carburant_updated": False,
        "mojibake_fixed": [],
        "janngo_hidden_duplicate": False,
    }

    async with AsyncSessionLocal() as db:
        impots_source = await _get_or_create_impots_source(db)

        carburant = (
            await db.execute(select(Device).where(Device.id == CARBURANT_ID))
        ).scalar_one_or_none()
        if carburant:
            carburant.source_id = impots_source.id
            carburant.source_url = IMPOTS_ACTUALITE_URL
            carburant.source_raw = (
                "Page officielle impots.gouv.fr: aide carburant grands rouleurs 2026, "
                "simulateur d'éligibilité et formulaire depuis l'espace personnel impots.gouv.fr."
            )
            carburant.short_description = (
                "L'indemnité carburant grands rouleurs est une aide forfaitaire destinée aux travailleurs "
                "modestes qui utilisent leur véhicule personnel à des fins professionnelles et parcourent "
                "des distances importantes."
            )
            carburant.full_description = (
                "Cette fiche renvoie vers la page officielle impots.gouv.fr consacrée à l'aide carburant "
                "pour les travailleurs dits grands rouleurs. La page détaille les conditions d'éligibilité, "
                "le simulateur et la démarche à effectuer depuis l'espace personnel impots.gouv.fr."
            )
            carburant.specific_conditions = (
                "Vérifier l'éligibilité avec le simulateur officiel, puis déposer la demande depuis "
                "l'espace personnel impots.gouv.fr lorsque le formulaire est ouvert."
            )
            _append_tags(carburant, "source:official_impots", "audit:dead_link_fixed")
            _refresh_scores(carburant)
            result["carburant_updated"] = True

        for device in (
            await db.execute(select(Device).where(Device.id.in_(MOJIBAKE_IDS)))
        ).scalars().all():
            changed = False
            for field in (
                "title",
                "organism",
                "country",
                "region",
                "zone",
                "short_description",
                "full_description",
                "eligibility_criteria",
                "eligible_expenses",
                "specific_conditions",
                "required_documents",
                "funding_details",
                "recurrence_notes",
                "source_raw",
                "auto_summary",
            ):
                current = getattr(device, field)
                fixed = _fix_text(current)
                if fixed != current:
                    setattr(device, field, fixed)
                    changed = True
            for field in ("content_sections_json", "ai_rewritten_sections_json", "decision_analysis"):
                current = getattr(device, field)
                fixed = _fix_json(current)
                if fixed != current:
                    setattr(device, field, fixed)
                    changed = True
            if changed:
                _append_tags(device, "audit:mojibake_fixed")
                _refresh_scores(device)
                result["mojibake_fixed"].append({"id": str(device.id), "title": device.title})

        keep = (
            await db.execute(select(Device).where(Device.id == JANGGO_KEEP_ID))
        ).scalar_one_or_none()
        duplicate = (
            await db.execute(select(Device).where(Device.id == JANGGO_HIDE_ID))
        ).scalar_one_or_none()
        if keep and duplicate:
            _append_tags(keep, "dedupe:kept_visible")
            _refresh_scores(keep)
            duplicate.validation_status = "admin_only"
            duplicate.user_quality_decision = "admin_only"
            duplicate.user_quality_score = min(duplicate.user_quality_score or 55, 55)
            duplicate.status = "standby"
            duplicate.decision_analysis = {
                **(duplicate.decision_analysis or {}),
                "duplicate_of": str(keep.id),
                "quality_action": "hide_duplicate",
                "quality_action_at": datetime.now(timezone.utc).isoformat(),
            }
            _append_tags(duplicate, "visibility:admin_only", "dedupe:hidden_duplicate", "duplicate:janngo_capital")
            _refresh_scores(duplicate)
            result["janngo_hidden_duplicate"] = True

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
