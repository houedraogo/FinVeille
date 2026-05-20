from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness, normalize_title


VISIBLE_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_DECISIONS = {None, "publish", "publish_with_caution"}
TARGET_COUNTRIES = {
    "Afrique",
    "Afrique de l'Ouest",
    "Burkina Faso",
    "Benin",
    "Bénin",
    "BÃ©nin",
    "Cote d'Ivoire",
    "Côte d'Ivoire",
    "CÃ´te d'Ivoire",
}

TITLE_FIXES = {
    "Common Fund for Commodities - appel a propositions pour PME agricoles": "Fonds commun pour les produits de base - appel à propositions pour PME agricoles",
    "RISE 2 Benin - acceleration et financement des PME et startups": "RISE 2 Bénin - accélération et financement des PME et startups",
    "RISE 2 Benin - appui technique et financier pour TPE/PME": "RISE 2 Bénin - appui technique et financier pour TPE/PME",
    "Orange Corners Benin - subventions OCIAC et OCIF 2026": "Orange Corners Bénin - subventions OCIAC et OCIF 2026",
    "SOE Benin 2026 - rencontres investisseurs et opportunites business": "SOE Bénin 2026 - rencontres investisseurs et opportunités business",
    "AfCFTA Startup Acceleration 2026 - startups africaines a fort potentiel": "Programme d'accélération AfCFTA 2026 pour startups africaines",
    "Prix Pierre Castel 2026 - entrepreneurs des systemes alimentaires": "Prix Pierre Castel 2026 - entrepreneurs des systèmes alimentaires",
    "Investing for Employment - subventions emploi Cote d'Ivoire 2026": "Investing for Employment - subventions emploi Côte d'Ivoire 2026",
    "Cote d'Ivoire PME - accompagnement des PME a la levee de fonds": "Côte d'Ivoire PME - accompagnement des PME à la levée de fonds",
    "FONSTI Cote d'Ivoire - guichets recherche, innovation et entrepreneuriat": "FONSTI Côte d'Ivoire - guichets recherche, innovation et entrepreneuriat",
    "FNEC Benin - appels environnement et climat": "FNEC Bénin - appels environnement et climat",
    "AFP-PME Burkina Faso - financement et promotion des PME": "AFP-PME Burkina Faso - financement et promotion des PME",
    "FIN CULTURE Cote d'Ivoire - prets pour industries culturelles et creatives": "FIN CULTURE Côte d'Ivoire - prêts pour industries culturelles et créatives",
    "FCI4Africa Open Call 1 - jusqu'a 50 000 EUR pour l'innovation alimentaire": "FCI4Africa - appel 1 jusqu'à 50 000 EUR pour l'innovation alimentaire",
    "FCI4Africa Open Call 1 - jusqu'à 50 000 EUR pour l'innovation alimentaire": "FCI4Africa - appel 1 jusqu'à 50 000 EUR pour l'innovation alimentaire",
}

TEXT_REPLACEMENTS = {
    "Benin": "Bénin",
    "beninoises": "béninoises",
    "beninois": "béninois",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Cote d’Ivoire": "Côte d’Ivoire",
    "systemes": "systèmes",
    "acceleration": "accélération",
    "accelerateur": "accélérateur",
    "accompagnement": "accompagnement",
    "opportunites": "opportunités",
    "opportunite": "opportunité",
    "energie": "énergie",
    "numerique": "numérique",
    "selectionner": "sélectionner",
    "mecanisme": "mécanisme",
    "developpent": "développent",
    "developper": "développer",
    "developpement": "développement",
    "marche": "marché",
    "marches": "marchés",
    "demarres": "démarrés",
    "durables": "durables",
    "acces": "accès",
    "le financement a suivre": "le financement à suivre",
    "opportunité a suivre": "opportunité à suivre",
    "a fort potentiel": "à fort potentiel",
    "destine a": "destiné à",
    "base au": "basé au",
    "engagees": "engagées",
    "modele": "modèle",
    "equipe": "équipe",
    "prets": "prêts",
    "creatives": "créatives",
    "projets energies": "projets énergies",
    "vià": "via",
    "àu": "au",
    "Demarché": "Démarche",
    "Démarché": "Démarche",
    "Demarche": "Démarche",
    "Presentation": "Présentation",
    "Verifier": "Vérifier",
    "eligibilite": "éligibilité",
    "eligibles": "éligibles",
    "fenetre": "fenêtre",
    "fenetres": "fenêtres",
    "modalites": "modalités",
    "deposer": "déposer",
    "resilience": "résilience",
    "communautes": "communautés",
    "marginalisees": "marginalisées",
    "activites generatrices": "activités génératrices",
    "competences": "compétences",
    "mobilite": "mobilité",
    "appel a projets": "appel à projets",
    "appels a projets": "appels à projets",
    "a surveiller": "à surveiller",
    "a projets": "à projets",
    "sante": "santé",
    "priorites": "priorités",
    "thematique": "thématique",
    "thematiques": "thématiques",
    "reelle": "réelle",
    "reels": "réels",
    "reel": "réel",
    "Opportunite": "Opportunité",
    "opportunité intéressanté": "opportunité intéressante",
    "intéressanté": "intéressante",
    "edition": "édition",
    "ecosysteme": "écosystème",
    "coreen": "coréen",
    "creant": "créant",
    "generer": "générer",
    "prive": "privé",
    "economie": "économie",
    "economies": "économies",
    "energetique": "énergétique",
    "selection": "sélection",
    "selectionner": "sélectionner",
    "deja": "déjà",
    "capacite": "capacité",
    "maturite": "maturité",
    "categorie": "catégorie",
    "pieces": "pièces",
    "delais": "délais",
    "criteres": "critères",
    "coherente": "cohérente",
    "evaluable": "évaluable",
    "academiques": "académiques",
    "regionales": "régionales",
    "beneficiaires": "bénéficiaires",
    "immediatement": "immédiatement",
    "portees": "portées",
    "alignees": "alignées",
    "evaluée": "évaluée",
    "porteurs eligibles": "porteurs éligibles",
    "aider les": "aider les",
    "vise a": "vise à",
    "visant a": "visant à",
    "cherche a": "cherche à",
    "cherchent a": "cherchent à",
    "aider a": "aider à",
    "a se": "à se",
    "acceder a": "accéder à",
    "jusqu'a": "jusqu'à",
    "porte par": "porté par",
    "portee par": "portée par",
    "accès a": "accès à",
    "appel a candidatures": "appel à candidatures",
    "L'appel a": "L'appel à",
    "l'appel a": "l'appel à",
    "L'edition": "L'édition",
    "La selection": "La sélection",
    "la selection": "la sélection",
    "la langue": "la langue",
    "là langue": "la langue",
    "là session": "la session",
    "etre ": "être ",
    "confirmees": "confirmées",
    "confirmes": "confirmés",
    "depot": "dépôt",
    "formalisees": "formalisées",
    "financiere": "financière",
    "operationnelle": "opérationnelle",
    "viabilite": "viabilité",
    "detailles": "détaillés",
    "perimetre": "périmètre",
    "geographique": "géographique",
    "liees a": "liées à",
    "feminines": "féminines",
    "developpement": "développement",
    "publie": "publié",
    "publies": "publiés",
    "publiee": "publiée",
    "depend": "dépend",
    "dependent": "dépendent",
}

COUNTRY_FIXES = {
    "Benin": "Bénin",
    "BÃ©nin": "Bénin",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "CÃ´te d'Ivoire": "Côte d'Ivoire",
}


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _polish_text(value: str | None) -> str | None:
    if not value:
        return value
    text = value
    for before, after in TEXT_REPLACEMENTS.items():
        text = text.replace(before, after)
    text = text.replace("àu", "au").replace("àux", "aux")
    return text


def _polish_json(value: Any) -> Any:
    if isinstance(value, str):
        return _polish_text(value)
    if isinstance(value, list):
        return [_polish_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _polish_json(item) for key, item in value.items()}
    return value


def _append_tag(device: Device, tag: str) -> None:
    tags = set(device.tags or [])
    tags.add(tag)
    device.tags = sorted(tags)


def _is_target_visible(device: Device) -> bool:
    if device.validation_status not in VISIBLE_STATUSES:
        return False
    if device.user_quality_decision not in VISIBLE_DECISIONS:
        return False
    return (device.country in TARGET_COUNTRIES) or (device.region in TARGET_COUNTRIES) or (device.zone in TARGET_COUNTRIES)


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    Device.validation_status.in_(list(VISIBLE_STATUSES)),
                    Device.status.in_(["open", "recurring"]),
                )
            )
        ).scalars().all()

        for device in devices:
            if not _is_target_visible(device):
                continue

            before = {
                "title": device.title,
                "country": device.country,
                "region": device.region,
            }

            title = TITLE_FIXES.get(device.title or "", _polish_text(device.title) or device.title)
            device.title = title
            device.title_normalized = normalize_title(title) if title else device.title_normalized

            if device.country in COUNTRY_FIXES:
                device.country = COUNTRY_FIXES[device.country]
            if device.region in COUNTRY_FIXES:
                device.region = COUNTRY_FIXES[device.region]
            if device.zone in COUNTRY_FIXES:
                device.zone = COUNTRY_FIXES[device.zone]

            for field in (
                "short_description",
                "full_description",
                "eligibility_criteria",
                "funding_details",
                "specific_conditions",
                "required_documents",
                "recurrence_notes",
                "auto_summary",
            ):
                setattr(device, field, _polish_text(getattr(device, field)))

            device.content_sections_json = _polish_json(device.content_sections_json)
            device.ai_rewritten_sections_json = _polish_json(device.ai_rewritten_sections_json)
            device.language = "fr"
            device.ai_rewrite_status = "done"
            device.ai_rewrite_checked_at = now
            device.ai_rewrite_model = device.ai_rewrite_model or "visible-africa-launch-polish-v1"
            device.completeness_score = compute_completeness(_payload(device))
            device.updated_at = now
            _append_tag(device, "visible_africa_polished")

            after = {
                "title": device.title,
                "country": device.country,
                "region": device.region,
            }
            if before != after:
                changed.append({"id": str(device.id), "before": before, "after": after})

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": len(changed), "items": changed[:40]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Polish visible African launch devices.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
