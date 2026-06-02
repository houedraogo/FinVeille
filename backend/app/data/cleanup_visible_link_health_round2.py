"""Fix or hide the current visible link-health actionable failures."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness, generate_slug, normalize_title


URL_FIXES: dict[str, dict[str, Any]] = {
    "6bc5e45c-dfdc-4ce9-9894-d65559acf594": {
        "title": "Assurance Maladie - Captage fumées de diesel",
        "organism": "Assurance Maladie - Risques professionnels",
        "region": None,
        "geographic_scope": "national",
        "source_url": "https://www.ameli.fr/entreprise/sante-travail/prevention/aides-financieres/subventions-1-50-salaries/subventions-risques-chimiques/captage-fumees-diesel",
        "source_raw": "Page officielle Ameli Entreprise active pour la subvention Captage fumées de diesel, mise à jour en 2026.",
        "funding_rate": 70,
        "funding_details": "Subvention Prévention couvrant 70 % du montant HT des équipements et vérifications éligibles, avec un minimum de subvention de 500 €.",
    },
    "bd98805d-abdf-4a14-b335-ca370a7b613d": {
        "title": "Bpifrance - Subvention Innovation / Innovation créative",
        "organism": "Bpifrance",
        "region": None,
        "geographic_scope": "national",
        "source_url": "https://www.bpifrance.fr/catalogue-offres/subvention-innovationinnovation-creative",
        "source_raw": "Page officielle Bpifrance active pour la Subvention Innovation / Innovation créative.",
        "amount_max": 50_000,
        "funding_rate": 70,
        "funding_details": "Aide sous forme de subvention pouvant aller jusqu'à 50 000 €, avec une prise en charge pouvant atteindre 70 % selon la catégorie d'entreprise.",
    },
    "bd34d471-a55c-4ea9-8396-d955dd64cc3a": {
        "title": "Nouvelle-Aquitaine - Accélération Start-Up",
        "source_url": "https://les-aides.nouvelle-aquitaine.fr/economie-et-emploi/acceleration-start",
        "source_raw": "Page officielle active du Guide des aides Nouvelle-Aquitaine pour Accélération Start-Up.",
        "is_recurring": True,
        "close_date": None,
        "recurrence_notes": "Demande étudiée au fil de l'eau, après validation de l'éligibilité puis instruction régionale.",
    },
    "da339694-234f-49bf-bec8-cb8e34db9fae": {
        "title": "Nouvelle-Aquitaine - Aide à l'investissement des TPE à fort potentiel",
        "source_url": "https://les-aides.nouvelle-aquitaine.fr/amenagement-du-territoire/aide-linvestissement-des-tpe-fort-potentiel",
        "source_raw": "Page officielle active du Guide des aides Nouvelle-Aquitaine pour l'aide à l'investissement des TPE à fort potentiel.",
        "amount_max": 100_000,
        "funding_rate": 35,
        "funding_details": "Taux d'intervention maximum de 35 % sur les investissements éligibles, avec un plafond d'aide de 100 000 €.",
        "is_recurring": True,
        "close_date": None,
        "recurrence_notes": "Etude des dossiers à réception du dossier transmis, puis décision après instruction par la Région.",
    },
}

HIDE_IDS: dict[str, str] = {
    "44f7d991-055d-4102-bd47-e209b2948f33": (
        "La source officielle de repli est accessible en PDF, mais indique une fin de dépôt au 31 décembre 2025."
    ),
}


def _append_tags(device: Device, *tags: str) -> None:
    current = list(device.tags or [])
    for tag in tags:
        if tag not in current:
            current.append(tag)
    device.tags = current[:24]


def _refresh(device: Device) -> None:
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    device.completeness_score = compute_completeness(payload)
    device.title_normalized = normalize_title(device.title)
    device.slug = device.slug or generate_slug(device.title)
    now = datetime.now(timezone.utc)
    device.updated_at = now
    device.last_verified_at = now


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {"url_fixed": [], "hidden": []}
    ids = set(URL_FIXES) | set(HIDE_IDS)
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(ids)))).scalars().all()
        for device in devices:
            device_id = str(device.id)
            if device_id in URL_FIXES:
                for field, value in URL_FIXES[device_id].items():
                    setattr(device, field, value)
                _append_tags(device, "audit:link_fixed", "audit:source_verified_20260601")
                _refresh(device)
                result["url_fixed"].append(
                    {"id": device_id, "title": device.title, "source_url": device.source_url}
                )
                continue

            if device_id in HIDE_IDS:
                device.source_url = "https://les-aides.nouvelle-aquitaine.fr/gda-fiche-pdf/5480"
                device.close_date = date(2025, 12, 31)
                device.status = "expired"
                device.validation_status = "admin_only"
                device.user_quality_decision = "admin_only"
                device.source_raw = (
                    "PDF officiel Nouvelle-Aquitaine accessible, mais échéance officielle dépassée au 31 décembre 2025."
                )
                device.recurrence_notes = "Masquée côté utilisateur : échéance officielle dépassée."
                device.decision_analysis = {
                    **(device.decision_analysis or {}),
                    "quality_action": "hide_expired_link_failure",
                    "quality_action_at": datetime.now(timezone.utc).isoformat(),
                    "reason": HIDE_IDS[device_id],
                }
                _append_tags(device, "visibility:admin_only", "audit:expired_hidden", "audit:source_verified_20260601")
                _refresh(device)
                result["hidden"].append(
                    {"id": device_id, "title": device.title, "source_url": device.source_url}
                )

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
