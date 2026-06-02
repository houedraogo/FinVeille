"""Corrige les residus francais non accentues dans les fiches visibles."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
TEXT_FIELDS = [
    "title",
    "short_description",
    "full_description",
    "eligibility_criteria",
    "eligible_expenses",
    "specific_conditions",
    "required_documents",
    "funding_details",
    "recurrence_notes",
]
JSON_FIELDS = ["content_sections_json", "ai_rewritten_sections_json", "decision_analysis"]

REPLACEMENTS = [
    ("opportunites", "opportunités"),
    ("opportunite", "opportunité"),
    ("eligibilite", "éligibilité"),
    ("eligibles", "éligibles"),
    ("criteres", "critères"),
    ("beneficiaires", "bénéficiaires"),
    ("demarche", "démarche"),
    ("presentation", "présentation"),
    ("verifier", "vérifier"),
    ("confirmer", "confirmer"),
    ("confirmees", "confirmées"),
    ("confirmes", "confirmés"),
    ("confirmee", "confirmée"),
    ("confirme", "confirmé"),
    ("etre", "être"),
    ("recevabilite", "recevabilité"),
    ("relayee", "relayée"),
    ("reperee", "repérée"),
    ("resume", "résumé"),
    ("decision", "décision"),
    ("securite", "sécurité"),
    ("donnees", "données"),
    ("donnee", "donnée"),
    ("creation", "création"),
    ("creer", "créer"),
    ("creant", "créant"),
    ("generer", "générer"),
    ("generatrices", "génératrices"),
    ("activites", "activités"),
    ("activite", "activité"),
    ("Tres", "Très"),
    ("tres", "très"),
    ("reelle", "réelle"),
    ("reels", "réels"),
    ("reel", "réel"),
    ("fenetre", "fenêtre"),
    ("cloture", "clôture"),
    ("depot", "dépôt"),
    ("depots", "dépôts"),
    ("depenses", "dépenses"),
    ("modalites", "modalités"),
    ("pieces", "pièces"),
    ("developpement", "développement"),
    ("developper", "développer"),
    ("developpent", "développent"),
    ("developpee", "développée"),
    ("developpe", "développé"),
    ("recurrentes", "récurrentes"),
    ("recurrente", "récurrente"),
    ("recurrent", "récurrent"),
    ("communiquee", "communiquée"),
    ("communique", "communiqué"),
    ("detaillees", "détaillées"),
    ("detailles", "détaillés"),
    ("detaille", "détaillé"),
    ("operationnelle", "opérationnelle"),
    ("operationnel", "opérationnel"),
    ("economiques", "économiques"),
    ("economique", "économique"),
    ("numeriques", "numériques"),
    ("numerique", "numérique"),
    ("energies", "énergies"),
    ("energie", "énergie"),
    ("ecosysteme", "écosystème"),
    ("capacite", "capacité"),
    ("priorites", "priorités"),
    ("priorite", "priorité"),
    ("maturite", "maturité"),
    ("selectionner", "sélectionner"),
    ("selection", "sélection"),
    ("editions", "éditions"),
    ("edition", "édition"),
    ("acces", "accès"),
    ("age", "âge"),
    ("prets", "prêts"),
    ("pret", "prêt"),
    ("elevee", "élevée"),
    ("eleves", "élevés"),
    ("eleve", "élevé"),
    ("privee", "privée"),
    ("prive", "privé"),
    ("equipes", "équipes"),
    ("equipe", "équipe"),
    ("diplomes", "diplômés"),
    ("cinema", "cinéma"),
    ("Equipement", "Équipement"),
    ("equipement", "équipement"),
    ("handicapees", "handicapées"),
    ("handicapee", "handicapée"),
    ("scolarisee", "scolarisée"),
    ("scolarise", "scolarisé"),
    ("alphabetisee", "alphabétisée"),
    ("alphabetise", "alphabétisé"),
    ("jusqu'a", "jusqu'à"),
    ("Details", "Détails"),
    ("Presentation", "Présentation"),
    ("Demarche", "Démarche"),
    ("priorisees", "priorisées"),
    ("priorises", "priorisés"),
    ("preparables", "préparables"),
    ("verifiees", "vérifiées"),
    ("verifiee", "vérifiée"),
    ("financees", "financées"),
    ("finances", "financés"),
    ("presentees", "présentées"),
    ("presentes", "présentés"),
    ("Region", "Région"),
    ("proposees", "proposées"),
    ("proposee", "proposée"),
    ("reperee", "repérée"),
    ("repere", "repéré"),
    ("detaillee", "détaillée"),
]

PATTERNS = [(re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE), target) for source, target in REPLACEMENTS]
RANGE_A_PATTERN = re.compile(r"(?<=\d)\s+a\s+(?=\d)", re.IGNORECASE)


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _fix_text(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    text = value
    for pattern, replacement in PATTERNS:
        text = pattern.sub(lambda match: _match_case(match.group(0), replacement), text)
    text = RANGE_A_PATTERN.sub(" à ", text)
    return text, text != value


def _fix_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _fix_text(value)
    if isinstance(value, list):
        changed = False
        items = []
        for item in value:
            new_item, item_changed = _fix_json(item)
            changed = changed or item_changed
            items.append(new_item)
        return items, changed
    if isinstance(value, dict):
        changed = False
        data = {}
        for key, item in value.items():
            if key == "key":
                new_item, item_changed = item, False
            else:
                new_item, item_changed = _fix_json(item)
            changed = changed or item_changed
            data[key] = new_item
        return data, changed
    return value, False


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed_items: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device))).scalars().all()

        for device in devices:
            if not _visible(device):
                continue
            changed_fields: list[str] = []
            for field in TEXT_FIELDS:
                value = getattr(device, field)
                fixed, changed = _fix_text(value)
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)
            for field in JSON_FIELDS:
                value = getattr(device, field)
                fixed, changed = _fix_json(value)
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)

            if changed_fields:
                device.updated_at = now
                changed_items.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "fields": sorted(set(changed_fields)),
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": len(changed_items), "items": changed_items[:120]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrige les residus francais non accentues visibles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
