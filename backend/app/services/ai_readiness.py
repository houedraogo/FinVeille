from dataclasses import dataclass
from datetime import date
import re
from typing import Any
from urllib.parse import urlparse

from unidecode import unidecode

from app.utils.text_utils import clean_editorial_text, looks_english_text


AI_READY = "pret_pour_recommandation_ia"
AI_CAUTION = "utilisable_avec_prudence"
AI_REVIEW = "a_verifier"
AI_UNUSABLE = "non_exploitable"


@dataclass(frozen=True)
class AIReadiness:
    score: int
    label: str
    reasons: list[str]


def _source_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _section_texts(sections: Any) -> dict[str, str]:
    if not isinstance(sections, list):
        return {}
    result: dict[str, str] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = str(section.get("key") or "").strip()
        content = clean_editorial_text(section.get("content") or "")
        if key and content:
            result[key] = content
    return result


def _deadline_tags(tags: list[str]) -> set[str]:
    return {tag for tag in tags if tag.startswith("deadline:")}


def _taxonomy_tags(tags: list[str]) -> set[str]:
    return {tag for tag in tags if tag.startswith("taxonomy:")}


def _has_public_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    blocked_hosts = ("localhost", "127.0.0.1", "0.0.0.0")
    blocked_markers = ("token=", "access_token=", "google.com/search", "file://")
    return not any(marker in host or marker in str(url).lower() for marker in (*blocked_hosts, *blocked_markers))


def _source_reliability(source: Any) -> int:
    try:
        return int(_source_value(source, "reliability", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _is_source_active(source: Any) -> bool | None:
    value = _source_value(source, "is_active", None)
    if value is None:
        return None
    return bool(value)


def _has_unusable_marker(text: str) -> bool:
    normalized = unidecode(clean_editorial_text(text).lower())
    markers = (
        "aucun contenu exploitable trouve",
        "aucun contenu editorial exploitable",
        "javascript dynamique",
        "structure html trop pauvre",
        "token invalide ou expire",
        "impossible d'acceder a l'url",
        "url non publique",
        "page non publique",
        "activation deconseillee",
    )
    return any(marker in normalized for marker in markers)


def _is_placeholder_funding(text: str) -> bool:
    normalized = unidecode(clean_editorial_text(text).lower())
    markers = (
        "montant ou les avantages ne sont pas precises",
        "montant exact doit etre confirme",
        "montant ou avantage financier a confirmer",
        "modalites doivent etre confirme",
        "doivent etre confirmes sur la source officielle",
        "a confirmer sur la source officielle",
        "ne sont pas precises clairement",
    )
    return any(marker in normalized for marker in markers)


def _has_amount_marker(text: str) -> bool:
    normalized = unidecode(clean_editorial_text(text).lower())
    return bool(re.search(r"\b\d[\d\s.,]*(eur|euro|€|usd|\$|fcfa|xaf|xof|%)\b", normalized))


def _has_confirmed_benefit_signal(text: str) -> bool:
    normalized = unidecode(clean_editorial_text(text).lower())
    if not normalized or _is_placeholder_funding(normalized):
        return False
    if _has_amount_marker(normalized):
        return True
    benefit_markers = (
        "subvention",
        "dotation",
        "prix",
        "prime",
        "pret",
        "garantie",
        "accompagnement",
        "mentorat",
        "coaching",
        "programme d'accompagnement",
        "visibilite",
    )
    return any(marker in normalized for marker in benefit_markers)


def compute_ai_readiness(device: dict[str, Any], source: Any = None) -> AIReadiness:
    """Calcule si une fiche est exploitable par un futur moteur de recommandation IA."""

    reasons: list[str] = []
    score = 0

    tags = list(device.get("tags") or [])
    status = str(device.get("status") or "").lower()
    validation_status = str(device.get("validation_status") or "").lower()
    device_type = str(device.get("device_type") or "").lower()
    short_description = clean_editorial_text(device.get("short_description") or "")
    full_description = clean_editorial_text(device.get("full_description") or "")
    eligibility = clean_editorial_text(device.get("eligibility_criteria") or "")
    funding = clean_editorial_text(device.get("funding_details") or "")
    source_raw = clean_editorial_text(device.get("source_raw") or "")
    combined_text = " ".join(
        value for value in (short_description, full_description, eligibility, funding, source_raw[:1200]) if value
    )

    if validation_status == "rejected" or _has_unusable_marker(combined_text):
        return AIReadiness(0, AI_UNUSABLE, ["fiche_rejetee_ou_source_inexploitable"])

    sections = _section_texts(device.get("content_sections_json"))
    expected_sections = {"presentation", "eligibility", "funding", "calendar", "procedure", "official_source", "checks"}
    meaningful_sections = {
        key for key, value in sections.items() if len(value) >= 35 and "non communique" not in unidecode(value.lower())
    }
    if expected_sections <= set(sections):
        score += 12
        reasons.append("sections_structurees")
    if len(meaningful_sections & {"presentation", "eligibility", "funding", "calendar"}) >= 3:
        score += 10
        reasons.append("sections_metier_utiles")
    else:
        reasons.append("sections_metier_incompletes")

    if len(short_description) >= 90:
        score += 10
        reasons.append("resume_exploitable")
    else:
        reasons.append("resume_trop_court")

    if len(full_description) >= 350:
        score += 12
        reasons.append("description_detaillee")
    elif len(full_description) >= 180:
        score += 6
        reasons.append("description_partielle")
    else:
        reasons.append("description_insuffisante")

    if len(eligibility) >= 70 or len(sections.get("eligibility", "")) >= 70:
        score += 12
        reasons.append("criteres_presents")
    else:
        reasons.append("criteres_absents_ou_generiques")

    has_amount = bool(device.get("amount_min") or device.get("amount_max"))
    funding_text = " ".join(value for value in (funding, sections.get("funding", "")) if value)
    has_confirmed_benefit = _has_confirmed_benefit_signal(funding_text)
    funding_placeholder = _is_placeholder_funding(funding_text)
    if has_amount:
        score += 8
        reasons.append("montant_ou_avantage_present")
    elif has_confirmed_benefit:
        score += 5
        reasons.append("avantage_present_montant_a_confirmer")
    elif funding_placeholder:
        reasons.append("montant_a_confirmer")
    else:
        reasons.append("montant_absent")

    deadline_tags = _deadline_tags(tags)
    close_date = device.get("close_date")
    if close_date and status in {"open", "standby", "recurring"}:
        try:
            parsed_close_date = close_date if isinstance(close_date, date) else date.fromisoformat(str(close_date)[:10])
            if parsed_close_date >= date.today():
                score += 14
                reasons.append("date_limite_fiable")
            else:
                score += 4
                reasons.append("date_limite_passee")
        except (TypeError, ValueError):
            reasons.append("date_limite_invalide")
    elif "deadline:known" in deadline_tags or "deadline:permanent" in deadline_tags:
        score += 14
        reasons.append("calendrier_fiable")
    elif "deadline:institutional_project" in deadline_tags:
        score += 8
        reasons.append("projet_institutionnel")
    elif "deadline:not_communicated" in deadline_tags:
        score += 5
        reasons.append("cloture_non_communiquee")
    else:
        reasons.append("calendrier_a_verifier")

    taxonomy_tags = _taxonomy_tags(tags)
    if taxonomy_tags and "taxonomy:a_qualifier" not in taxonomy_tags and device_type != "autre":
        score += 8
        reasons.append("type_metier_classe")
    else:
        reasons.append("type_metier_a_qualifier")

    reliability = _source_reliability(source)
    if reliability >= 4:
        score += 9
        reasons.append("source_fiable")
    elif reliability == 3:
        score += 5
        reasons.append("source_moyennement_fiable")
    elif source is not None:
        score += 2
        reasons.append("source_faible")
    else:
        reasons.append("source_non_rattachee")

    if _is_source_active(source) is False:
        score -= 10
        reasons.append("source_inactive")

    if _has_public_url(device.get("source_url")):
        score += 5
        reasons.append("url_publique")
    else:
        score -= 12
        reasons.append("url_non_fiable")

    if looks_english_text(" ".join(value for value in (short_description, full_description, eligibility, funding) if value)):
        score -= 18
        reasons.append("texte_anglais_restant")

    if validation_status == "pending_review":
        score -= 8
        reasons.append("validation_humaine_requise")

    if status in {"expired", "closed"}:
        score -= 12
        reasons.append("fiche_expiree")
    elif status in {"open", "recurring"}:
        score += 4
        reasons.append("statut_exploitable")

    if "source_non_rattachee" in reasons or "url_non_fiable" in reasons:
        score = min(score, 70)
    if "texte_anglais_restant" in reasons:
        score = min(score, 69)
    if "cloture_non_communiquee" in reasons or "calendrier_a_verifier" in reasons:
        score = min(score, 79)
    if "montant_a_confirmer" in reasons or "avantage_present_montant_a_confirmer" in reasons:
        score = min(score, 79)
    if "montant_absent" in reasons and "projet_institutionnel" not in reasons:
        score = min(score, 79)
    if "criteres_absents_ou_generiques" in reasons and "calendrier_a_verifier" in reasons:
        score = min(score, 54)

    score = max(0, min(100, int(score)))

    if score >= 80 and validation_status in {"auto_published", "approved", "validated", ""}:
        label = AI_READY
    elif score >= 60:
        label = AI_CAUTION
    elif score >= 35:
        label = AI_REVIEW
    else:
        label = AI_UNUSABLE

    return AIReadiness(score, label, reasons[:12])
