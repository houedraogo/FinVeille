from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


TARGET_COUNTRIES = [
    "Burkina Faso",
    "Benin",
    "Bénin",
    "Côte d'Ivoire",
    "Cote d'Ivoire",
    "Afrique de l'Ouest",
    "Afrique",
]

PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours"]

ENTREPRENEUR_BENEFICIARIES = [
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
]

ENGLISH_MARKERS = (
    " call for applications ",
    " funding opportunity ",
    " opens applications ",
    " apply by ",
)

GENERIC_MARKERS = (
    "les beneficiaires eligibles et les conditions d'acces doivent etre confirmes",
    "le montant exact ou les avantages associes doivent etre confirmes",
    "opportunite de financement relayee",
)


def _format_amount(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}".replace(",", " ")
    return f"{number:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def _norm(value: str | None) -> str:
    return clean_editorial_text(value or "").lower()


def _as_payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _label_type(device_type: str | None) -> str:
    return {
        "subvention": "financement",
        "pret": "prêt",
        "aap": "appel à projets",
        "accompagnement": "programme d'accompagnement",
        "garantie": "garantie",
        "concours": "concours",
    }.get(str(device_type or "").lower(), "opportunité")


def _needs_cleanup(device: Device) -> bool:
    text = _norm(" ".join([device.title or "", device.short_description or "", device.eligibility_criteria or "", device.funding_details or ""]))
    if any(marker in text for marker in ENGLISH_MARKERS):
        return True
    if any(marker in text for marker in GENERIC_MARKERS):
        return True
    if not device.eligibility_criteria or len(device.eligibility_criteria.strip()) < 80:
        return True
    if not device.funding_details or len(device.funding_details.strip()) < 80:
        return True
    return False


def _funding_text(device: Device) -> str:
    dtype = str(device.device_type or "").lower()
    if device.amount_max:
        return f"Montant maximum connu : {_format_amount(device.amount_max)} {device.currency or 'EUR'}. Vérifier les plafonds, cofinancements et conditions exactes sur la source officielle."
    if dtype == "pret":
        return (
            "L'aide prend principalement la forme d'un prêt ou d'un financement remboursable. "
            "Le montant, le taux, les garanties éventuelles et les modalités de remboursement doivent être confirmés sur la source officielle."
        )
    if dtype == "accompagnement":
        return (
            "L'avantage principal est un accompagnement : appui technique, mentorat, incubation, mise en relation ou préparation au financement. "
            "Un appui financier peut exister selon les cohortes ; il doit être confirmé sur la source officielle."
        )
    if dtype == "concours":
        return (
            "L'avantage peut prendre la forme d'un prix, d'une dotation, d'un accompagnement, de visibilité ou d'une mise en relation avec des partenaires. "
            "Le montant exact et les avantages non financiers doivent être confirmés sur la page officielle."
        )
    return (
        "L'opportunité peut donner accès à une subvention, un cofinancement, un appui technique ou un avantage équivalent selon les règles du programme. "
        "Le montant exact, les dépenses éligibles et les contreparties doivent être vérifiés sur la source officielle."
    )


def _calendar_text(device: Device) -> str:
    if device.close_date:
        return f"Date limite indiquée : {device.close_date:%d/%m/%Y}. Il est conseillé de vérifier la date sur la source officielle avant de déposer un dossier."
    if device.status == "recurring" or device.is_recurring:
        return "Opportunité récurrente ou permanente : aucune date limite unique n'est publiée. Vérifier si une session, cohorte ou fenêtre de candidature est ouverte."
    return "Date limite non confirmée : vérifier la source officielle avant toute décision."


def _sections(device: Device, presentation: str, eligibility: str, funding: str, procedure: str, checks: str) -> list[dict[str, Any]]:
    return [
        {"key": "presentation", "title": "Présentation", "content": presentation, "confidence": 86, "source": "nettoyage visible Kafundo"},
        {"key": "eligibility", "title": "Critères d'éligibilité", "content": eligibility, "confidence": 78, "source": "nettoyage visible Kafundo"},
        {"key": "funding", "title": "Montant / avantages", "content": funding, "confidence": 76, "source": "nettoyage visible Kafundo"},
        {"key": "calendar", "title": "Calendrier", "content": _calendar_text(device), "confidence": 80, "source": "nettoyage visible Kafundo"},
        {"key": "procedure", "title": "Démarche", "content": procedure, "confidence": 76, "source": "nettoyage visible Kafundo"},
        {"key": "checks", "title": "Points à vérifier", "content": checks, "confidence": 72, "source": "nettoyage visible Kafundo"},
    ]


def _clean_device(device: Device) -> bool:
    if not _needs_cleanup(device):
        return False

    dtype = _label_type(device.device_type)
    country = clean_editorial_text(device.country or device.zone or "Afrique")
    sectors = ", ".join(device.sectors or []) or "les secteurs indiqués par la source"
    beneficiaries = ", ".join(device.beneficiaries or []) or "entrepreneurs, PME, startups ou porteurs de projet éligibles"

    presentation = clean_editorial_text(
        f"{device.title} est un {dtype} à suivre pour {country}. "
        f"Cette opportunité concerne principalement {sectors}. "
        "Elle est présentée ici pour aider à décider rapidement si elle mérite une vérification ou une candidature."
    )
    eligibility = clean_editorial_text(
        f"Publics à vérifier : {beneficiaries}. "
        "Les critères précis peuvent dépendre du secteur, de la localisation, du stade du projet et des pièces demandées par l'organisme source."
    )
    funding = clean_editorial_text(_funding_text(device))
    procedure = clean_editorial_text(
        "Consulter la source officielle, vérifier la date limite et les critères, puis préparer les informations demandées avant toute candidature."
    )
    checks = clean_editorial_text(
        "Confirmer la date limite, le montant ou l'avantage exact, les bénéficiaires admissibles et la procédure de dépôt sur la source officielle."
    )

    sections = _sections(device, presentation, eligibility, funding, procedure, checks)
    full_description = build_structured_sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        close_date=device.close_date,
        open_date=device.open_date,
        procedure=procedure,
        recurrence_notes=device.recurrence_notes,
    )

    device.short_description = presentation
    device.eligibility_criteria = eligibility
    device.funding_details = funding
    device.full_description = full_description
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = "visible-target-cleanup-v1"
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    device.language = "fr"
    device.completeness_score = compute_completeness(_as_payload(device))
    device.updated_at = datetime.now(timezone.utc)
    return True


async def run(apply: bool = False) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        service = DeviceService(db)
        result = await service.search(
            DeviceSearchParams(
                countries=TARGET_COUNTRIES,
                device_types=PUBLIC_TYPES,
                beneficiaries=ENTREPRENEUR_BENEFICIARIES,
                actionable_now=True,
                sort_by="relevance",
                sort_desc=True,
                page=1,
                page_size=50,
            )
        )
        ids = [device.id for device in result["items"]]
        devices = (await db.execute(select(Device).where(Device.id.in_(ids)))).scalars().all()

        updated = 0
        preview: list[dict[str, Any]] = []
        for device in devices:
            before = {
                "title": device.title,
                "short": (device.short_description or "")[:160],
                "funding": (device.funding_details or "")[:160],
            }
            if _clean_device(device):
                updated += 1
                if len(preview) < 20:
                    preview.append(
                        {
                            "title": device.title,
                            "before": before,
                            "after_short": (device.short_description or "")[:220],
                            "after_funding": (device.funding_details or "")[:220],
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "visible_total": result["total"], "updated": updated, "preview": preview}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Nettoie les fiches visibles Burkina, Benin, Cote d'Ivoire.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
