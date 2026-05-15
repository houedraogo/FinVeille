from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


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

INSTITUTIONAL_BENEFICIARIES = [
    "institution publique",
    "etat",
    "ministere",
    "collectivite",
    "acteur territorial",
]


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


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Import manuel / historique"


def _country_label(device: Device) -> str:
    country = clean_editorial_text(device.country or device.region or device.zone or "Afrique de l'Ouest")
    return country or "Afrique de l'Ouest"


def _type_label(device: Device) -> str:
    mapping = {
        "subvention": "financement",
        "aap": "appel à projets",
        "appel_a_projets": "appel à projets",
        "concours": "concours",
        "pret": "prêt",
        "accompagnement": "accompagnement",
        "investissement": "investissement",
        "institutional_project": "projet institutionnel",
        "recurring": "dispositif permanent",
    }
    return mapping.get(str(device.device_type or "").lower(), "opportunité")


def _type_label_from_value(value: str | None) -> str:
    mapping = {
        "subvention": "financement",
        "aap": "appel à projets",
        "appel_a_projets": "appel à projets",
        "appel à projets": "appel à projets",
        "concours": "concours",
        "pret": "prêt",
        "accompagnement": "accompagnement",
        "investissement": "investissement",
    }
    return mapping.get(str(value or "").lower(), "opportunité")


def _type_phrase(value: str | None) -> str:
    label = _type_label_from_value(value)
    return f"un {label}"


def _calendar(device: Device) -> str:
    if device.close_date:
        return f"Date limite ou clôture indiquée par la source : {device.close_date:%d/%m/%Y}."
    if device.is_recurring or device.status == "recurring":
        return "Dispositif permanent ou récurrent : aucune fenêtre de clôture unique n'est publiée."
    return "Date limite non communiquée par la source. Vérifier la page officielle avant toute décision."


def _section(key: str, title: str, content: str, confidence: int = 78) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": "normalisation ciblée Kafundo",
    }


def _sections(
    *,
    presentation: str,
    eligibility: str,
    funding: str,
    calendar: str,
    procedure: str,
    checks: str,
) -> list[dict[str, Any]]:
    return [
        _section("presentation", "Présentation", presentation, 84),
        _section("eligibility", "Critères d'éligibilité", eligibility, 78),
        _section("funding", "Montant / avantages", funding, 76),
        _section("calendar", "Calendrier", calendar, 80),
        _section("procedure", "Démarche", procedure, 76),
        _section("checks", "Points à vérifier", checks, 72),
    ]


def _as_payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _apply_institutional(device: Device) -> bool:
    source = _source_name(device).lower()
    if (
        device.device_type != "institutional_project"
        and "banque mondiale" not in source
        and "foname" not in source
    ):
        return False

    country = _country_label(device)
    presentation = (
        f"{device.title} est un projet institutionnel suivi par Kafundo pour {country}. "
        "Il sert à comprendre les priorités publiques, les programmes structurants et les financements de référence, "
        "mais ce n'est pas un appel à candidatures direct pour une entreprise."
    )
    eligibility = (
        "Cette fiche concerne principalement des institutions publiques, partenaires de mise en oeuvre, collectivités "
        "ou acteurs mandatés. Elle ne doit pas être interprétée comme une opportunité directe pour un entrepreneur, "
        "sauf si la source officielle publie ensuite un appel, un guichet ou une procédure ouverte."
    )
    funding = (
        "Les montants correspondent à un financement de projet ou à une enveloppe institutionnelle. "
        "Ils ne représentent pas une aide directement attribuable à une entreprise individuelle."
    )
    procedure = (
        "Utiliser cette fiche comme signal de veille. Pour candidater, attendre ou rechercher un appel opérationnel "
        "lié au projet, publié par l'institution, le ministère, l'agence de mise en oeuvre ou un partenaire local."
    )
    checks = (
        "Vérifier s'il existe un appel à projets, un appel d'offres, un guichet PME ou un programme partenaire avant "
        "de considérer cette fiche comme une opportunité actionnable."
    )

    changed = False
    updates = {
        "device_type": "institutional_project",
        "beneficiaries": INSTITUTIONAL_BENEFICIARIES,
        "short_description": presentation,
        "eligibility_criteria": eligibility,
        "funding_details": funding,
        "language": "fr",
        "ai_readiness_score": 58,
        "ai_readiness_label": "utilisable_avec_prudence",
        "ai_readiness_reasons": [
            "projet institutionnel",
            "pas une candidature directe",
            "source officielle à vérifier",
        ],
    }
    sections = _sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        calendar=_calendar(device),
        procedure=procedure,
        checks=checks,
    )
    full_description = build_structured_sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        close_date=device.close_date,
        open_date=device.open_date,
        procedure=procedure,
        recurrence_notes=device.recurrence_notes,
    )

    for field, value in updates.items():
        if getattr(device, field) != value:
            setattr(device, field, value)
            changed = True
    if device.content_sections_json != sections:
        device.content_sections_json = sections
        changed = True
    if device.ai_rewritten_sections_json != sections:
        device.ai_rewritten_sections_json = sections
        changed = True
    if device.full_description != full_description:
        device.full_description = full_description
        changed = True
    return changed


def _infer_actionable_type(device: Device) -> str:
    text = _norm(" ".join([device.title or "", device.full_description or "", device.short_description or ""]))
    if any(word in text for word in ["concours", "prix", "challenge", "award"]):
        return "concours"
    if any(word in text for word in ["appel a projets", "appel a propositions", "aap", "candidature"]):
        return "aap"
    if any(word in text for word in ["pret", "credit", "avance remboursable"]):
        return "pret"
    if any(word in text for word in ["incub", "acceler", "mentorat", "coaching", "accompagnement"]):
        return "accompagnement"
    if any(word in text for word in ["investissement", "capital", "venture"]):
        return "investissement"
    return "subvention"


def _apply_actionable(device: Device) -> bool:
    if device.device_type == "institutional_project":
        return False

    country = _country_label(device)
    source = clean_editorial_text(_source_name(device))
    dtype = _infer_actionable_type(device) if device.device_type in {None, "", "autre"} else str(device.device_type)
    sectors = ", ".join(device.sectors or []) or "secteurs indiqués par la source"
    beneficiaries = ", ".join(device.beneficiaries or []) or "porteurs de projet, PME, associations ou acteurs éligibles selon la source"

    presentation = (
        f"{device.title} est {_type_phrase(dtype)} suivi par Kafundo pour {country}. "
        f"Cette opportunité concerne principalement {sectors}. L'objectif est d'aider les porteurs éligibles à identifier rapidement "
        "si cette piste mérite d'être étudiée."
    )
    eligibility = (
        f"Bénéficiaires à vérifier : {beneficiaries}. Les conditions précises dépendent de la source officielle "
        "et doivent être relues avant de préparer un dossier."
    )
    funding_text = clean_editorial_text(device.funding_details or "")
    normalized_funding = _norm(funding_text)
    if device.amount_max:
        funding = f"Montant maximum connu : {device.amount_max:g} {device.currency or 'EUR'}."
    elif funding_text and len(funding_text) > 80 and "doivent etre confirm" not in normalized_funding and "a confirmer" not in normalized_funding:
        funding = funding_text
    else:
        funding = "Montant ou avantage non publié de façon suffisamment précise. Consulter la source officielle pour confirmer l'enveloppe."
    procedure = (
        f"Consulter la page officielle de {source}, vérifier les critères et préparer les pièces demandées si la fenêtre de candidature est ouverte."
    )
    checks = "Confirmer la date limite, les bénéficiaires exacts, le montant et les pièces à fournir sur la source officielle."

    sections = _sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        calendar=_calendar(device),
        procedure=procedure,
        checks=checks,
    )
    full_description = build_structured_sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        close_date=device.close_date,
        open_date=device.open_date,
        procedure=procedure,
        recurrence_notes=device.recurrence_notes,
    )

    changed = False
    updates = {
        "device_type": dtype,
        "short_description": presentation,
        "eligibility_criteria": eligibility,
        "funding_details": funding,
        "language": "fr",
    }
    for field, value in updates.items():
        if getattr(device, field) != value:
            setattr(device, field, value)
            changed = True
    if device.content_sections_json != sections:
        device.content_sections_json = sections
        changed = True
    if device.ai_rewritten_sections_json != sections:
        device.ai_rewritten_sections_json = sections
        changed = True
    if device.full_description != full_description:
        device.full_description = full_description
        changed = True
    return changed


async def run(*, apply: bool = False) -> dict[str, Any]:
    stats = {
        "scanned": 0,
        "updated": 0,
        "institutional_fixed": 0,
        "actionable_fixed": 0,
    }
    preview: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
            )
        ).scalars().all()

        for device in devices:
            if not _targets_device(device):
                continue
            stats["scanned"] += 1
            before = {
                "title": device.title,
                "type": device.device_type,
                "beneficiaries": list(device.beneficiaries or []),
                "short": clean_editorial_text(device.short_description or "")[:160],
            }

            changed = False
            if device.device_type == "institutional_project" or "banque mondiale" in _source_name(device).lower():
                changed = _apply_institutional(device)
                if changed:
                    stats["institutional_fixed"] += 1
            else:
                source = _source_name(device).lower()
                text = _norm(" ".join([device.short_description or "", device.full_description or ""]))
                if "foname" in source or "portefeuille national" in _norm(device.title):
                    changed = _apply_institutional(device)
                    if changed:
                        stats["institutional_fixed"] += 1
                else:
                    changed = _apply_actionable(device)
                    if changed:
                        stats["actionable_fixed"] += 1

            if changed:
                device.completeness_score = compute_completeness(_as_payload(device))
                device.updated_at = datetime.now(timezone.utc)
                stats["updated"] += 1
                if len(preview) < 15:
                    preview.append(
                        {
                            "title": before["title"],
                            "source": _source_name(device),
                            "before_type": before["type"],
                            "after_type": device.device_type,
                            "before_beneficiaries": before["beneficiaries"],
                            "after_beneficiaries": device.beneficiaries,
                            "after_short": clean_editorial_text(device.short_description or "")[:220],
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les fiches prioritaires Burkina, Benin et Cote d'Ivoire.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
