from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


TARGETS: dict[str, dict[str, Any]] = {
    "AECF - financement des entreprises féminines vertes au Bénin et au Burkina Faso": {
        "presentation": (
            "Programme AECF destiné aux entreprises, coopératives et organisations portées par des femmes au Bénin et au Burkina Faso. "
            "Il vise des projets de croissance économique verte, notamment dans les chaînes de valeur locales, l'agriculture, l'énergie ou les activités génératrices de revenus durables."
        ),
        "eligibility": (
            "Priorité aux entreprises et organisations féminines ou dirigées par des femmes, implantées au Bénin ou au Burkina Faso, avec une activité économique démontrable et un projet à impact environnemental ou social."
        ),
        "funding": (
            "Le programme peut combiner financement, accompagnement technique et appui au développement d'activité. La page ne publie pas une enveloppe unique permanente : vérifier la fenêtre ouverte et les modalités exactes sur AECF."
        ),
        "procedure": (
            "Consulter la page officielle AECF, vérifier si un appel est actuellement ouvert, puis préparer les informations sur l'entreprise, le projet, l'impact attendu et les justificatifs demandés."
        ),
        "checks": "Confirmer la fenêtre de candidature, le pays éligible, les secteurs retenus et le montant disponible avant de préparer un dossier.",
        "recurrence_notes": "Programme pluriannuel avec fenêtres de financement successives selon les appels AECF.",
    },
    "FNDA Benin - financement des projets agricoles": {
        "presentation": (
            "Guichet du Fonds National de Développement Agricole du Bénin pour faciliter le financement de projets agricoles. "
            "La plateforme partenaires permet de suivre ou soumettre des demandes liées aux facilités du FNDA."
        ),
        "eligibility": (
            "S'adresse aux promoteurs agricoles, organisations professionnelles, institutions financières ou acteurs de services agricoles selon le guichet concerné. Les conditions varient selon la facilité FNDA utilisée."
        ),
        "funding": (
            "Le FNDA intervient à travers des mécanismes de subvention, garantie, bonification ou facilitation d'accès au crédit. Les montants dépendent du guichet, du projet et du partenaire financier."
        ),
        "procedure": (
            "Passer par la plateforme officielle des partenaires FNDA ou par l'appel publié. Choisir l'instance de soumission effective uniquement pour une demande réelle."
        ),
        "checks": "Vérifier le guichet ouvert, les filières admissibles, les partenaires financiers concernés et les pièces exigées.",
        "recurrence_notes": "Guichet permanent avec appels ou sessions selon les dispositifs FNDA.",
    },
    "MTN Innovation Lab Bénin - incubation de jeunes entreprises numériques": {
        "presentation": (
            "MTN Innovation Lab Bénin accompagne des porteurs de solutions numériques, startups et jeunes entreprises innovantes. "
            "La fiche est utile pour les projets qui cherchent mentorat, incubation, réseau ou préparation à la croissance."
        ),
        "eligibility": (
            "Cible principalement les startups, entrepreneurs numériques, jeunes porteurs de solutions technologiques ou projets innovants pouvant bénéficier d'un accompagnement entrepreneurial."
        ),
        "funding": (
            "L'avantage principal est l'accompagnement : mentorat, incubation, réseau, visibilité et accès à un écosystème tech. Un appui financier éventuel dépend des programmes ou cohortes ouvertes."
        ),
        "procedure": (
            "Consulter la plateforme officielle du MTN Innovation Lab Bénin, vérifier les programmes ouverts et suivre la procédure de candidature ou de prise de contact indiquée."
        ),
        "checks": "Confirmer la cohorte active, le type d'accompagnement disponible, les critères de sélection et les dates de candidature.",
        "recurrence_notes": "Programme d'accompagnement récurrent selon les cohortes et appels MTN Innovation Lab.",
    },
    "I&P - investissement et accompagnement des PME africaines": {
        "presentation": (
            "Investisseurs & Partenaires finance et accompagne des PME africaines à fort potentiel. "
            "Cette fiche concerne surtout les entreprises déjà structurées qui cherchent un investisseur patient, un accompagnement stratégique et un appui à la croissance."
        ),
        "eligibility": (
            "Cible des PME africaines formalisées, avec une activité réelle, un potentiel de croissance, une équipe dirigeante solide et un besoin de financement en capital ou quasi-capital."
        ),
        "funding": (
            "L'appui prend la forme d'un investissement minoritaire, souvent complété par un accompagnement stratégique, financier et opérationnel. Le ticket et les conditions dépendent du profil de l'entreprise."
        ),
        "procedure": (
            "Soumettre un business plan via la page officielle I&P, en présentant clairement l'activité, le marché, les chiffres clés, le besoin de financement et l'impact attendu."
        ),
        "checks": "Vérifier le pays couvert par les véhicules I&P, le stade de maturité demandé, le ticket d'investissement et les documents nécessaires.",
        "recurrence_notes": "Guichet de prise de contact permanent pour PME africaines en recherche d'investissement.",
    },
    "FIN CULTURE Cote d'Ivoire - prets pour industries culturelles et creatives": {
        "presentation": (
            "FIN CULTURE est un guichet de financement destiné aux acteurs des industries culturelles et créatives en Côte d'Ivoire. "
            "Il vise à soutenir les projets culturels structurés, avec une logique de prêt ou d'appui financier encadré."
        ),
        "eligibility": (
            "S'adresse aux entreprises, porteurs de projets ou acteurs culturels ivoiriens opérant dans les industries créatives : arts, audiovisuel, production culturelle, patrimoine, design ou services associés."
        ),
        "funding": (
            "Le dispositif repose principalement sur un prêt ou financement remboursable. Les montants, garanties, taux et échéances doivent être vérifiés sur la page officielle du guichet."
        ),
        "procedure": (
            "Consulter la page officielle FIN CULTURE, vérifier l'ouverture du guichet, puis préparer le dossier projet, le budget, les justificatifs et les pièces administratives demandées."
        ),
        "checks": "Confirmer que le guichet est encore ouvert, le plafond de financement, les conditions de remboursement et les pièces exigées.",
        "recurrence_notes": "Guichet ou appel récurrent selon les campagnes publiées par le ministère et ses partenaires.",
    },
    "FONSTI Cote d'Ivoire - guichets recherche, innovation et entrepreneuriat": {
        "presentation": (
            "Le FONSTI publie des appels à projets pour soutenir la recherche, l'innovation, la technologie et l'entrepreneuriat en Côte d'Ivoire. "
            "Cette fiche est pertinente pour les projets innovants adossés à une démarche de recherche, de prototypage ou de valorisation."
        ),
        "eligibility": (
            "S'adresse selon les appels aux chercheurs, équipes de recherche, innovateurs, startups, entrepreneurs technologiques ou structures partenaires capables de porter un projet structuré."
        ),
        "funding": (
            "L'appui peut prendre la forme d'une subvention ou d'un financement de projet. Les montants, thématiques et dépenses éligibles changent selon chaque appel FONSTI."
        ),
        "procedure": (
            "Consulter la page officielle des appels FONSTI, identifier l'appel actif, télécharger les documents et respecter les modalités de dépôt indiquées."
        ),
        "checks": "Vérifier la thématique ouverte, la date limite, les bénéficiaires admissibles, le budget disponible et le format du dossier.",
        "recurrence_notes": "Appels à projets récurrents, publiés par fenêtre selon les thématiques FONSTI.",
    },
}


def _section(key: str, title: str, content: str, confidence: int = 82) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": "reformulation métier Kafundo",
    }


def _sections(device: Device, data: dict[str, Any]) -> list[dict[str, Any]]:
    if device.close_date:
        calendar = f"Date limite indiquée : {device.close_date:%d/%m/%Y}. Vérifier la date sur la source officielle avant tout dépôt."
    else:
        calendar = data.get("recurrence_notes") or "Opportunité récurrente : aucune date limite unique n'est publiée."
    return [
        _section("presentation", "Présentation", data["presentation"], 88),
        _section("eligibility", "Critères d'éligibilité", data["eligibility"], 82),
        _section("funding", "Montant / avantages", data["funding"], 80),
        _section("calendar", "Calendrier", calendar, 80),
        _section("procedure", "Démarche", data["procedure"], 78),
        _section("checks", "Points à vérifier", data["checks"], 74),
    ]


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def run(apply: bool) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Device).where(Device.title.in_(TARGETS.keys())))
        devices = list(result.scalars().all())
        found = {device.title for device in devices}
        report: dict[str, Any] = {"updated": [], "missing": sorted(set(TARGETS) - found)}

        for device in devices:
            data = TARGETS[device.title]
            sections = _sections(device, data)
            full_description = build_structured_sections(
                presentation=data["presentation"],
                eligibility=data["eligibility"],
                funding=data["funding"],
                close_date=device.close_date,
                open_date=device.open_date,
                procedure=data["procedure"],
                recurrence_notes=data.get("recurrence_notes"),
            )
            report["updated"].append(
                {
                    "title": device.title,
                    "old_short": (device.short_description or "")[:180],
                    "new_short": data["presentation"][:220],
                }
            )
            if apply:
                device.short_description = clean_editorial_text(data["presentation"])
                device.full_description = full_description
                device.eligibility_criteria = clean_editorial_text(data["eligibility"])
                device.funding_details = clean_editorial_text(data["funding"])
                device.recurrence_notes = clean_editorial_text(data.get("recurrence_notes") or device.recurrence_notes or "")
                device.content_sections_json = sections
                device.ai_rewritten_sections_json = sections
                device.ai_rewrite_status = "done"
                device.ai_rewrite_model = "manual-country-wording-v1"
                device.ai_rewrite_checked_at = datetime.now(timezone.utc)
                device.language = "fr"
                device.ai_readiness_score = max(device.ai_readiness_score or 0, 86)
                device.ai_readiness_label = "pret_recommandation"
                device.ai_readiness_reasons = ["texte métier reformulé", "source officielle conservée", "sections décisionnelles"]
                device.completeness_score = compute_completeness(_payload(device))
                device.updated_at = datetime.now(timezone.utc)

        if apply:
            await session.commit()
        else:
            await session.rollback()

        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
