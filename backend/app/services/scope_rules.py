"""Règles de périmètre : Kafundo ne garde que de vraies opportunités de financement.

Décision produit (octobre 2026) : sont exclus les fiches décrivant simplement
un projet institutionnel déjà financé (Banque Mondiale, jeu de données de
projets de l'AFD), les marchés publics / appels d'offres de prestation et les
prestations de conseil ou d'ingénierie sans aide financière identifiable.
Sont conservés les vrais appels à projets, subventions et guichets, y compris
ceux de la Banque Mondiale ou de l'AFD (pages d'appels, pas de fiches projet).

Précision avant tout : le classifieur de contenu (ContentClassifier) se
trompe souvent sur les portails d'aides françaises (aides locales prises pour
des « marchés publics » ou des « événements »). Il n'est donc JAMAIS utilisé
ici pour exclure automatiquement une fiche d'un portail d'aides : seules des
règles structurelles (URL de fiche projet, jeu de données de projets,
sources de projets) bloquent l'import. Le reste est signalé « à revoir ».
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional
from urllib.parse import urlsplit


class ScopeVerdict(str, Enum):
    IN_SCOPE = "in_scope"
    EXCLUDED = "excluded"      # structurellement hors périmètre : quarantaine
    REVIEW = "review"          # doute : jamais exclu automatiquement


@dataclass(frozen=True)
class ScopeDecision:
    verdict: ScopeVerdict
    rule: Optional[str] = None
    reason: Optional[str] = None

    @property
    def excluded(self) -> bool:
        return self.verdict is ScopeVerdict.EXCLUDED


IN_SCOPE = ScopeDecision(ScopeVerdict.IN_SCOPE)

# (identifiant de règle, motif sur « hôte + chemin » canonique, explication)
_URL_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "worldbank_project_record",
        re.compile(r"(^|\.)worldbank\.org/.*(?:project-detail|projects-operations)"),
        "Fiche projet de la Banque Mondiale : projet déjà financé, pas un appel ouvert",
    ),
    (
        "afd_opendata_project_dataset",
        re.compile(r"(^|\.)opendata\.afd\.fr/.*les-projets-de-l-afd"),
        "Jeu de données des projets financés par l'AFD : pas un appel ouvert",
    ),
)

# Sources dont le contenu est exclusivement composé de fiches projet.
_SOURCE_NAME_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "worldbank_projects_source",
        re.compile(r"^banque mondiale\s*-\s*projets\b", re.IGNORECASE),
        "Source « Banque Mondiale - projets » : uniquement des fiches projet",
    ),
)

_REVIEW_TITLE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("technical_assistance_title", re.compile(
        r"^(?:être accompagné|bénéficier d.(?:une?|des) (?:assistance|expertise|étude|conseil|accompagnement|diagnostic|formation)|"
        r"obtenir un conseil|conseiller |fédérer|assister |préparer le lancement|lancer un schéma|diagnostiquer)",
        re.IGNORECASE,
    )),
    ("procurement_title", re.compile(
        r"appel d.offres|march[ée]s? public|avis d.attribution|dossier de consultation|request for (?:proposal|quotation)|invitation to bid",
        re.IGNORECASE,
    )),
)


def _host_and_path(url: Optional[str]) -> str:
    if not url:
        return ""
    raw = str(url).strip()
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{parts.path or ''}".lower()


def evaluate_scope(device: Mapping[str, object], source_name: Optional[str] = None) -> ScopeDecision:
    """Décide si une fiche (à créer ou existante) est dans le périmètre Kafundo.

    EXCLUDED  -> ne pas créer / archiver (règle structurelle, haute précision)
    REVIEW    -> garder mais signaler pour revue humaine, sans traitement IA coûteux
    IN_SCOPE  -> aucune objection
    """
    location = _host_and_path(device.get("source_url"))  # type: ignore[arg-type]
    for rule_id, pattern, reason in _URL_RULES:
        if location and pattern.search(location):
            return ScopeDecision(ScopeVerdict.EXCLUDED, rule_id, reason)

    name = str(source_name or "")
    for rule_id, pattern, reason in _SOURCE_NAME_RULES:
        if name and pattern.search(name):
            # Une page d'appel à projets reste conservée même dans une source de projets.
            if re.search(r"appels?-a-projets|call-for-proposals|appel-a-candidatures", location):
                continue
            return ScopeDecision(ScopeVerdict.EXCLUDED, rule_id, reason)

    title = str(device.get("title") or "")
    for rule_id, pattern in _REVIEW_TITLE_RULES:
        if pattern.search(title):
            return ScopeDecision(ScopeVerdict.REVIEW, rule_id, "Intitulé évoquant une prestation / un marché : à revoir")

    return IN_SCOPE
