"""Corrige les residus visibles apres audit des fiches signalees par l'utilisateur."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import compute_completeness, generate_slug, normalize_title


CARBURANT_ID = "a6d02f0f-5fdf-411c-8aae-560650b57dca"
JEI_ID = "45fd53fe-9c14-4ac9-9286-784c90e360ec"
BCS_ID = "4e9e7de8-e0e9-4997-90d3-04f79f0001a3"
PAST_DEADLINE_IDS = {
    "e0627c1f-6de7-42fd-8ef4-7b5431a561d1",
    "ae62e284-6645-432a-8f94-c5304969a740",
    "edab4d6b-7306-4fec-86c0-49e89c43564d",
}
AMOUNT_FIXES: dict[str, dict[str, Any]] = {
    "62d8ca91-e969-4f18-bb09-a86af9802ae2": {
        "amount_max": Decimal("1500000"),
        "funding_rate": Decimal("60"),
        "funding_details": (
            "Garantie de prêts à moyen ou long terme ou de crédit-bail. La quotité maximale est de "
            "60 %, avec un plafond de risque de 1,5 million EUR sur une même entreprise ou un même groupe."
        ),
    },
    "0fa7a86c-77fb-48c3-9188-0505e669fbfa": {
        "amount_max": Decimal("1500000"),
        "funding_rate": Decimal("60"),
        "funding_details": (
            "Garantie de prêts à moyen ou long terme ou de crédit-bail. La quotité maximale est de "
            "60 %, avec un plafond de risque de 1,5 million EUR sur une même entreprise ou un même groupe."
        ),
    },
    "7a84000a-5fb4-4f54-adfc-22974b91d1e5": {
        "funding_rate": Decimal("60"),
        "funding_details": (
            "La garantie couvre jusqu'à 60 % du financement. La durée de garantie indiquée par Bpifrance "
            "est comprise entre 2 et 15 ans."
        ),
    },
    "7dcb3f0a-2208-46ac-883f-5283ac4c5f5e": {
        "amount_min": Decimal("35000"),
        "amount_max": Decimal("60000"),
        "funding_details": (
            "Subvention comprise entre 35 000 et 60 000 EUR par porteur de projet. Les projets attendus "
            "doivent présenter une assiette minimale de 70 000 EUR."
        ),
    },
    "5113afed-3791-4793-a765-7593f14c6baf": {
        "funding_rate": Decimal("50"),
        "funding_details": (
            "Soutien mixte en subvention et avance remboursable. Dans le cas général, la part de subvention "
            "est de 50 % pour les projets, avec une assiette minimale de 2 millions EUR en mono-partenaire "
            "ou 4 millions EUR en collaboratif."
        ),
    },
    "676dc9ac-7dbe-450e-9f3c-11e4c019d557": {
        "funding_rate": Decimal("50"),
        "funding_details": (
            "Soutien France 2030 sous forme de subvention et d'avance remboursable, couvrant jusqu'à 50 % "
            "des dépenses éligibles. L'assiette minimale de projet est de 2 millions EUR."
        ),
    },
    "a8b8da5f-6d22-4166-b9c5-b5317681afce": {
        "amount_min": Decimal("50000"),
        "amount_max": Decimal("3000000"),
        "funding_rate": Decimal("80"),
        "funding_details": (
            "Pour les partenaires français, l'aide à l'innovation est comprise entre 50 000 et 3 millions "
            "EUR. Elle peut prendre la forme d'un Prêt Innovation R&D jusqu'à 80 % des dépenses ou d'une "
            "Avance Innovation jusqu'à 65 %."
        ),
    },
    "d8e797a8-9e26-4049-ad92-f1ff49072dc1": {
        "amount_min": Decimal("50000"),
        "amount_max": Decimal("3000000"),
        "funding_rate": Decimal("80"),
        "funding_details": (
            "Pour les partenaires français, l'aide à l'innovation est comprise entre 50 000 et 3 millions "
            "EUR. Elle peut prendre la forme d'un Prêt Innovation R&D jusqu'à 80 % des dépenses ou d'une "
            "Avance Innovation jusqu'à 65 %."
        ),
    },
}

IMPOTS_GRANDS_ROULEURS_URL = (
    "https://www.impots.gouv.fr/actualite/grace-notre-simulateur-decouvrez-si-vous-pourrez-beneficier-de-laide-de-100-eu-pour-les"
)


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
    device.updated_at = datetime.now(timezone.utc)


async def _get_or_create_impots_source(db) -> Source:
    source = (
        await db.execute(select(Source).where(Source.url == IMPOTS_GRANDS_ROULEURS_URL))
    ).scalar_one_or_none()
    if source:
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
        url=IMPOTS_GRANDS_ROULEURS_URL,
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
        "polish_updated": [],
        "expired_hidden": [],
    }

    async with AsyncSessionLocal() as db:
        impots_source = await _get_or_create_impots_source(db)

        carburant = (await db.execute(select(Device).where(Device.id == CARBURANT_ID))).scalar_one_or_none()
        if carburant:
            carburant.source_id = impots_source.id
            carburant.source_url = IMPOTS_GRANDS_ROULEURS_URL
            carburant.amount_min = Decimal("100")
            carburant.amount_max = Decimal("100")
            carburant.currency = "EUR"
            carburant.funding_details = (
                "Indemnité forfaitaire de 100 EUR, accordée une seule fois pour un même véhicule."
            )
            carburant.short_description = (
                "Aide forfaitaire de 100 EUR pour les travailleurs modestes qui utilisent leur véhicule "
                "personnel à des fins professionnelles et parcourent des distances importantes."
            )
            carburant.full_description = (
                "La page officielle impots.gouv.fr présente l'aide carburant grands rouleurs 2026. "
                "Elle précise le montant forfaitaire de 100 EUR, le simulateur d'éligibilité, les critères "
                "de ressources et la démarche depuis l'espace personnel impots.gouv.fr. La fiche permet de "
                "qualifier rapidement les travailleurs concernés avant le dépôt en ligne."
            )
            carburant.eligibility_criteria = (
                "Être domicilié fiscalement en France, avoir au moins 16 ans au 31 décembre 2024, "
                "utiliser un véhicule personnel pour l'activité professionnelle et respecter les seuils "
                "de distance et de revenu fiscal de référence indiqués par impots.gouv.fr."
            )
            carburant.specific_conditions = (
                "Vérifier l'éligibilité avec le simulateur officiel, puis déposer la demande dans l'espace "
                "personnel impots.gouv.fr lorsque le formulaire est ouvert."
            )
            carburant.source_raw = (
                "Page officielle impots.gouv.fr publiée le 22/04/2026 et modifiée le 22/05/2026."
            )
            _append_tags(carburant, "source:official_impots", "audit:dead_link_fixed", "amount:verified")
            _refresh(carburant)
            result["carburant_updated"] = True

        jei = (await db.execute(select(Device).where(Device.id == JEI_ID))).scalar_one_or_none()
        if jei:
            jei.eligibility_criteria = (
                "L'entreprise doit respecter les critères du statut Jeune Entreprise Innovante, notamment "
                "la taille, l'ancienneté, l'indépendance du capital et le niveau de dépenses de recherche "
                "et développement requis."
            )
            _append_tags(jei, "copy:eligibility_polished")
            _refresh(jei)
            result["polish_updated"].append({"id": str(jei.id), "title": jei.title})

        bcs = (await db.execute(select(Device).where(Device.id == BCS_ID))).scalar_one_or_none()
        if bcs:
            bcs.eligibility_criteria = (
                "La participation vise les TPE et PME bretonnes, tous secteurs d'activité confondus, "
                "à l'exclusion des commerces de détail."
            )
            _append_tags(bcs, "copy:eligibility_polished")
            _refresh(bcs)
            result["polish_updated"].append({"id": str(bcs.id), "title": bcs.title})

        past_deadline_devices = (
            await db.execute(select(Device).where(Device.id.in_(PAST_DEADLINE_IDS)))
        ).scalars().all()
        for device in past_deadline_devices:
            device.status = "expired"
            device.validation_status = "admin_only"
            device.user_quality_decision = "admin_only"
            device.decision_analysis = {
                **(device.decision_analysis or {}),
                "quality_action": "hide_expired_deadline",
                "quality_action_at": datetime.now(timezone.utc).isoformat(),
                "reason": (
                    "Date limite dépassée au 26/05/2026."
                    if str(device.id) != "edab4d6b-7306-4fec-86c0-49e89c43564d"
                    else "Source officielle Bpifrance clôturée le 09/09/2025."
                ),
            }
            if str(device.id) == "edab4d6b-7306-4fec-86c0-49e89c43564d":
                device.close_date = datetime(2025, 9, 9, tzinfo=timezone.utc).date()
                device.funding_details = (
                    "Le FFRER était doté de 250 millions EUR par l'Etat et investissait aux côtés "
                    "des Régions dans des fonds régionaux ou interrégionaux. La page officielle "
                    "Bpifrance indique une période de candidature close le 09/09/2025."
                )
                device.specific_conditions = (
                    "Fiche masquée côté utilisateur : l'appel Bpifrance est clos depuis le 09/09/2025."
                )
            _append_tags(device, "visibility:admin_only", "audit:past_deadline_hidden")
            _refresh(device)
            result["expired_hidden"].append(
                {"id": str(device.id), "title": device.title, "close_date": str(device.close_date)}
            )

        amount_devices = (
            await db.execute(select(Device).where(Device.id.in_(AMOUNT_FIXES.keys())))
        ).scalars().all()
        result["amounts_updated"] = []
        for device in amount_devices:
            fix = AMOUNT_FIXES.get(str(device.id))
            if not fix:
                continue
            for field, value in fix.items():
                setattr(device, field, value)
            device.currency = device.currency or "EUR"
            _append_tags(device, "amount:verified")
            _refresh(device)
            result["amounts_updated"].append({"id": str(device.id), "title": device.title})

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
