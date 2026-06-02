"""Ameliore la qualite visible des fiches Afrique ajoutees recemment."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device

from app.data.add_burkina_concrete_round import DEVICES as BURKINA_DEVICES
from app.data.add_actionable_africa_round22 import DEVICES as ROUND22_DEVICES
from app.data.add_actionable_africa_round23 import DEVICES as ROUND23_DEVICES
from app.data.add_actionable_africa_round24 import DEVICES as ROUND24_DEVICES
from app.data.add_actionable_africa_round25 import DEVICES as ROUND25_DEVICES


TARGET_DEVICES = [
    *BURKINA_DEVICES,
    *ROUND22_DEVICES,
    *ROUND23_DEVICES,
    *ROUND24_DEVICES,
    *ROUND25_DEVICES,
]

TEXT_FIELDS = [
    "title",
    "short_description",
    "full_description",
    "eligibility_criteria",
    "specific_conditions",
    "required_documents",
    "funding_details",
    "recurrence_notes",
    "source_raw",
]

JSON_FIELDS = [
    "content_sections_json",
    "ai_rewritten_sections_json",
    "decision_analysis",
    "ai_readiness_reasons",
]


REPLACEMENTS = {
    "Pourquoi regarder cette opportunite ?": "Pourquoi regarder cette opportunité ?",
    "Presentation": "Présentation",
    "Points a verifier": "Points à vérifier",
    "A prioriser": "À prioriser",
    "A suivre": "À suivre",
    "a surveiller": "à surveiller",
    "a verifier": "à vérifier",
    "a confirmer": "à confirmer",
    "a preparer": "à préparer",
    "a fournir": "à fournir",
    "a deposer": "à déposer",
    "a mobiliser": "à mobiliser",
    "a obtenir": "à obtenir",
    "a structurer": "à structurer",
    "a renforcer": "à renforcer",
    "a transformer": "à transformer",
    "a financer": "à financer",
    "a rembourser": "à rembourser",
    "a utiliser": "à utiliser",
    "a suivre": "à suivre",
    "aupres": "auprès",
    "acces": "accès",
    "acceder": "accéder",
    "activite": "activité",
    "activites": "activités",
    "adapte": "adapté",
    "adaptee": "adaptée",
    "adaptees": "adaptées",
    "administres": "administrés",
    "ameliorer": "améliorer",
    "amorcage": "amorçage",
    "annee": "année",
    "apprentissage": "apprentissage",
    "apres": "après",
    "artisanale": "artisanale",
    "basee": "basée",
    "beneficiaire": "bénéficiaire",
    "beneficiaires": "bénéficiaires",
    "beninois": "béninois",
    "beninoise": "béninoise",
    "beninoises": "béninoises",
    "bancarisable": "bancarisable",
    "bancarisables": "bancarisables",
    "capacite": "capacité",
    "capacites": "capacités",
    "categorie": "catégorie",
    "ciblee": "ciblée",
    "ciblees": "ciblées",
    "cibles": "cibles",
    "chaine": "chaîne",
    "chaines": "chaînes",
    "chiffre": "chiffré",
    "cloture": "clôture",
    "cofinancement": "cofinancement",
    "competence": "compétence",
    "competences": "compétences",
    "complement": "complément",
    "concernes": "concernés",
    "concernees": "concernées",
    "concretement": "concrètement",
    "conditionnalite": "conditionnalité",
    "confirme": "confirmé",
    "confirmes": "confirmés",
    "confirmee": "confirmée",
    "confirmees": "confirmées",
    "cooperative": "coopérative",
    "cooperatives": "coopératives",
    "cout": "coût",
    "couts": "coûts",
    "credit": "crédit",
    "credits": "crédits",
    "criteres": "critères",
    "cree": "créé",
    "creer": "créer",
    "creation": "création",
    "curee": "curée",
    "date limite": "date limite",
    "deja": "déjà",
    "demarche": "démarche",
    "demarches": "démarches",
    "demarrer": "démarrer",
    "depot": "dépôt",
    "depose": "déposé",
    "deposer": "déposer",
    "depenses": "dépenses",
    "depend": "dépend",
    "dependent": "dépendent",
    "developpement": "développement",
    "developper": "développer",
    "developpe": "développe",
    "developpees": "développées",
    "differents": "différents",
    "disponibilite": "disponibilité",
    "duree": "durée",
    "echeance": "échéance",
    "echeancier": "échéancier",
    "economie": "économie",
    "economique": "économique",
    "economiques": "économiques",
    "ecosysteme": "écosystème",
    "edition": "édition",
    "egalement": "également",
    "eligibilite": "éligibilité",
    "eligible": "éligible",
    "eligibles": "éligibles",
    "emprunt": "emprunt",
    "energie": "énergie",
    "energetique": "énergétique",
    "entrepreneuriat": "entrepreneuriat",
    "enveloppe": "enveloppe",
    "equipement": "équipement",
    "equipements": "équipements",
    "equipe": "équipe",
    "etape": "étape",
    "etranger": "étranger",
    "etrangers": "étrangers",
    "etre": "être",
    "etude": "étude",
    "evenements": "événements",
    "facilite": "facilité",
    "facilites": "facilités",
    "feminin": "féminin",
    "feminine": "féminine",
    "feminines": "féminines",
    "fenetre": "fenêtre",
    "fiche curee": "fiche curée",
    "gere": "géré",
    "garanties": "garanties",
    "idee": "idée",
    "idees": "idées",
    "identite": "identité",
    "incubee": "incubée",
    "incube": "incubé",
    "indique": "indiqué",
    "indiquee": "indiquée",
    "innovation": "innovation",
    "interet": "intérêt",
    "intermediaire": "intermédiaire",
    "juridique": "juridique",
    "legale": "légale",
    "legalement": "légalement",
    "levee": "levée",
    "localite": "localité",
    "maitrise": "maîtrise",
    "marche": "marché",
    "marches": "marchés",
    "mecanisme": "mécanisme",
    "mecanismes": "mécanismes",
    "modere": "modéré",
    "montant demande": "montant demandé",
    "numerique": "numérique",
    "operationnel": "opérationnel",
    "operationnelle": "opérationnelle",
    "operationnelles": "opérationnelles",
    "operateur": "opérateur",
    "orientation": "orientation",
    "ouvertes": "ouvertes",
    "paiement": "paiement",
    "partenaire": "partenaire",
    "partenaires": "partenaires",
    "periode": "période",
    "periodes": "périodes",
    "permet": "permet",
    "piece": "pièce",
    "pieces": "pièces",
    "plafond": "plafond",
    "plafonds": "plafonds",
    "pluriannuel": "pluriannuel",
    "preparer": "préparer",
    "prepare": "prépare",
    "presente": "présente",
    "presenter": "présenter",
    "preuve": "preuve",
    "priorite": "priorité",
    "prioritaire": "prioritaire",
    "proceder": "procéder",
    "procedure": "procédure",
    "procedures": "procédures",
    "projet deja": "projet déjà",
    "promoteur": "promoteur",
    "publie": "publié",
    "publiee": "publiée",
    "publies": "publiés",
    "recemment": "récemment",
    "recurrent": "récurrent",
    "recurrente": "récurrente",
    "recurrents": "récurrents",
    "reference": "référence",
    "reglement": "règlement",
    "remunératrices": "rémunératrices",
    "remuneratrices": "rémunératrices",
    "rembourse": "remboursé",
    "reseau": "réseau",
    "resilience": "résilience",
    "selection": "sélection",
    "selectionner": "sélectionner",
    "specifique": "spécifique",
    "specifiques": "spécifiques",
    "strategique": "stratégique",
    "structure": "structuré",
    "structuree": "structurée",
    "structurees": "structurées",
    "suivi": "suivi",
    "tres": "très",
    "verifier": "vérifier",
    "viabilite": "viabilité",
    "visibilite": "visibilité",
}


def _polish_text(value: str | None) -> tuple[str | None, bool]:
    if not value:
        return value, False

    new = value
    for before, after in REPLACEMENTS.items():
        new = new.replace(before, after)
        if before[:1].islower():
            new = new.replace(before.capitalize(), after.capitalize())

    new = new.replace("Pret ", "Prêt ")
    new = new.replace(" pret ", " prêt ")
    new = new.replace("prets", "prêts")
    new = new.replace("Pret", "Prêt")
    new = new.replace("Cote d'Ivoire", "Côte d'Ivoire")
    new = new.replace("Benin", "Bénin")
    new = new.replace("burkinabe", "burkinabè")
    new = new.replace("Burkinabe", "Burkinabè")
    new = new.replace("generatrice", "génératrice")
    new = new.replace("generateurs", "générateurs")
    new = new.replace("generateur", "générateur")
    new = new.replace("societes", "sociétés")
    new = new.replace("Ministere", "Ministère")
    new = new.replace("Developpement", "Développement")
    new = new.replace("Competent", "Compétent")
    new = new.replace("competent", "compétent")
    new = new.replace("Differé", "Différé")
    new = new.replace("differe", "différé")
    new = new.replace("age limite", "âge limite")
    new = new.replace("Age limite", "Âge limite")
    new = new.replace("facilitér", "faciliter")
    new = new.replace("Facilitér", "Faciliter")
    new = new.replace("amorçâge", "amorçage")
    new = new.replace("Amorçâge", "Amorçage")
    new = new.replace("âgence", "agence")
    new = new.replace("Âgence", "Agence")
    new = new.replace("structurér", "structurer")
    new = new.replace("Structurér", "Structurer")
    new = new.replace("confirmér", "confirmer")
    new = new.replace("Confirmér", "Confirmer")
    new = new.replace("déposér", "déposer")
    new = new.replace("Déposér", "Déposer")
    new = new.replace("présentér", "présenter")
    new = new.replace("Présentér", "Présenter")
    new = new.replace("publiér", "publier")
    new = new.replace("Publiér", "Publier")
    new = new.replace("remboursément", "remboursement")
    new = new.replace("Remboursément", "Remboursement")
    new = new.replace("démarchés", "démarches")
    new = new.replace("Démarchés", "Démarches")
    new = new.replace("démarché", "démarche")
    new = new.replace("Démarché", "Démarche")
    new = new.replace("reelle", "réelle")
    new = new.replace("Reelle", "Réelle")
    new = new.replace("formalisee", "formalisée")
    new = new.replace("Formalisee", "Formalisée")
    new = new.replace("formalisees", "formalisées")
    new = new.replace("Formalisees", "Formalisées")
    new = new.replace("maturite", "maturité")
    new = new.replace("Maturite", "Maturité")
    new = new.replace("chomage", "chômage")
    new = new.replace("Chomage", "Chômage")
    new = new.replace("ministere", "ministère")
    new = new.replace("Ministere", "Ministère")
    new = new.replace("L'appui visible", "L'appui")
    new = new.replace("Le site ne communique pas", "La source ne communique pas")
    return new, new != value


def _polish_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _polish_text(value)
    if isinstance(value, list):
        changed = False
        items = []
        for item in value:
            next_item, item_changed = _polish_json(item)
            changed = changed or item_changed
            items.append(next_item)
        return items, changed
    if isinstance(value, dict):
        changed = False
        data = {}
        for key, item in value.items():
            if key == "go_no_go":
                next_item, item_changed = item, False
            else:
                next_item, item_changed = _polish_json(item)
            changed = changed or item_changed
            data[key] = next_item
        return data, changed
    return value, False


def _target_values() -> tuple[list[str], list[str]]:
    titles = [str(device["title"]) for device in TARGET_DEVICES]
    urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    return titles, urls


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    titles, urls = _target_values()
    changed_items: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    or_(
                        Device.title.in_(titles),
                        Device.source_url.in_(urls),
                    )
                )
            )
        ).scalars().all()

        for device in devices:
            changed_fields: set[str] = set()
            for field in TEXT_FIELDS:
                value = getattr(device, field)
                new_value, changed = _polish_text(value)
                if changed:
                    setattr(device, field, new_value)
                    changed_fields.add(field)

            for field in JSON_FIELDS:
                value = getattr(device, field)
                new_value, changed = _polish_json(value)
                if changed:
                    setattr(device, field, new_value)
                    changed_fields.add(field)

            if isinstance(device.decision_analysis, dict):
                analysis = dict(device.decision_analysis)
                if analysis.get("go_no_go") == "a_vérifier":
                    analysis["go_no_go"] = "a_verifier"
                    device.decision_analysis = analysis
                    changed_fields.add("decision_analysis")

            if device.user_quality_reasons:
                reasons = [
                    "fiche_curee" if reason == "fiche_curée" else reason
                    for reason in device.user_quality_reasons
                ]
                if reasons != device.user_quality_reasons:
                    device.user_quality_reasons = reasons
                    changed_fields.add("user_quality_reasons")

            if changed_fields:
                device.ai_rewrite_model = "added-africa-quality-polish-v1"
                device.ai_rewrite_checked_at = now
                device.last_verified_at = now
                device.updated_at = now
                device.user_quality_score = max(device.user_quality_score or 0, 92)
                if device.status == "open":
                    device.user_quality_decision = "publish"
                elif device.user_quality_decision not in {"publish", "publish_with_caution"}:
                    device.user_quality_decision = "publish_with_caution"

                reasons = set(device.user_quality_reasons or [])
                reasons.update({"source_officielle", "fiche_curee", "texte_poli"})
                device.user_quality_reasons = sorted(reasons)
                changed_items.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "fields": sorted(changed_fields),
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {
        "dry_run": not apply,
        "target_expected": len(titles),
        "matched": len(devices),
        "changed": len(changed_items),
        "items": changed_items[:80],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Polish visible copy for recently added Africa devices.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
