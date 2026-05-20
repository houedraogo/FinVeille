from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from unidecode import unidecode

from app.utils.text_utils import clean_editorial_text, looks_english_text


USER_PUBLISH = "publish"
USER_CAUTION = "publish_with_caution"
USER_ADMIN_ONLY = "admin_only"
USER_REJECT = "reject"


@dataclass(frozen=True)
class UserQualityScore:
    score: int
    decision: str
    reasons: list[str]


def _text(value: Any) -> str:
    return clean_editorial_text(str(value or ""))


def _normalized(value: Any) -> str:
    return unidecode(_text(value).lower())


def _has_public_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    blocked = ("localhost", "127.0.0.1", "0.0.0.0", "file://", "google.com/search")
    return not any(marker in str(url).lower() for marker in blocked)


def _has_unusable_marker(blob: str) -> bool:
    markers = (
        "aucun contenu exploitable trouve",
        "aucun contenu editorial exploitable",
        "javascript dynamique",
        "structure html trop pauvre",
        "token invalide ou expire",
        "impossible d'acceder a l'url",
        "url non publique",
        "page non publique",
        "404",
        "401",
        "403",
        "activation deconseillee",
    )
    return any(marker in blob for marker in markers)


def _section_texts(sections: Any) -> dict[str, str]:
    if not isinstance(sections, list):
        return {}
    result: dict[str, str] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = str(section.get("key") or "").strip()
        content = _text(section.get("content"))
        if key and content:
            result[key] = content
    return result


def _date_is_clear(device: dict[str, Any], status: str) -> bool:
    if device.get("close_date"):
        return True
    if status in {"recurring", "standby", "closed", "expired"}:
        return True
    if device.get("is_recurring") or _text(device.get("recurrence_notes")):
        return True
    tags = [str(tag) for tag in (device.get("tags") or [])]
    return any(tag.startswith("deadline:") for tag in tags)


def compute_user_quality(device: dict[str, Any]) -> UserQualityScore:
    """Score interne orienté expérience utilisateur, distinct du score technique."""

    reasons: list[str] = []
    score = 0

    title = _text(device.get("title"))
    status = _normalized(device.get("status") or "open")
    device_type = _normalized(device.get("device_type"))
    short_description = _text(device.get("short_description") or device.get("auto_summary"))
    full_description = _text(device.get("full_description"))
    eligibility = _text(device.get("eligibility_criteria"))
    funding = _text(device.get("funding_details"))
    source_url = str(device.get("source_url") or "")
    source_raw = _text(device.get("source_raw"))[:1800]
    sections = _section_texts(device.get("ai_rewritten_sections_json") or device.get("content_sections_json"))
    combined = _normalized(" ".join([title, short_description, full_description, eligibility, funding, source_raw]))

    if _has_unusable_marker(combined):
        return UserQualityScore(0, USER_REJECT, ["source_inexploitable"])

    if _has_public_url(source_url):
        score += 20
        reasons.append("source_fiable")
    else:
        reasons.append("source_non_fiable")

    date_clear = _date_is_clear(device, status)
    if date_clear:
        score += 18
        reasons.append("date_ou_statut_clair")
    else:
        reasons.append("date_ou_statut_ambigu")

    readable_text = len(short_description) >= 80 and (len(full_description) >= 160 or len(sections) >= 3)
    still_english = looks_english_text(title) or any(
        looks_english_text(value)
        for value in (short_description, full_description)
        if value
    )
    has_html_noise = any(marker in combined for marker in ("<div", "<span", "</", "cookie", "javascript"))
    if readable_text and not still_english and not has_html_noise:
        score += 22
        reasons.append("contenu_lisible")
    else:
        if still_english:
            reasons.append("anglais_a_traduire")
        if has_html_noise:
            reasons.append("texte_bruite")
        if not readable_text:
            reasons.append("contenu_trop_pauvre")

    action_signal = bool(source_url) and (
        status in {"open", "recurring", "standby"}
        or any(word in combined for word in ("candidature", "postuler", "apply", "formulaire", "contact", "dossier"))
    )
    if action_signal and device_type not in {"institutional_project", "autre"}:
        score += 18
        reasons.append("action_possible")
    else:
        reasons.append("action_non_claire")

    beneficiaries = device.get("beneficiaries") or []
    target_clear = bool(beneficiaries) or len(eligibility) >= 80 or len(sections.get("eligibility", "")) >= 80
    if target_clear:
        score += 22
        reasons.append("profil_cible_clair")
    else:
        reasons.append("profil_cible_ambigu")

    if device_type in {"institutional_project", "autre"}:
        score = min(score, 55)
        reasons.append("type_non_actionnable")

    if status in {"expired", "closed"}:
        score = min(score, 45)
        reasons.append("opportunite_fermee")

    score = max(0, min(100, score))

    critical = set(reasons) & {"source_non_fiable", "contenu_trop_pauvre"}
    if score < 35 or {"source_non_fiable", "contenu_trop_pauvre"} <= set(reasons):
        decision = USER_REJECT
    elif score < 60 or "type_non_actionnable" in reasons or "anglais_a_traduire" in reasons:
        decision = USER_ADMIN_ONLY
    elif score < 80 or critical or "date_ou_statut_ambigu" in reasons or "action_non_claire" in reasons:
        decision = USER_CAUTION
    else:
        decision = USER_PUBLISH

    return UserQualityScore(score=score, decision=decision, reasons=reasons)
