from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from unidecode import unidecode

from app.utils.text_utils import has_recurrence_evidence, sanitize_text


@dataclass(frozen=True)
class TaxonomyClassification:
    device_type: str
    taxonomy_tag: str
    reason: str
    confidence: int


_RULES: tuple[tuple[str, tuple[str, ...], int], ...] = (
    (
        "investissement",
        (
            "fonds d'investissement",
            "capital investissement",
            "capital-risque",
            "capital risque",
            "venture capital",
            "private equity",
            "prise de participation",
            "equity",
            "amorçage",
            "amorcage",
            "seed",
            "series a",
            "series b",
            "business angel",
            "investisseur",
            "entrer au capital",
            "fonds propres",
        ),
        38,
    ),
    (
        "pret",
        (
            "pret",
            "prêt",
            "credit-bail",
            "crédit-bail",
            "credit bail",
            "crédit bail",
            "credit d'investissement",
            "crédit d'investissement",
            "emprunt",
            "avance remboursable",
            "financement bancaire",
        ),
        34,
    ),
    (
        "garantie",
        (
            "garantie",
            "contre-garantie",
            "cautionnement",
            "pré-garantie",
            "pre-garantie",
            "fonds de garantie",
        ),
        34,
    ),
    (
        "concours",
        (
            "concours",
            "prix ",
            "trophee",
            "trophée",
            "award",
            "competition",
            "compétition",
            "laureat",
            "lauréat",
            "candidats finalistes",
        ),
        32,
    ),
    (
        "aap",
        (
            "appel a projets",
            "appel à projets",
            "appel a projet",
            "appel à projet",
            "appel a candidatures",
            "appel à candidatures",
            "call for proposals",
            "call for applications",
            "ami ",
            "appel a manifestation d'interet",
            "appel à manifestation d'intérêt",
        ),
        30,
    ),
    (
        "accompagnement",
        (
            "accompagnement",
            "diag ",
            "diagnostic",
            "conseil",
            "coaching",
            "mentorat",
            "incubation",
            "acceleration",
            "accélération",
            "formation",
            "expert",
            "audit",
            "programme d'accompagnement",
        ),
        28,
    ),
    (
        "credit_impot",
        (
            "credit d'impot",
            "crédit d'impôt",
            "reduction d'impot",
            "réduction d'impôt",
            "deduction fiscale",
            "déduction fiscale",
            "abattement",
            "exoneration fiscale",
            "exonération fiscale",
            "cotisation fonciere",
            "cotisation foncière",
            "benefice imposable",
            "bénéfice imposable",
        ),
        28,
    ),
    (
        "exoneration",
        (
            "exoneration",
            "exonération",
            "allegement de charges",
            "allègement de charges",
            "charges sociales",
            "cotisations patronales",
            "franchise de cotisations",
        ),
        28,
    ),
    (
        "subvention",
        (
            "subvention",
            "aide financière",
            "aide financiere",
            "dotation",
            "grant",
            "prime",
            "financement non remboursable",
            "aide directe",
            "allocation",
        ),
        26,
    ),
)


def _blob(device: dict[str, Any]) -> str:
    return sanitize_text(
        " ".join(
            str(device.get(field) or "")
            for field in (
                "title",
                "organism",
                "device_type",
                "aid_nature",
                "short_description",
                "full_description",
                "eligibility_criteria",
                "funding_details",
                "source_raw",
                "recurrence_notes",
            )
        )
    )


def _source_blob(source: dict[str, Any] | None) -> str:
    if not source:
        return ""
    return sanitize_text(" ".join(str(source.get(field) or "") for field in ("name", "organism", "url", "source_type")))


def _score_keywords(text: str, keywords: tuple[str, ...], base_score: int) -> int:
    normalized = unidecode(text.lower())
    score = 0
    for keyword in keywords:
        marker = unidecode(keyword.lower())
        if marker in normalized:
            score += base_score
    return min(score, 100)


def classify_taxonomy(device: dict[str, Any], source: dict[str, Any] | None = None) -> TaxonomyClassification:
    text = _blob(device)
    normalized = unidecode(text.lower())
    source_text = unidecode(_source_blob(source).lower())
    current_type = str(device.get("device_type") or "autre")
    status = str(device.get("status") or "").lower()
    is_recurring = bool(device.get("is_recurring"))

    if "world bank" in source_text or "banque mondiale" in source_text or current_type == "institutional_project":
        return TaxonomyClassification(
            device_type="institutional_project",
            taxonomy_tag="taxonomy:projet_institutionnel",
            reason="Source ou type identifie comme projet institutionnel.",
            confidence=95,
        )

    if "fonds_prive" in source_text or any(
        marker in source_text
        for marker in ("africinvest", "partech", "france angels", "business angels", "investisseurs & partenaires")
    ):
        return TaxonomyClassification(
            device_type="investissement",
            taxonomy_tag="taxonomy:investissement",
            reason="Source rattachee a un acteur d'investissement prive.",
            confidence=90,
        )

    scored = []
    for device_type, keywords, base_score in _RULES:
        score = _score_keywords(text, keywords, base_score)
        if score:
            scored.append((score, device_type))

    if scored:
        score, device_type = sorted(scored, reverse=True)[0]
        if device_type == "credit_impot" and "exoneration" in normalized:
            device_type = "exoneration"
        if device_type == "pret" and re.search(r"\bavance remboursable\b", normalized):
            device_type = "avance_remboursable"
        return TaxonomyClassification(
            device_type=device_type,
            taxonomy_tag=f"taxonomy:{device_type}",
            reason="Categorie deduite des mots-cles metier du titre et de la description.",
            confidence=max(55, min(score, 92)),
        )

    if (is_recurring or status == "recurring" or has_recurrence_evidence(text)) and current_type not in {"autre", ""}:
        return TaxonomyClassification(
            device_type=current_type,
            taxonomy_tag="taxonomy:dispositif_permanent",
            reason="Dispositif recurrent ou permanent, nature conservee faute de signal plus precis.",
            confidence=65,
        )

    return TaxonomyClassification(
        device_type=current_type if current_type else "autre",
        taxonomy_tag="taxonomy:a_qualifier",
        reason="Aucun signal taxonomique suffisamment fiable.",
        confidence=30,
    )
