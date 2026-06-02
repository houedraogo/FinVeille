"""Corrige les liens de sources des fiches Afrique visibles."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness, normalize_title


URL_FIXES: dict[str, dict[str, Any]] = {
    "2006a5b0-bb55-42b8-bf61-4b98c3178143": {
        "source_url": "https://www.faij.gov.bf/presentation",
        "source_raw": "Page officielle FAIJ Burkina Faso active : présentation du fonds et de ses financements de microprojets jeunes.",
    },
    "c6657ffb-d20e-419d-b468-7926dbb09022": {
        "source_url": "https://www.fonafi-bf.org/fonafi-presentation/",
        "source_raw": "Page officielle FONAFI : présentation du Fonds National de la Finance Inclusive au Burkina Faso.",
    },
    "d83ac039-ee69-4835-93c0-2e655f088d87": {
        "source_url": "https://paif.bf/",
        "source_raw": "Site officiel PAIF-PME Burkina Faso : Projet d'Appui à l'Inclusion Financière et à l'Accès au Financement des PME.",
    },
    "c663ab48-944d-4995-9c1b-54587794456f": {
        "source_url": "https://www.sofigib.bf/",
        "source_raw": "Site officiel SOFIGIB : société financière de garantie interbancaire du Burkina Faso.",
    },
    "91f96890-95e7-4f0e-8926-5f76e952e508": {
        "source_url": "https://www.gouv.bj/article/3006/",
        "source_raw": "Article officiel du Gouvernement du Bénin sur le programme Azôli, mis en œuvre par l'ANPE avec l'appui de la Banque mondiale.",
    },
    "5eaf752e-bca5-40cd-abfb-e21e2f4bca0a": {
        "title": "CMA Bénin - accompagnement et opportunités pour artisans",
        "organism": "Chambre des Métiers de l'Artisanat du Bénin",
        "source_url": "https://www.cmabenin.bj/",
        "source_raw": "Site officiel de la Chambre des Métiers de l'Artisanat du Bénin.",
    },
    "1f2c2c1b-d3e9-4812-be0f-abc14fa5c508": {
        "source_url": "https://fnda.agriculture.gouv.bj/",
        "source_raw": "Site officiel du Fonds National de Développement Agricole du Bénin.",
    },
    "900bd47c-2d80-48ab-b833-b66106df590b": {
        "source_url": "https://www.pfs-aie.cm/public/portail/iej",
        "source_raw": "Portail officiel du Projet Filets Sociaux Adaptatifs et d'Inclusion Économique sur l'Inclusion économique des jeunes au Cameroun.",
    },
    "ef3787ee-7772-4702-9dda-c329e5f2a108": {
        "source_url": "https://enza.capital/",
        "source_raw": "Site officiel Enza Capital.",
    },
    "dd2d6db4-56cd-4335-8714-4defcfe7c1ef": {
        "title": "Verod-Kepple Africa Ventures",
        "organism": "Verod-Kepple Africa Ventures",
        "source_url": "https://vkav.vc/",
        "source_raw": "Site officiel Verod-Kepple Africa Ventures, nouvelle référence publique de Kepple Africa Ventures.",
    },
    "e8213800-5334-4ae9-a30e-d59f2758d7dc": {
        "source_url": "https://vc4a.com/samurai-incubate/",
        "source_raw": "Profil VC4A vérifié de Samurai Incubate Africa.",
    },
    "89af47f8-7d42-4c64-8e62-da098bc87846": {
        "source_url": "https://www.mcapitalp.com/",
        "source_raw": "Site officiel Mediterrania Capital Partners.",
    },
    "b580e50f-6286-43cf-a96e-1bcd4e403b42": {
        "source_url": "https://www.anadec.cd/accompagnement-a-la-creation-et-a-la-formalisation/",
        "source_raw": "Page officielle ANADEC sur l'accompagnement à la création et à la formalisation des entrepreneurs en RDC.",
    },
    "f39eba2c-cfa4-4c26-8de7-413675a38b07": {
        "source_url": "https://mastercardfdn.org/en/what-we-do/our-programs/enhancing-capacities-of-young-women-and-youth-led-enterprises-for-regional-trade-ecowyert/",
        "source_raw": "Page officielle Mastercard Foundation du programme ECoWYERT, couvrant notamment la RDC.",
    },
    "ebe9192c-fa4a-4cc9-bdb8-9d46b12f269e": {
        "source_url": "https://anpgftogo.org/",
        "source_raw": "Site officiel de l'Agence Nationale de Promotion et de Garantie de Financement des PME/PMI du Togo.",
    },
    "77e78d69-3628-4f70-92ef-aa07154f999d": {
        "source_url": "https://at2er.tg/projet-delectrification-rurale-hors-reseau-par-kits-solaires-domestiques-en-mode-paygo-cizo/",
        "source_raw": "Page officielle AT2ER sur le projet CIZO d'électrification rurale hors réseau au Togo.",
    },
    "8723b395-9f5f-4f3e-96d4-2af76a116692": {
        "source_url": "https://www.republiquetogolaise.com/agro/1601-3961-en-2019-le-mifa-a-mobilise-8-1-milliards-fcfa-de-financement-et-impacte-76-000-acteurs-agricoles",
        "source_raw": "Article du site officiel République Togolaise sur les financements mobilisés par le MIFA.",
    },
    "b88f682d-2df1-48f6-b6a6-7bb0abd5613a": {
        "source_url": "https://www.paeij-georef.com/",
        "source_raw": "Site public PAEIJ Géoref présentant le Projet d'appui à l'employabilité et à l'insertion des jeunes dans les secteurs porteurs au Togo.",
    },
}

HIDE_IDS: dict[str, str] = {
    "1c30623b-04fa-452f-9ce3-ae301bbb57df": (
        "Aucune source officielle active suffisamment fiable n'a été retrouvée pour l'ANVAR Burkina Faso."
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
    now = datetime.now(timezone.utc)
    device.last_verified_at = now
    device.updated_at = now


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {"fixed": [], "hidden": []}
    ids = set(URL_FIXES) | set(HIDE_IDS)

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(ids)))).scalars().all()
        for device in devices:
            device_id = str(device.id)
            if device_id in URL_FIXES:
                for field, value in URL_FIXES[device_id].items():
                    setattr(device, field, value)
                _append_tags(device, "audit:africa_link_fixed", "source:verified_20260601")
                _refresh(device)
                result["fixed"].append(
                    {"id": device_id, "title": device.title, "source_url": device.source_url}
                )
            elif device_id in HIDE_IDS:
                device.status = "standby"
                device.validation_status = "admin_only"
                device.user_quality_decision = "admin_only"
                _append_tags(device, "visibility:admin_only", "audit:africa_link_hidden")
                device.decision_analysis = {
                    **(device.decision_analysis or {}),
                    "quality_action": "hide_unverified_africa_source",
                    "quality_action_at": datetime.now(timezone.utc).isoformat(),
                    "reason": HIDE_IDS[device_id],
                }
                _refresh(device)
                result["hidden"].append({"id": device_id, "title": device.title})

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
