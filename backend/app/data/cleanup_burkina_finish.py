from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, compute_completeness


ADMIN_ONLY = {
    "CORAF - veille innovations agricoles et Prix Abdoulaye Toure": (
        "Source de veille agricole utile, mais aucune fenêtre active clairement exploitable n'est confirmée. "
        "A republier seulement lorsqu'un appel ou prix ouvert avec calendrier clair est identifié."
    )
}


UPDATES: dict[str, dict[str, Any]] = {
    "AECF - entrepreneuriat feminin pour une economie plus verte au Benin et au Burkina Faso": {
        "title": "AECF - financement des entreprises féminines vertes au Bénin et au Burkina Faso",
        "country": "Afrique de l'Ouest",
        "region": "Bénin, Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "status": "recurring",
        "is_recurring": True,
        "short_description": (
            "Programme AECF destiné aux entreprises, coopératives et organisations portées par des femmes au Bénin et au Burkina Faso, "
            "avec un objectif de croissance économique verte. La page indique une possibilité de candidature, mais sans échéance unique publiée."
        ),
        "eligibility_criteria": (
            "Cible principale : PME, institutions financières, coopératives ou organisations de femmes actives au Bénin ou au Burkina Faso. "
            "Le projet doit contribuer à l'entrepreneuriat féminin, à l'inclusion économique et à une économie plus verte. "
            "Les critères détaillés doivent être confirmés sur la page AECF avant préparation du dossier."
        ),
        "funding_details": (
            "Le programme est rattaché à une enveloppe globale financée par Affaires mondiales Canada. "
            "Les montants accessibles dépendent de la fenêtre d'investissement, du profil du bénéficiaire et du type de projet. "
            "Vérifier sur AECF la fenêtre actuellement ouverte et les plafonds applicables."
        ),
        "recurrence_notes": (
            "Programme pluriannuel avec fenêtres de financement successives. Aucune échéance unique n'est publiée dans la fiche stockée."
        ),
        "calendar": (
            "Programme pluriannuel. La prochaine fenêtre de candidature doit être confirmée sur la page AECF avant toute décision."
        ),
        "procedure": (
            "Ouvrir la page officielle AECF, vérifier la fenêtre disponible, puis utiliser le bouton ou portail de candidature indiqué par AECF."
        ),
        "checks": (
            "Confirmer la fenêtre actuellement ouverte, le type de bénéficiaire accepté, le montant mobilisable et les pièces demandées."
        ),
        "why": (
            "Bonne piste pour les femmes entrepreneures, coopératives et PME vertes au Burkina Faso, surtout dans l'agriculture, le climat, l'artisanat ou les services productifs."
        ),
        "source_raw": (
            "Programme AECF Investing in Women's Entrepreneurship for a Greener Economy in Benin and Burkina Faso. "
            "La page officielle présente le programme et renvoie vers les fenêtres de financement ouvertes."
        ),
    },
    "FAIJ Burkina Faso - financement de micro-projets jeunes": {
        "status": "recurring",
        "is_recurring": True,
        "short_description": (
            "Guichet national burkinabè destiné aux jeunes porteurs de micro-projets. "
            "Il peut financer des activités génératrices de revenus et créatrices d'emplois, avec accompagnement et suivi."
        ),
        "eligibility_criteria": (
            "Cible principale : jeunes porteurs de projet au Burkina Faso, individuellement ou en collectif, souhaitant lancer ou renforcer une activité économique. "
            "Les conditions exactes, pièces à fournir et secteurs acceptés doivent être vérifiés sur la fiche officielle du service public."
        ),
        "funding_details": (
            "Financement sous forme de prêt pouvant aller jusqu'à 5 000 000 XOF selon le projet et les conditions du fonds. "
            "Le remboursement, les garanties éventuelles et l'accompagnement doivent être confirmés auprès du FAIJ."
        ),
        "recurrence_notes": "Procédure publique permanente : il n'y a pas de campagne unique affichée dans la source officielle.",
        "calendar": "Guichet permanent. La disponibilité effective du fonds doit être vérifiée auprès du service public ou du FAIJ.",
        "procedure": (
            "Consulter la fiche officielle, préparer les justificatifs demandés et contacter le service compétent ou le FAIJ pour déposer la demande."
        ),
        "checks": "Confirmer l'âge requis, les documents à fournir, le plafond accordable, les modalités de remboursement et le lieu de dépôt.",
        "why": "Bonne piste pour un jeune entrepreneur burkinabè avec un micro-projet concret et un besoin de financement modéré.",
    },
    "FASI Burkina Faso - financement de microprojets du secteur informel": {
        "status": "recurring",
        "is_recurring": True,
        "short_description": (
            "Guichet public burkinabè pour les acteurs du secteur informel souhaitant financer un microprojet productif. "
            "Il vise notamment les activités de commerce, artisanat, agriculture, élevage ou services."
        ),
        "eligibility_criteria": (
            "Cible principale : microentrepreneurs, travailleurs non salariés, coopératives, associations ou acteurs du secteur informel au Burkina Faso. "
            "Le projet doit porter sur une activité économique réelle et les conditions exactes doivent être confirmées sur la fiche officielle."
        ),
        "funding_details": (
            "Financement sous forme de prêt pouvant atteindre 1 500 000 XOF selon le type de projet. "
            "Les dépenses couvertes peuvent concerner l'équipement, l'approvisionnement ou les besoins de production, sous réserve des règles du FASI."
        ),
        "recurrence_notes": "Procédure publique permanente pour le secteur informel, sans campagne unique affichée dans la source officielle.",
        "calendar": "Guichet permanent. Vérifier la disponibilité effective du fonds et les délais de traitement auprès du service officiel.",
        "procedure": (
            "Consulter la fiche officielle, préparer le dossier de microprojet et contacter le service compétent ou le FASI pour les modalités de dépôt."
        ),
        "checks": "Confirmer le plafond applicable, les pièces à fournir, les garanties éventuelles, les conditions de remboursement et le lieu de dépôt.",
        "why": "Bonne piste pour un petit entrepreneur informel au Burkina Faso qui cherche un financement de démarrage ou d'équipement.",
    },
    "I&P - financement et accompagnement des PME africaines": {
        "title": "I&P - investissement et accompagnement des PME africaines",
        "country": "Afrique",
        "region": "Afrique subsaharienne",
        "zone": "Afrique subsaharienne",
        "status": "recurring",
        "is_recurring": True,
        "short_description": (
            "Investisseurs & Partenaires finance et accompagne des PME africaines à fort potentiel, avec une logique d'investissement minoritaire et d'appui stratégique. "
            "La prise de contact se fait via la soumission d'un business plan."
        ),
        "eligibility_criteria": (
            "Cible principale : PME et startups formelles basées en Afrique subsaharienne ou dans l'océan Indien, dirigées par des équipes locales. "
            "L'entreprise doit présenter un potentiel de croissance, de création de valeur et d'impact local."
        ),
        "funding_details": (
            "I&P intervient généralement en investissement minoritaire. Les besoins de financement indiqués par la source se situent typiquement entre 300 000 EUR et 1,5 M EUR, "
            "avec certains véhicules adaptés à des tickets inférieurs. Les conditions dépendent du véhicule d'investissement et du profil de l'entreprise."
        ),
        "recurrence_notes": "Investisseur actif en continu : pas de clôture unique, les opportunités sont analysées au fil de l'eau.",
        "calendar": "Soumission au fil de l'eau. Le délai d'analyse initial indiqué par la source est généralement de quelques semaines.",
        "procedure": (
            "Préparer un business plan solide, vérifier les critères d'investissement, puis soumettre le dossier via la page officielle I&P."
        ),
        "checks": "Confirmer le ticket recherché, la zone couverte, la maturité attendue, la structure juridique et les conditions d'entrée au capital.",
        "why": "Bonne piste pour une PME africaine déjà structurée qui cherche un investisseur d'impact plutôt qu'une subvention.",
        "source_raw": (
            "Investisseurs & Partenaires étudie les PME et startups formelles d'Afrique subsaharienne et de l'océan Indien, "
            "avec des besoins de financement généralement compris entre 300 000 EUR et 1,5 M EUR selon les véhicules d'investissement."
        ),
    },
}


def _sections(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": "presentation", "title": "Présentation", "content": data["short_description"], "confidence": 90, "source": "finition Burkina Kafundo"},
        {"key": "eligibility", "title": "Pour qui ?", "content": data["eligibility_criteria"], "confidence": 86, "source": "finition Burkina Kafundo"},
        {"key": "funding", "title": "Montant / avantages", "content": data["funding_details"], "confidence": 84, "source": "finition Burkina Kafundo"},
        {"key": "calendar", "title": "Calendrier", "content": data["calendar"], "confidence": 84, "source": "finition Burkina Kafundo"},
        {"key": "procedure", "title": "Démarche", "content": data["procedure"], "confidence": 82, "source": "finition Burkina Kafundo"},
        {"key": "checks", "title": "À confirmer", "content": data["checks"], "confidence": 80, "source": "finition Burkina Kafundo"},
    ]


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _apply_public_update(device: Device, data: dict[str, Any]) -> None:
    for field in ("title", "country", "region", "zone", "status", "is_recurring", "source_raw"):
        if field in data:
            setattr(device, field, data[field])
    device.short_description = data["short_description"]
    device.eligibility_criteria = data["eligibility_criteria"]
    device.funding_details = data["funding_details"]
    device.recurrence_notes = data["recurrence_notes"]
    device.full_description = build_structured_sections(
        presentation=data["short_description"],
        eligibility=data["eligibility_criteria"],
        funding=data["funding_details"],
        close_date=device.close_date,
        open_date=device.open_date,
        procedure=data["procedure"],
        recurrence_notes=data["recurrence_notes"],
    )
    sections = _sections(data)
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = "burkina-finish-v1"
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    device.language = "fr"
    device.decision_analysis = {
        "go_no_go": "go",
        "recommended_priority": "moyenne",
        "why_interesting": data["why"],
        "why_cautious": data["checks"],
        "points_to_confirm": data["checks"],
        "recommended_action": data["procedure"],
        "urgency_level": "moyenne" if device.close_date else "faible",
        "difficulty_level": "moyenne",
        "effort_level": "moyenne",
        "eligibility_score": 78,
        "strategic_interest": 82,
        "model": "burkina-finish-v1",
    }
    device.decision_analyzed_at = datetime.now(timezone.utc)
    device.completeness_score = compute_completeness(_payload(device))
    device.ai_readiness_score = max(device.ai_readiness_score or 0, 86)
    device.ai_readiness_label = "Prête pour recommandation"
    tags = list(device.tags or [])
    for tag in ("burkina_finish", "fiche_premium"):
        if tag not in tags:
            tags.append(tag)
    device.tags = tags
    device.last_verified_at = datetime.now(timezone.utc)
    device.updated_at = datetime.now(timezone.utc)


def _mark_admin_only(device: Device, reason: str) -> None:
    device.validation_status = "admin_only"
    device.decision_analysis = {
        "go_no_go": "a_verifier",
        "recommended_priority": "faible",
        "why_interesting": "Source utile pour la veille admin, mais pas assez actionnable pour l'utilisateur final.",
        "why_cautious": reason,
        "points_to_confirm": "Identifier une fenêtre active, une page de candidature et un calendrier clair.",
        "recommended_action": "Ne pas afficher côté utilisateur tant qu'une opportunité active n'est pas confirmée.",
        "urgency_level": "faible",
        "difficulty_level": "moyenne",
        "effort_level": "moyenne",
        "eligibility_score": 35,
        "strategic_interest": 60,
        "model": "burkina-finish-v1",
    }
    device.ai_readiness_score = 55
    device.ai_readiness_label = "Réservée à la veille admin"
    tags = list(device.tags or [])
    for tag in ("burkina_finish", "admin_only_watch_source"):
        if tag not in tags:
            tags.append(tag)
    device.tags = tags
    device.last_verified_at = datetime.now(timezone.utc)
    device.updated_at = datetime.now(timezone.utc)


async def run(apply: bool = False) -> dict[str, Any]:
    titles = list(UPDATES) + list(ADMIN_ONLY)
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.title.in_(titles)).order_by(Device.title.asc()))).scalars().all()
        updated = []
        for device in devices:
            before = {
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "short": (device.short_description or "")[:160],
            }
            if device.title in ADMIN_ONLY:
                _mark_admin_only(device, ADMIN_ONLY[device.title])
            else:
                _apply_public_update(device, UPDATES[device.title])
            updated.append(
                {
                    "before": before,
                    "after": {
                        "title": device.title,
                        "status": device.status,
                        "validation_status": device.validation_status,
                        "short": (device.short_description or "")[:180],
                    },
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "updated_count": len(updated), "updated": updated}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Finition premium des 5 fiches Burkina restantes.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
