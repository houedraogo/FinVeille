"""Corrige les irritants catalogues signales par les tests utilisateur."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


WATCH_FIXES: dict[str, dict[str, Any]] = {
    "TP'up Souveraineté IDF": {
        "title": "TP'up Île-de-France - transformation écologique des TPE",
        "source_url": "https://www.iledefrance.fr/aides-et-appels-a-projets/tpup",
        "amount_max": Decimal("82500"),
        "currency": "EUR",
        "funding_details": (
            "Le plafond standard TP'up est de 55 000 EUR. Il peut être porté exceptionnellement "
            "à 82 500 EUR pour les projets localisés en zones de reconquête économique ou présentant "
            "un fort impact écologique et un plan de transition ambitieux."
        ),
    },
    "FCI4Africa - appel 1 jusqu'à 50 000 EUR pour l'innovation alimentaire": {
        "source_url": "https://fci4africa.eu/open-calls/open-call-1/",
        "amount_min": Decimal("50000"),
        "amount_max": Decimal("50000"),
        "currency": "EUR",
        "funding_details": (
            "L'enveloppe totale de l'appel est de 400 000 EUR. Huit sous-projets doivent être "
            "financés, avec un budget maximal de 50 000 EUR par sous-projet. La candidature se "
            "dépose via la plateforme opencalls.fund indiquée par FCI4Africa."
        ),
    },
    "FAPE Burkina Faso - cofinancement de projets productifs": {
        "organism": "Fonds d'Appui à la Promotion de l'Emploi",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-cofinancement-des-projets-agriculture-elevage-artisanat-et-transformation-des-produits-locaux-commerce-prestation-de-service-transport-et-btp",
        "funding_details": (
            "Le FAPE intervient par prêts directs, garanties et accompagnement au profit des micro, "
            "petites et moyennes entreprises. La fiche de procédure publique ne donne pas de plafond "
            "unique exploitable : les montants, garanties et apports personnels doivent être confirmés "
            "au guichet FAPE ou via la procédure Service Public Burkina."
        ),
    },
}

PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
PUBLIC_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
PUBLIC_TYPES = {
    "subvention",
    "pret",
    "avance_remboursable",
    "garantie",
    "credit_impot",
    "exoneration",
    "aap",
    "appel_a_projets",
    "ami",
    "accompagnement",
    "concours",
}
ENTREPRENEUR_BENEFICIARIES = {
    "entreprise",
    "pme",
    "tpe",
    "mpme",
    "startup",
    "entrepreneur",
    "porteur projet",
    "porteur de projet",
    "jeune entrepreneur",
    "femme entrepreneure",
    "cooperative",
    "entreprise sociale",
    "exploitant agricole",
    "structure_accompagnement",
}
EURO_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[ .]\d{3})+|\d+(?:[,.]\d+)?)\s*(?:€|eur\b|euros?\b)", re.IGNORECASE)
PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[,.]\d+)?)\s*%")


def _visible_france_entrepreneur(device: Device) -> bool:
    return (
        device.country == "France"
        and device.validation_status in PUBLIC_VALIDATION_STATUSES
        and device.user_quality_decision in PUBLIC_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type in PUBLIC_TYPES
        and bool(set(device.beneficiaries or []) & ENTREPRENEUR_BENEFICIARIES)
    )


def _parse_decimal(raw: str) -> Decimal:
    normalized = raw.replace(" ", "").replace(".", "").replace(",", ".")
    return Decimal(normalized)


def _extract_euro_amounts(text: str | None) -> list[Decimal]:
    if not text:
        return []
    amounts: list[Decimal] = []
    for match in EURO_RE.finditer(text):
        try:
            amount = _parse_decimal(match.group(1))
        except Exception:
            continue
        if amount >= 100:
            amounts.append(amount)
    return amounts


def _extract_rate(text: str | None) -> Decimal | None:
    if not text:
        return None
    rates: list[Decimal] = []
    for match in PERCENT_RE.finditer(text):
        try:
            rate = Decimal(match.group(1).replace(",", "."))
        except Exception:
            continue
        if 0 < rate <= 100:
            rates.append(rate)
    return max(rates) if rates else None


async def run(apply: bool) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device))).scalars().all()

        for device in devices:
            fields: list[str] = []
            fix = WATCH_FIXES.get(device.title or "")
            if fix:
                for field, value in fix.items():
                    if getattr(device, field) != value:
                        fields.append(field)
                        if apply:
                            setattr(device, field, value)

            if _visible_france_entrepreneur(device):
                amounts = _extract_euro_amounts(device.funding_details)
                if amounts and device.amount_min is None and device.amount_max is None:
                    amount_min = min(amounts)
                    amount_max = max(amounts)
                    if device.device_type in {"pret", "subvention", "garantie", "avance_remboursable", "accompagnement", "aap", "appel_a_projets", "ami", "concours"}:
                        fields.extend(["amount_min", "amount_max"])
                        if apply:
                            device.amount_min = amount_min
                            device.amount_max = amount_max
                            device.currency = device.currency or "EUR"

                rate = _extract_rate(device.funding_details)
                if rate and device.funding_rate is None and device.device_type in {"credit_impot", "exoneration", "subvention", "accompagnement"}:
                    fields.append("funding_rate")
                    if apply:
                        device.funding_rate = rate

            if fields:
                changed.append({"id": str(device.id), "title": device.title, "fields": sorted(set(fields))})
                if apply:
                    device.updated_at = now

        if apply:
            await db.commit()

    return {"dry_run": not apply, "changed": len(changed), "items": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
