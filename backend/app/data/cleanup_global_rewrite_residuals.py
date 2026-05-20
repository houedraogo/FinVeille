from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import (
    build_structured_sections,
    clean_editorial_text,
    compute_completeness,
    normalize_title,
)


MODEL_NAME = "global-rewrite-residual-cleanup-v1"

TITLE_REWRITES = {
    "Call for Applications: develoPPP Ventures 2026 – Funding Opportunity for Start-Ups Expanding Across Africa": (
        "Financement develoPPP Ventures 2026 pour startups en expansion en Afrique"
    ),
    "GAFSP Launches $163 Million Grants Programme to Strengthen Global Food Security and Support Smallholder Farmers": (
        "Programme de subventions GAFSP pour la sécurité alimentaire et les petits producteurs"
    ),
}


def _payload(device: Device) -> dict:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _sentence(text: str, fallback: str, max_len: int = 420) -> str:
    cleaned = clean_editorial_text(text or "")
    if not cleaned:
        return fallback
    replacements = {
        "Opportunite": "Opportunité",
        "relayee": "relayée",
        "reperee": "repérée",
        "etre": "être",
        "concerne principalement": "concerne principalement",
        "date limite reperee": "date limite repérée",
        "criteres": "critères",
        "eligibilite": "éligibilité",
        "verifier": "vérifier",
        "confirmee": "confirmée",
        "collectees": "collectées",
        "donnees": "données",
        "procedure": "procédure",
        "decision": "décision",
        "securite": "sécurité",
        "anti-pauvrete": "anti-pauvreté",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rsplit(" ", 1)[0].rstrip(" ,;:") + "."


def _section(key: str, title: str, content: str, confidence: int, source: str) -> dict:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": source,
    }


def _global_south_sections(device: Device) -> list[dict]:
    title = clean_editorial_text(device.title or "Cette opportunite")
    presentation = _sentence(
        device.short_description or device.full_description,
        f"{title} est une opportunité repérée par Global South Opportunities. Elle doit être vérifiée sur la source officielle avant toute candidature.",
    )
    eligibility = _sentence(
        device.eligibility_criteria,
        "Les critères exacts d'éligibilité doivent être confirmés sur la page officielle : pays couverts, type d'organisation, stade du projet et pièces demandées.",
    )
    funding = _sentence(
        device.funding_details,
        "Le montant, la dotation ou les avantages ne sont pas suffisamment explicites dans la fiche collectée et doivent être confirmés sur la source officielle.",
    )
    if device.close_date:
        calendar = f"Date limite repérée : {device.close_date:%d/%m/%Y}. Vérifier cette date sur la source officielle avant de préparer une candidature."
    elif device.is_recurring or device.status == "recurring":
        calendar = "Opportunité à calendrier récurrent ou variable : vérifier si une session est actuellement ouverte."
    else:
        calendar = "La date limite n'est pas confirmée dans les données collectées. Ne pas traiter cette fiche comme prioritaire sans vérification."

    return [
        _section("presentation", "Présentation", presentation, 84, "global_south_cleanup"),
        _section("eligibility", "Critères d'éligibilité", eligibility, 74, "global_south_cleanup"),
        _section("funding", "Montant / avantages", funding, 72, "global_south_cleanup"),
        _section("calendar", "Calendrier", calendar, 82 if device.close_date else 65, "global_south_cleanup"),
        _section(
            "procedure",
            "Demarche",
            "Consulter la source officielle, vérifier les critères et déposer la candidature uniquement depuis le site indiqué par l'organisateur.",
            76,
            "global_south_cleanup",
        ),
        _section(
            "checks",
            "Points à vérifier",
            "Confirmer la date limite, les pays éligibles, les documents demandés et la procédure officielle avant toute décision.",
            74,
            "global_south_cleanup",
        ),
    ]


def _world_bank_sections(device: Device) -> list[dict]:
    country = clean_editorial_text(device.country or "le pays concerne")
    title = clean_editorial_text(device.title or "Ce projet")
    presentation = (
        f"{title} est un projet institutionnel de la Banque mondiale rattaché à {country}. "
        "Cette fiche sert de signal de veille et ne correspond pas à un appel à candidatures direct pour un utilisateur."
    )
    if device.close_date:
        calendar = f"Date prévisionnelle repérée : {device.close_date:%d/%m/%Y}. Elle concerne le cycle du projet, pas nécessairement une candidature."
    else:
        calendar = "Le flux stocké ne fournit pas de date exploitable pour une candidature. La page officielle doit être consultée pour le suivi institutionnel."
    return [
        _section("presentation", "Présentation", presentation, 82, "world_bank_signal_cleanup"),
        _section(
            "eligibility",
            "Éligibilité",
            "Aucune éligibilité utilisateur directe n'est confirmée. Les bénéficiaires, partenaires et modalités dépendent du projet public suivi par la Banque mondiale.",
            70,
            "world_bank_signal_cleanup",
        ),
        _section(
            "funding",
            "Financement",
            "Cette fiche indique un financement de projet institutionnel. Elle ne doit pas être présentée comme une subvention directement candidatable sans preuve complémentaire.",
            70,
            "world_bank_signal_cleanup",
        ),
        _section("calendar", "Calendrier", calendar, 78 if device.close_date else 65, "world_bank_signal_cleanup"),
        _section(
            "procedure",
            "Demarche",
            "Consulter la page officielle de la Banque mondiale pour suivre le projet, ses documents et ses informations de mise en œuvre.",
            75,
            "world_bank_signal_cleanup",
        ),
    ]


def _apply_sections(device: Device, sections: list[dict]) -> None:
    procedure = next((section["content"] for section in sections if section["key"] == "procedure"), None)
    eligibility = next((section["content"] for section in sections if section["key"] == "eligibility"), None)
    funding = next((section["content"] for section in sections if section["key"] == "funding"), None)
    presentation = next((section["content"] for section in sections if section["key"] == "presentation"), None)

    device.short_description = presentation
    device.eligibility_criteria = eligibility
    device.funding_details = funding
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = MODEL_NAME
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    device.language = "fr"
    device.full_description = build_structured_sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        open_date=device.open_date,
        close_date=device.close_date,
        procedure=procedure,
        recurrence_notes=device.recurrence_notes,
    )
    device.completeness_score = compute_completeness(_payload(device))


async def run(apply: bool = False, force_own: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(
                    Device.validation_status != "rejected",
                    or_(
                        Device.ai_rewritten_sections_json.is_(None),
                        Device.ai_rewrite_status.is_(None),
                        Device.ai_rewrite_status != "done",
                        Device.ai_rewrite_model == MODEL_NAME if force_own else Device.id.is_(None),
                    ),
                )
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

        stats = {
            "global_south_rewritten": 0,
            "world_bank_rewritten": 0,
            "world_bank_hidden_from_public": 0,
            "titles_francised": 0,
            "scanned": len(devices),
            "preview": [],
        }

        for device in devices:
            source_name = device.source.name if device.source else ""
            if "Global South Opportunities" in source_name:
                old_title = device.title
                if device.title in TITLE_REWRITES:
                    device.title = TITLE_REWRITES[device.title]
                    device.title_normalized = normalize_title(device.title)
                    stats["titles_francised"] += 1
                _apply_sections(device, _global_south_sections(device))
                stats["global_south_rewritten"] += 1
                if len(stats["preview"]) < 12:
                    stats["preview"].append(
                        {
                            "source": source_name,
                            "old_title": old_title,
                            "title": device.title,
                            "status": device.status,
                            "validation_status": device.validation_status,
                        }
                    )
                continue

            if "Banque Mondiale" in source_name or (device.organism or "").lower().startswith("world bank"):
                _apply_sections(device, _world_bank_sections(device))
                stats["world_bank_rewritten"] += 1
                if device.device_type == "institutional_project" and device.validation_status != "admin_only":
                    device.validation_status = "admin_only"
                    stats["world_bank_hidden_from_public"] += 1
                if len(stats["preview"]) < 12:
                    stats["preview"].append(
                        {
                            "source": source_name,
                            "title": device.title,
                            "status": device.status,
                            "validation_status": device.validation_status,
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    stats["dry_run"] = not apply
    return stats


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Nettoie les reformulations restantes Global South et Banque Mondiale.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force-own", action="store_true", help="Recalcule aussi les fiches deja traitees par ce script.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, force_own=args.force_own)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
