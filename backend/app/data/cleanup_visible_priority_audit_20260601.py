"""Corrections prioritaires issues de l'audit visible du 2026-06-01."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


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

ACCENT_TARGET_IDS = {
    UUID("4e70bd3d-6380-4735-8b35-8628e9d087f1"),
    UUID("a5de7f58-f384-483e-9453-b9e1ba33f009"),
    UUID("bcf13ec9-df99-4c79-962c-f836df1c92a6"),
    UUID("8c41722e-e123-4ca7-8b1d-932cf2702b24"),
    UUID("71bdc132-5463-44de-9fc0-3c7c58c2f55d"),
    UUID("c93e1f24-e561-4f0c-8ad8-ac2661928b2c"),
}

HORIZON_UPDATES: dict[UUID, dict[str, Any]] = {
    UUID("65252a7c-3db2-4da9-9939-bcd709e3f14b"): {
        "source_url": "https://www.horizon-europe.gouv.fr/programme-de-travail-2026-27-cluster-6-bio-environnement-34432",
        "funding_details": (
            "Subvention Horizon Europe selon le topic retenu. Les dates et budgets exacts doivent être vérifiés "
            "sur le topic Funding & Tenders correspondant avant candidature."
        ),
        "recurrence_notes": "Source officielle mise à jour vers le programme de travail Cluster 6 2026-2027.",
    },
    UUID("8ff23419-8daf-4b03-8283-182021d86776"): {
        "source_url": "https://www.horizon-europe.gouv.fr/cluster-2-shs",
        "funding_details": (
            "Subvention Horizon Europe selon le topic Culture, Creativity and Inclusive Society retenu. Les budgets "
            "et dates exacts doivent être vérifiés sur la fiche topic officielle avant dépôt."
        ),
        "recurrence_notes": "Source officielle conservée sur la page Cluster 2 / SHS et topics 2027 associés.",
    },
    UUID("1cc64dda-7ad2-492c-a5b1-2abfa0382122"): {
        "source_url": "https://www.horizon-europe.gouv.fr/guide-des-appels-cluster-3-2026-43406",
        "funding_details": (
            "Subvention Horizon Europe selon le topic Cluster sécurité retenu. La date limite et le budget doivent "
            "être vérifiés dans le topic Funding & Tenders avant candidature."
        ),
        "recurrence_notes": "Ancienne page WP 2021-2022 remplacée par le guide officiel Cluster 3 2026.",
    },
}

AMOUNT_UPDATES: dict[UUID, dict[str, Any]] = {
    UUID("5e506cc2-16a5-4265-a3f9-b35860de2332"): {"amount_min": 100000, "amount_max": 100000, "currency": "USD"},
    UUID("d68a9c02-55fe-496a-909d-70253eef0b59"): {"amount_min": 5000, "amount_max": 50000, "currency": "EUR"},
    UUID("220876ab-a515-4210-aadc-6ed5eeed6a57"): {"amount_max": 200000, "currency": "USD"},
    UUID("12bbce7f-10f8-46ff-98a5-aabf1f96ac2b"): {"amount_min": 15000, "amount_max": 45000, "currency": "CHF"},
    UUID("89c32f02-88f6-483b-9d32-7703b70236b1"): {"funding_rate": Decimal("10")},
    UUID("463be3ee-b11c-4a8f-8056-a3ef160ab4ee"): {"funding_rate": Decimal("75")},
    UUID("a61fddd8-b209-4177-a789-90a4b6a95621"): {"amount_max": 100000000, "currency": "EUR"},
    UUID("b3196197-7139-40fc-b17c-df0932e598cd"): {"funding_rate": Decimal("80")},
    UUID("ff84892c-530e-4212-87b0-ab8e027dd8d2"): {"funding_rate": Decimal("50")},
    UUID("cd41614b-5745-477f-b8c7-b0df7a7475cc"): {"funding_rate": Decimal("53.55")},
    UUID("2c558786-6bec-4ca8-a9be-3e0e4b627798"): {"funding_rate": Decimal("30")},
    UUID("45fd53fe-9c14-4ac9-9286-784c90e360ec"): {"funding_rate": Decimal("100")},
    UUID("d8ef94c9-85de-4b0d-b317-f1cb1ac6f3ee"): {"funding_rate": Decimal("50")},
    UUID("c3f77b05-c657-4f8d-a838-66507d040312"): {"amount_min": 50000, "amount_max": 800000, "currency": "EUR"},
    UUID("ccc36850-9ee1-4710-9a50-9add2d7fea85"): {"amount_min": 3000000, "amount_max": 5000000, "currency": "EUR"},
    UUID("51ba3117-edaa-495d-a71e-ecf9dead07df"): {"funding_rate": Decimal("100")},
    UUID("4893bc20-8fbe-4d7b-b0e9-fabf32061914"): {"amount_min": 300000, "amount_max": 1000000, "currency": "EUR"},
    UUID("7a84000a-5fb4-4f54-adfc-22974b91d1e5"): {"funding_rate": Decimal("60")},
    UUID("21e648c4-2b26-4c77-bb66-8450eeda2c1d"): {"amount_min": 1000, "amount_max": 8000, "currency": "EUR"},
    UUID("5113afed-3791-4793-a765-7593f14c6baf"): {"amount_min": 2000000, "funding_rate": Decimal("50"), "currency": "EUR"},
    UUID("676dc9ac-7dbe-450e-9f3c-11e4c019d557"): {"amount_min": 2000000, "funding_rate": Decimal("50"), "currency": "EUR"},
    UUID("f582ad91-a8d2-419d-bf77-3fde790e8bf6"): {"amount_max": 200000, "currency": "GBP"},
    UUID("26f2bbd7-45de-4c5c-877f-39e019d3a183"): {"amount_max": 10000, "currency": "USD"},
}

NON_AMOUNT_FUNDING_DETAILS: dict[UUID, str] = {
    UUID("f6b6c3c6-1a73-478a-8042-4750f6d02aa9"): (
        "L'avantage principal est un accompagnement d'accélération: mentorat, préparation au développement, "
        "exposition auprès de partenaires et accès potentiel à un réseau santé/innovation. Aucun montant "
        "financier standard n'est communiqué dans la fiche visible."
    ),
    UUID("a5de7f58-f384-483e-9453-b9e1ba33f009"): (
        "L'avantage principal est l'accompagnement stratégique et opérationnel. Le programme peut donner accès "
        "à de l'expertise, du mentorat, des contacts investisseurs ou des services partenaires; tout financement "
        "direct doit être confirmé auprès de la BERD ou sur la page source."
    ),
    UUID("0a3a5455-c005-41c1-a86e-75d0aeadc57f"): (
        "Le programme prévoit le financement de micro-projets individuels et collectifs. Les montants unitaires, "
        "taux de cofinancement et modalités exactes doivent être vérifiés dans les avis ou auprès des structures "
        "locales du programme."
    ),
    UUID("eeff2af6-83c9-4467-8704-3fa58780d845"): (
        "Subvention AECF selon appel. La dernière fenêtre identifiée est close; surveiller les prochains appels "
        "avant toute candidature."
    ),
    UUID("65252a7c-3db2-4da9-9939-bcd709e3f14b"): (
        "Subvention Horizon Europe selon le topic retenu. Les dates et budgets exacts doivent être vérifiés "
        "sur le topic Funding & Tenders correspondant avant candidature."
    ),
    UUID("8ff23419-8daf-4b03-8283-182021d86776"): (
        "Subvention Horizon Europe selon le topic Culture, Creativity and Inclusive Society retenu. Les budgets "
        "et dates exacts doivent être vérifiés sur la fiche topic officielle avant dépôt."
    ),
    UUID("1cc64dda-7ad2-492c-a5b1-2abfa0382122"): (
        "Subvention Horizon Europe selon le topic Cluster sécurité retenu. La date limite et le budget doivent "
        "être vérifiés dans le topic Funding & Tenders avant candidature."
    ),
    UUID("30c5b006-1c9d-4521-a398-2f38408dc95a"): (
        "Bpifrance achète le matériel à la place de l'entreprise et le loue pendant la période du contrat. "
        "Plusieurs formules peuvent être étudiées avec l'entreprise bénéficiaire selon le matériel et le montage."
    ),
    UUID("e2260502-40c3-46a4-b940-bc1f327f6e6d"): (
        "Subvention UNESCO selon l'appel annuel. La dernière fenêtre identifiée est close; surveiller le prochain "
        "appel avant toute candidature."
    ),
}

HIDE_DEAD_LINK_IDS = {
    UUID("a6d02f0f-5fdf-411c-8aae-560650b57dca"),
}

TEXT_REPLACEMENTS = [
    (re.compile(r"\ba verifier\b", re.IGNORECASE), "à vérifier"),
    (re.compile(r"\ba confirmer\b", re.IGNORECASE), "à confirmer"),
    (re.compile(r"\ba preparer\b", re.IGNORECASE), "à préparer"),
    (re.compile(r"\ba deposer\b", re.IGNORECASE), "à déposer"),
    (re.compile(r"\ba publier\b", re.IGNORECASE), "à publier"),
    (re.compile(r"\bopportunite\b", re.IGNORECASE), "opportunité"),
    (re.compile(r"\beligibilite\b", re.IGNORECASE), "éligibilité"),
    (re.compile(r"\bcriteres\b", re.IGNORECASE), "critères"),
    (re.compile(r"\bdemarche\b", re.IGNORECASE), "démarche"),
    (re.compile(r"\bpresentation\b", re.IGNORECASE), "présentation"),
    (re.compile(r"\bverifier\b", re.IGNORECASE), "vérifier"),
    (re.compile(r"\bconfirmees\b", re.IGNORECASE), "confirmées"),
    (re.compile(r"\betre\b", re.IGNORECASE), "être"),
    (re.compile(r"\bdecision\b", re.IGNORECASE), "décision"),
    (re.compile(r"\bcloture\b", re.IGNORECASE), "clôture"),
    (re.compile(r"\bcommuniquee\b", re.IGNORECASE), "communiquée"),
    (re.compile(r"\bidentifiee\b", re.IGNORECASE), "identifiée"),
    (re.compile(r"\bannoncee\b", re.IGNORECASE), "annoncée"),
    (re.compile(r"\bsubventionnee\b", re.IGNORECASE), "subventionnée"),
    (re.compile(r"\bannuel\b", re.IGNORECASE), "annuel"),
    (re.compile(r"\bànnuel\b", re.IGNORECASE), "annuel"),
    (re.compile(r"\bspeciale\b", re.IGNORECASE), "spéciale"),
    (re.compile(r"\baccelerer\b", re.IGNORECASE), "accélérer"),
    (re.compile(r"\bcomplementaire\b", re.IGNORECASE), "complémentaire"),
    (re.compile(r"\bevolution\b", re.IGNORECASE), "évolution"),
    (re.compile(r"\bgeneralement\b", re.IGNORECASE), "généralement"),
]


def _fix_text(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    text = value
    for pattern, replacement in TEXT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text, text != value


def _fix_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _fix_text(value)
    if isinstance(value, list):
        changed = False
        output = []
        for item in value:
            fixed, item_changed = _fix_json(item)
            output.append(fixed)
            changed = changed or item_changed
        return output, changed
    if isinstance(value, dict):
        changed = False
        output = {}
        for key, item in value.items():
            fixed, item_changed = _fix_json(item)
            output[key] = fixed
            changed = changed or item_changed
        return output, changed
    return value, False


def _add_tag(device: Device, tag: str) -> None:
    tags = list(device.tags or [])
    if tag not in tags:
        tags.append(tag)
    device.tags = tags[:24]


async def run() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    target_ids = (
        set(ACCENT_TARGET_IDS)
        | set(HORIZON_UPDATES)
        | set(AMOUNT_UPDATES)
        | set(NON_AMOUNT_FUNDING_DETAILS)
        | HIDE_DEAD_LINK_IDS
    )
    changes: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(target_ids)))).scalars().all()
        by_id = {device.id: device for device in devices}

        for device_id, updates in HORIZON_UPDATES.items():
            device = by_id.get(device_id)
            if not device:
                continue
            changed_fields = []
            for field, value in updates.items():
                if getattr(device, field) != value:
                    setattr(device, field, value)
                    changed_fields.append(field)
            if changed_fields:
                _add_tag(device, "audit:horizon_source_20260601")
                device.updated_at = now
                changes.append({"id": str(device.id), "title": device.title, "fields": changed_fields})

        for device_id, updates in AMOUNT_UPDATES.items():
            device = by_id.get(device_id)
            if not device:
                continue
            changed_fields = []
            for field, value in updates.items():
                current = getattr(device, field)
                if current != value:
                    setattr(device, field, value)
                    changed_fields.append(field)
            if changed_fields:
                _add_tag(device, "audit:amount_structured_20260601")
                device.updated_at = now
                changes.append({"id": str(device.id), "title": device.title, "fields": changed_fields})

        for device_id, funding_details in NON_AMOUNT_FUNDING_DETAILS.items():
            device = by_id.get(device_id)
            if not device:
                continue
            if device.funding_details != funding_details:
                device.funding_details = funding_details
                _add_tag(device, "audit:funding_text_disambiguated_20260601")
                device.updated_at = now
                changes.append({"id": str(device.id), "title": device.title, "fields": ["funding_details"]})

        for device_id in HIDE_DEAD_LINK_IDS:
            device = by_id.get(device_id)
            if not device:
                continue
            changed_fields = []
            if device.status != "standby":
                device.status = "standby"
                changed_fields.append("status")
            if device.validation_status != "admin_only":
                device.validation_status = "admin_only"
                changed_fields.append("validation_status")
            if device.user_quality_decision != "hide":
                device.user_quality_decision = "hide"
                changed_fields.append("user_quality_decision")
            reasons = set(device.user_quality_reasons or [])
            if "lien_officiel_indisponible" not in reasons:
                reasons.add("lien_officiel_indisponible")
                device.user_quality_reasons = sorted(reasons)
                changed_fields.append("user_quality_reasons")
            if changed_fields:
                _add_tag(device, "audit:dead_link_hidden_20260601")
                device.updated_at = now
                changes.append({"id": str(device.id), "title": device.title, "fields": changed_fields})

        for device_id in ACCENT_TARGET_IDS | set(AMOUNT_UPDATES):
            device = by_id.get(device_id)
            if not device:
                continue
            changed_fields = []
            for field in TEXT_FIELDS:
                fixed, changed = _fix_text(getattr(device, field))
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)
            for field in JSON_FIELDS:
                fixed, changed = _fix_json(getattr(device, field))
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)
            if changed_fields:
                _add_tag(device, "audit:text_polished_20260601")
                device.updated_at = now
                changes.append({"id": str(device.id), "title": device.title, "fields": sorted(set(changed_fields))})

        await db.commit()

    return {"changed": len(changes), "items": changes}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
