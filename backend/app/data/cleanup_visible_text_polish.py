"""Corrige les petits defauts editoriaux detectes sur les fiches visibles."""

from __future__ import annotations

import argparse
import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


TARGET_FIXES: dict[str, dict[str, str]] = {
    "4e75546f-583b-4ee8-87d4-ba77760fb648": {
        "eligibility_criteria": "Les entreprises éligibles doivent compter moins de 50 salariés, être immatriculées en France, soumises au droit français, localisées en France métropolitaine ou dans les DROM, créées depuis au moins trois ans et présenter une situation financière saine."
    },
    "4e9e7de8-e0e9-4997-90d3-04f79f0001a3": {
        "eligibility_criteria": "Bretagne Capital Solidaire cible les TPE et PME bretonnes, tous secteurs d'activité confondus, à l'exclusion des commerces de détail. Les conditions d'entrée au capital, de valorisation et de sortie doivent être confirmées auprès de la structure."
    },
    "31609f9d-2882-476f-8fd1-e82923cfc45d": {
        "funding_details": "Le coût total du diagnostic s'élève à 13 000 EUR HT. Bpifrance prend en charge 42 % du coût, avec un reste à charge indicatif de 7 500 EUR HT pour l'entreprise."
    },
    "a136226e-08d1-4121-a0a0-4b08cd2f20f0": {
        "eligibility_criteria": "Le Diag Décarbon'Action cible les PME et petites ETI de moins de 500 salariés, justifiant d'au moins un an d'activité et n'ayant pas réalisé de bilan GES au cours des cinq dernières années. La mission dure généralement de six à huit mois."
    },
    "3fc7f11f-818c-411c-b37d-fdc5618d75c0": {
        "short_description": "France Active propose des garanties pour faciliter l'accès au crédit bancaire des entrepreneurs, notamment les publics prioritaires comme les jeunes avec de faibles apports, les femmes entrepreneures et les porteurs de projet dans les territoires fragiles."
    },
    "45fd53fe-9c14-4ac9-9286-784c90e360ec": {
        "eligibility_criteria": "Le statut JEI concerne les entreprises réellement nouvelles qui respectent les critères d'âge, de taille, de détention du capital et de dépenses de recherche. Les créations issues d'une concentration, restructuration, extension ou reprise d'activité existante sont exclues."
    },
    "ebe35a11-5634-42f2-bc61-eff6394b0ddc": {
        "short_description": "L'appel à projets Eureka Biotech soutient des projets collaboratifs de R&D entre partenaires français et sud-africains dans les biotechnologies, avec une fenêtre de dépôt ouverte du 31 mars au 25 septembre 2026."
    },
    "cf39429e-97de-4cdf-aac5-304cafebc9c1": {
        "short_description": "Le Fonds Jeunesse de la BAD soutient des actions favorisant l'employabilité, l'entrepreneuriat et l'inclusion économique des jeunes en Afrique. Les conditions exactes d'ouverture ou de mobilisation doivent être confirmées sur la source officielle."
    },
}

RAW_URL_IDS = {
    "6e3cfd7b-2bc2-4d1f-98aa-0c3742a3193b",
    "c3f77b05-c657-4f8d-a838-66507d040312",
    "ccc36850-9ee1-4710-9a50-9add2d7fea85",
}
RAW_URL_RE = re.compile(r"\s*https?://\S+", re.IGNORECASE)


async def run(apply: bool) -> dict:
    changed: list[dict] = []
    async with AsyncSessionLocal() as db:
        ids = set(TARGET_FIXES) | RAW_URL_IDS
        devices = (
            await db.execute(select(Device).where(Device.id.in_(ids)))
        ).scalars().all()

        for device in devices:
            fields: list[str] = []
            fixes = TARGET_FIXES.get(str(device.id), {})
            for field, value in fixes.items():
                if getattr(device, field) != value:
                    fields.append(field)
                    if apply:
                        setattr(device, field, value)

            if str(device.id) in RAW_URL_IDS and device.full_description:
                cleaned = RAW_URL_RE.sub("", device.full_description).strip()
                if cleaned != device.full_description:
                    fields.append("full_description")
                    if apply:
                        device.full_description = cleaned

            if fields:
                changed.append({"id": str(device.id), "title": device.title, "fields": fields})
                if apply:
                    device.updated_at = datetime.now(timezone.utc)

        if apply:
            await db.commit()

    return {"dry_run": not apply, "changed": len(changed), "items": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    import json

    print(json.dumps(asyncio.run(run(args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
