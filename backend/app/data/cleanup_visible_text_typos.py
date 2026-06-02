from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


VISIBLE_STATUSES = {"approved", "validated", "auto_published"}
VISIBLE_DECISIONS = {None, "publish", "publish_with_caution"}
FIELDS = [
    "title",
    "short_description",
    "full_description",
    "eligibility_criteria",
    "specific_conditions",
    "required_documents",
    "funding_details",
    "recurrence_notes",
]

REPLACEMENTS = {
    "L'A 2 D": "L'A2D",
    "A 2 D Facility": "A2D Facility",
    "àctif": "actif",
    "a structurer": "à structurer",
    "a transformer": "à transformer",
    "a fort potentiel": "à fort potentiel",
    "a se renforcer": "à se renforcer",
    "a vérifier": "à vérifier",
    "a confirmer": "à confirmer",
    "a préparer": "à préparer",
    "a accéder": "à accéder",
    "chaine de valeur": "chaîne de valeur",
    "chaines de valeur": "chaînes de valeur",
    "chaine du cajou": "chaîne du cajou",
    "idee": "idée",
    "ameliorent": "améliorent",
    "donnees": "données",
    "equitables": "équitables",
    "resilients": "résilients",
    "cooperatives": "coopératives",
    "d'entree": "d'entrée",
    "porte d'entree": "porte d'entrée",
    "acceder": "accéder",
    "Developpement": "Développement",
    "developpement": "développement",
    "developpent": "développent",
    "recurrent": "récurrent",
    "recurrente": "récurrente",
    "cloture": "clôture",
    "confirmes": "confirmés",
    "confirmees": "confirmées",
    "economique": "économique",
    "economiques": "économiques",
    "regionale": "régionale",
    "regional": "régional",
    "academique": "académique",
    "age limite": "âge limite",
    "utilise correspond": "utilisé correspond",
    "financement recherche": "financement recherché",
}


def _replace_text(value: str | None) -> tuple[str | None, bool]:
    if not value:
        return value, False
    new_value = value
    for before, after in REPLACEMENTS.items():
        new_value = new_value.replace(before, after)
    return new_value, new_value != value


def _replace_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _replace_text(value)
    if isinstance(value, list):
        changed = False
        new_items = []
        for item in value:
            new_item, item_changed = _replace_json(item)
            changed = changed or item_changed
            new_items.append(new_item)
        return new_items, changed
    if isinstance(value, dict):
        changed = False
        new_dict = {}
        for key, item in value.items():
            new_item, item_changed = _replace_json(item)
            changed = changed or item_changed
            new_dict[key] = new_item
        return new_dict, changed
    return value, False


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed_items: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    Device.validation_status.in_(VISIBLE_STATUSES),
                    Device.status.in_(["open", "recurring"]),
                )
            )
        ).scalars().all()

        for device in devices:
            if device.user_quality_decision not in VISIBLE_DECISIONS:
                continue
            changed_fields: list[str] = []
            for field in FIELDS:
                value = getattr(device, field)
                new_value, changed = _replace_text(value)
                if changed:
                    setattr(device, field, new_value)
                    changed_fields.append(field)

            for field in ["content_sections_json", "ai_rewritten_sections_json"]:
                value = getattr(device, field)
                new_value, changed = _replace_json(value)
                if changed:
                    setattr(device, field, new_value)
                    changed_fields.append(field)

            if changed_fields:
                device.updated_at = now
                changed_items.append({"id": str(device.id), "title": device.title, "fields": sorted(set(changed_fields))})

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": len(changed_items), "items": changed_items[:50]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrige les coquilles visibles sans changer le fond des fiches.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
