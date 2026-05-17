from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


UPDATES: dict[str, dict[str, Any]] = {
    "Hub Ivoire Tech - accompagnement startups en Cote d'Ivoire": {
        "title": "Hub Ivoire Tech - accompagnement de jeunes entreprises innovantes en Côte d'Ivoire",
        "short": "Hub Ivoire Tech accompagne les jeunes entreprises innovantes en Côte d'Ivoire, notamment dans le numérique, la technologie et l'innovation. Cette opportunité est utile pour structurer un projet, accéder à un réseau et préparer une levée de fonds ou un partenariat.",
        "eligibility": "Publics à vérifier : entrepreneurs, PME innovantes, porteurs de projet numérique et jeunes entreprises technologiques basées en Côte d'Ivoire. Vérifier les conditions exactes, le stade d'avancement attendu et les pièces demandées sur la source officielle.",
        "funding": "L'avantage principal est un accompagnement : incubation, mentorat, appui business, réseau et préparation au financement. Un financement direct n'est pas systématiquement garanti et doit être confirmé sur la source officielle.",
    },
    "MTN Innovation Lab Benin - incubation startups": {
        "title": "MTN Innovation Lab Bénin - incubation de jeunes entreprises numériques",
        "short": "MTN Innovation Lab Bénin accompagne les jeunes entreprises numériques et les porteurs de solutions innovantes. Cette opportunité peut aider à tester une solution, bénéficier d'un mentorat et accéder à un écosystème entrepreneurial.",
        "eligibility": "Publics à vérifier : entrepreneurs, jeunes entreprises numériques, porteurs de projet innovant et équipes basées ou actives au Bénin. Vérifier les critères d'éligibilité, le calendrier et les modalités de candidature sur la source officielle.",
        "funding": "L'appui est principalement non financier : incubation, mentorat, accès à un réseau, accompagnement technique et visibilité. Les éventuelles dotations ou avantages financiers doivent être confirmés sur la source officielle.",
    },
    "Fonds Google for Startups pour fondateurs africains": {
        "title": "Fonds Google pour fondateurs africains",
        "short": "Ce fonds soutient des fondateurs africains à fort potentiel, en particulier des entreprises technologiques en croissance. L'intérêt principal est l'accès à un appui financier, à du mentorat et à l'écosystème Google.",
        "eligibility": "Publics à vérifier : fondateurs africains, jeunes entreprises technologiques et équipes en phase de croissance. Confirmer les pays éligibles, le stade attendu, les secteurs ciblés et les dates de candidature sur la source officielle.",
        "funding": "L'opportunité peut inclure un appui financier, du mentorat, des crédits ou avantages techniques et de la visibilité. Les montants, cohortes ouvertes et conditions doivent être vérifiés sur la source officielle.",
    },
    "Villgro Africa - incubation et financement sante en Afrique": {
        "title": "Villgro Africa - incubation et financement santé en Afrique",
        "short": "Villgro Africa accompagne des entreprises africaines qui développent des solutions en santé, medtech et sciences de la vie. L'opportunité est intéressante pour les projets qui cherchent un appui business, technique et investisseur.",
        "eligibility": "Publics à vérifier : entreprises de santé, medtech, sciences de la vie et innovations à impact en Afrique. Vérifier le stade du projet, les pays couverts, les critères d'impact et les modalités de candidature sur la source officielle.",
        "funding": "L'appui peut combiner incubation, préparation à l'investissement, mentorat, réseau et financement selon les dossiers. Les montants et conditions de financement doivent être confirmés sur la source officielle.",
    },
    "Villgro Africa - programme d'incubation": {
        "title": "Villgro Africa - programme d'incubation santé et impact",
        "short": "Villgro Africa propose un accompagnement pour des entreprises africaines de santé et d'impact. Cette fiche doit être lue comme une opportunité récurrente à vérifier avant candidature.",
        "eligibility": "Publics à vérifier : entreprises africaines de santé, medtech, sciences de la vie et innovations à impact. Confirmer les critères de sélection, le stade attendu et les pays couverts sur la source officielle.",
        "funding": "L'avantage peut inclure incubation, mentorat, accompagnement technique, préparation à l'investissement et financement selon les cas. Les montants et modalités doivent être confirmés sur la source officielle.",
    },
    "Google for Startups Accelerator Africa": {
        "title": "Accélérateur Google pour jeunes entreprises africaines",
        "short": "Cet accélérateur accompagne des jeunes entreprises africaines à fort potentiel, surtout dans le numérique et la technologie. Il peut apporter du mentorat, un appui produit, de la visibilité et un accès à un réseau international.",
        "eligibility": "Publics à vérifier : jeunes entreprises africaines, fondateurs de solutions numériques et équipes en phase de croissance. Vérifier les pays éligibles, le stade de développement, les secteurs ciblés et les dates de candidature sur la source officielle.",
        "funding": "L'appui est principalement un accompagnement : mentorat, expertise produit, réseau, visibilité et avantages techniques. Les dotations, crédits ou éventuels financements doivent être confirmés sur la source officielle.",
    },
    "Digital Energy Challenge 2026 pour PME de l'énergie en Afrique": {
        "title": "Digital Energy Challenge 2026 pour PME de l'énergie en Afrique",
        "short": "Digital Energy Challenge 2026 soutient des PME africaines qui développent des solutions numériques pour le secteur de l'énergie. Cette opportunité est intéressante pour les entreprises qui veulent financer ou accélérer une innovation liée à l'accès à l'énergie, au climat ou aux infrastructures numériques.",
        "eligibility": "Publics à vérifier : PME, entreprises innovantes et organisations actives dans l'énergie digitale en Afrique. Vérifier les pays éligibles, le stade du projet, les secteurs retenus et les pièces à fournir sur la source officielle.",
        "funding": "L'opportunité peut inclure un financement, un accompagnement technique, de la visibilité et une mise en relation avec des partenaires. Les montants, dépenses éligibles et conditions de cofinancement doivent être confirmés sur la source officielle.",
    },
}


def _sections(device: Device, data: dict[str, Any]) -> list[dict[str, Any]]:
    calendar = (
        f"Date limite indiquée : {device.close_date:%d/%m/%Y}. Vérifier la date sur la source officielle avant de candidater."
        if device.close_date
        else "Opportunité récurrente ou à calendrier variable : vérifier si une session est ouverte sur la source officielle."
    )
    procedure = "Consulter la source officielle, vérifier les critères et préparer les informations demandées avant toute candidature."
    checks = "Confirmer la date, les critères, les avantages exacts et la procédure de dépôt sur la source officielle."
    return [
        {"key": "presentation", "title": "Présentation", "content": data["short"], "confidence": 88, "source": "nettoyage visible Kafundo"},
        {"key": "eligibility", "title": "Critères d'éligibilité", "content": data["eligibility"], "confidence": 80, "source": "nettoyage visible Kafundo"},
        {"key": "funding", "title": "Montant / avantages", "content": data["funding"], "confidence": 78, "source": "nettoyage visible Kafundo"},
        {"key": "calendar", "title": "Calendrier", "content": calendar, "confidence": 78, "source": "nettoyage visible Kafundo"},
        {"key": "procedure", "title": "Démarche", "content": procedure, "confidence": 78, "source": "nettoyage visible Kafundo"},
        {"key": "checks", "title": "Points à vérifier", "content": checks, "confidence": 74, "source": "nettoyage visible Kafundo"},
    ]


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def run(apply: bool = False) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.title.in_(list(UPDATES.keys()))))
        ).scalars().all()

        updated: list[dict[str, str]] = []
        now = datetime.now(timezone.utc)
        for device in devices:
            data = UPDATES.get(device.title)
            if not data:
                continue
            before = device.title
            sections = _sections(device, data)
            procedure = next(section["content"] for section in sections if section["key"] == "procedure")
            device.title = data["title"]
            device.title_normalized = data["title"].lower()
            device.short_description = clean_editorial_text(data["short"])
            device.eligibility_criteria = clean_editorial_text(data["eligibility"])
            device.funding_details = clean_editorial_text(data["funding"])
            device.content_sections_json = sections
            device.ai_rewritten_sections_json = sections
            device.ai_rewrite_status = "done"
            device.ai_rewrite_model = "visible-target-wording-v1"
            device.ai_rewrite_checked_at = now
            device.language = "fr"
            device.full_description = build_structured_sections(
                presentation=device.short_description,
                eligibility=device.eligibility_criteria,
                funding=device.funding_details,
                close_date=device.close_date,
                open_date=device.open_date,
                procedure=procedure,
                recurrence_notes=device.recurrence_notes,
            )
            device.completeness_score = compute_completeness(_payload(device))
            device.updated_at = now
            updated.append({"before": before, "after": device.title})

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "updated": len(updated), "items": updated}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Francise les fiches visibles restantes sur les pays cibles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
