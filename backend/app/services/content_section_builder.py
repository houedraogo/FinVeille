from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from unidecode import unidecode

from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    clean_editorial_text,
    sanitize_text,
)


SECTION_ORDER = (
    "presentation",
    "eligibility",
    "funding",
    "calendar",
    "procedure",
    "official_source",
    "checks",
)


SECTION_TITLES = {
    "presentation": "Presentation",
    "eligibility": "Criteres d'eligibilite",
    "funding": "Montant / avantages",
    "calendar": "Calendrier",
    "procedure": "Demarche",
    "official_source": "Source officielle",
    "checks": "Points a verifier",
}


def _section(key: str, content: str, *, confidence: int = 70, source: str = "derived") -> dict[str, Any]:
    cleaned = clean_editorial_text(content)
    cleaned = (
        cleaned.replace("Cloture:", "Cloture :")
        .replace("Ouverture:", "Ouverture :")
        .replace("Source de reference:", "Source de reference :")
        .replace("URL officielle:", "URL officielle :")
    )
    cleaned = re.sub(r"(\d),\s+(\d)", r"\1,\2", cleaned)
    cleaned = re.sub(r"https:\s*//", "https://", cleaned)
    cleaned = re.sub(r"\.\s+([a-z]{2,})(/|$)", r".\1\2", cleaned)
    return {
        "key": key,
        "title": SECTION_TITLES[key],
        "content": cleaned,
        "confidence": confidence,
        "source": source,
    }


def _same(left: str | None, right: str | None) -> bool:
    left_norm = unidecode(clean_editorial_text(left or "").lower())
    right_norm = unidecode(clean_editorial_text(right or "").lower())
    return bool(left_norm) and left_norm == right_norm


def _too_similar(left: str | None, right: str | None) -> bool:
    left_norm = unidecode(clean_editorial_text(left or "").lower())
    right_norm = unidecode(clean_editorial_text(right or "").lower())
    if not left_norm or not right_norm:
        return False
    shorter, longer = sorted((left_norm, right_norm), key=len)
    return len(shorter) >= 80 and shorter in longer


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = unidecode(clean_editorial_text(text).lower())
    return any(marker in normalized for marker in markers)


def _dedupe_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean_editorial_text(text))
    cleaned_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = clean_editorial_text(part)
        if not cleaned:
            continue
        key = unidecode(cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned_parts.append(cleaned)
    return " ".join(cleaned_parts).strip()


def _strip_between_markers(value: str, start_marker: str, end_markers: tuple[str, ...], *, max_span: int = 500) -> str:
    normalized = unidecode(value.lower())
    start = normalized.find(start_marker)
    if start < 0:
        return value
    candidates = [normalized.find(marker, start + len(start_marker)) for marker in end_markers]
    candidates = [candidate for candidate in candidates if candidate > start]
    if not candidates:
        return value
    end = min(candidates)
    if end - start > max_span:
        return value
    return clean_editorial_text(value[:start] + " " + value[end:])


def _clean_bpifrance_editorial_text(text: str, device: dict[str, Any], source: dict[str, Any] | None) -> str:
    source_name = unidecode(clean_editorial_text((source or {}).get("name") or "").lower())
    organism = unidecode(clean_editorial_text(device.get("organism") or "").lower())
    if "bpifrance" not in source_name and "bpifrance" not in organism:
        return text

    value = clean_editorial_text(text)
    value = re.sub(r"\)(?=[A-Z])", ") ", value)
    value = re.sub(r"(?<=[a-zàâçéèêëîïôûùüÿñæœ])(?=[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])", " ", value)
    value = re.sub(r"\bi-Ph\s+D\b", "i-PhD", value, flags=re.IGNORECASE)

    normalized = unidecode(value.lower())
    useful_markers = (
        "jeunes chercheurs:",
        "i-phd est",
        "le concours",
        "cet appel",
        "ce dispositif",
        "ce programme",
    )
    positions = [normalized.find(marker) for marker in useful_markers]
    positions = [position for position in positions if 0 <= position <= 800]
    if positions and "accueil" in normalized[: min(positions)]:
        value = value[min(positions):].strip()

    value = _strip_between_markers(
        value,
        " appels a projets ",
        (" i-phd est", " le concours", " cet appel", " ce dispositif", " ce programme"),
        max_span=650,
    )
    value = re.sub(
        r"\b(Deposez votre dossier|Documents a telecharger|Guide Demarche Numerique 2026|Reglement i-PhD 2026|FAQ concours i-PhD 2026)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    return _dedupe_sentences(value)


def _business_clean(text: str, device: dict[str, Any], source: dict[str, Any] | None) -> str:
    value = _clean_bpifrance_editorial_text(text, device, source)
    value = re.sub(r"\s{2,}", " ", value).strip()
    return value


def _is_bpifrance_iph_d(device: dict[str, Any], source: dict[str, Any] | None = None) -> bool:
    title = unidecode(clean_editorial_text(device.get("title") or "").lower())
    source_name = unidecode(clean_editorial_text((source or {}).get("name") or "").lower())
    organism = unidecode(clean_editorial_text(device.get("organism") or "").lower())
    return "i-phd" in title and ("bpifrance" in source_name or "bpifrance" in organism)


def _bpifrance_iph_d_presentation() -> str:
    return (
        "Le concours i-PhD s'adresse aux jeunes chercheurs qui souhaitent transformer leurs travaux "
        "de recherche en projet de startup deeptech. Il permet aux laureats de rejoindre une communaute "
        "de chercheurs-entrepreneurs et de beneficier d'un programme d'accompagnement pour structurer "
        "leur projet entrepreneurial."
    )


def _bpifrance_iph_d_eligibility() -> str:
    return (
        "Le concours est ouvert aux jeunes chercheurs : doctorants a partir de la deuxieme annee de these "
        "ou docteurs ayant soutenu depuis moins de cinq ans. Le projet doit viser la creation d'une startup "
        "deeptech et etre accompagne par un organisme de transfert de technologie ou un incubateur de la "
        "recherche publique."
    )


def _format_amount(value: Decimal | float | int | None, currency: str | None) -> str:
    if value is None:
        return ""
    amount = float(value)
    if amount.is_integer():
        label = f"{int(amount):,}".replace(",", " ")
    else:
        label = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{label} {(currency or 'EUR').strip()}".strip()


def _deadline_tags(tags: list[str]) -> set[str]:
    return {tag for tag in tags if tag.startswith("deadline:")}


def _quality_labels(tags: list[str]) -> list[str]:
    labels = {
        "quality:summary_too_short": "Resume trop court.",
        "quality:full_description_too_short": "Description detaillee insuffisante.",
        "quality:missing_eligibility_criteria": "Criteres d'eligibilite a confirmer.",
        "quality:missing_funding_signal": "Montant ou avantage financier a confirmer.",
        "quality:english_content_remaining": "Texte anglais restant a normaliser en francais.",
        "quality:unknown_deadline": "Date limite absente ou non confirmee.",
        "source:manual_import": "Fiche issue d'un import manuel ou historique.",
        "source:aggregator": "Source relais: confirmer sur le site officiel.",
    }
    return [label for tag, label in labels.items() if tag in tags]


def _calendar_content(device: dict[str, Any], tags: list[str]) -> str:
    lines: list[str] = []
    open_date = device.get("open_date")
    close_date = device.get("close_date")
    recurrence_notes = clean_editorial_text(device.get("recurrence_notes") or "")

    if isinstance(open_date, date):
        lines.append(f"Ouverture : {open_date.strftime('%d/%m/%Y')}.")
    elif open_date:
        lines.append(f"Ouverture : {str(open_date)[:10]}.")

    if isinstance(close_date, date):
        lines.append(f"Cloture : {close_date.strftime('%d/%m/%Y')}.")
    elif close_date:
        lines.append(f"Cloture : {str(close_date)[:10]}.")

    deadline_tags = _deadline_tags(tags)
    if "deadline:permanent" in deadline_tags:
        lines.append("Dispositif permanent ou recurrent, sans fenetre de cloture unique.")
    elif "deadline:institutional_project" in deadline_tags:
        lines.append("Projet institutionnel : aucune date de candidature classique n'est exploitable.")
    elif "deadline:not_communicated" in deadline_tags:
        lines.append("Date limite non communiquee clairement par la source.")
    elif "deadline:expired" in deadline_tags and not close_date:
        lines.append("Fiche cloturee ou expiree sans date exploitable conservee.")
    elif "deadline:needs_review" in deadline_tags:
        lines.append("Calendrier a verifier manuellement.")

    if recurrence_notes and not any(_same(recurrence_notes, line) for line in lines):
        lines.append(recurrence_notes)

    return "\n".join(f"- {line}" for line in lines) or "- Calendrier non communique clairement par la source."


def _funding_content(device: dict[str, Any]) -> str:
    existing = clean_editorial_text(device.get("funding_details") or "")
    if existing:
        return existing
    if _is_bpifrance_iph_d(device):
        return (
            "Le concours apporte principalement un programme d'accompagnement d'un an pour aider les laureats "
            "a murir leur projet entrepreneurial. Le montant ou la dotation financiere doivent etre confirmes "
            "sur la source officielle."
        )
    title = unidecode(clean_editorial_text(device.get("title") or "").lower())
    if "africa's business heroes" in title or "africas business heroes" in title or "abh" in title:
        return (
            "Chaque annee, dix finalistes peuvent remporter une part de 1,5 million de dollars "
            "de subventions. Le programme apporte aussi de la visibilite, du mentorat, de la "
            "formation et un acces a l'ecosysteme entrepreneurial."
        )

    amount_min = device.get("amount_min")
    amount_max = device.get("amount_max")
    currency = device.get("currency") or "EUR"
    if amount_min or amount_max:
        if amount_min and amount_max and amount_min != amount_max:
            return f"Montant indicatif compris entre {_format_amount(amount_min, currency)} et {_format_amount(amount_max, currency)}."
        return f"Montant indicatif : {_format_amount(amount_max or amount_min, currency)}."

    funding = build_contextual_funding(
        text=(device.get("source_raw") or "") or (device.get("short_description") or ""),
        device_type=device.get("device_type"),
        amount_min=amount_min,
        amount_max=amount_max,
        currency=currency,
    )
    if len(funding) > 350 and not _contains_any(funding, ("montant", "euro", "eur", "%", "dotation", "subvention", "prix")):
        if _contains_any(funding, ("accompagnement", "mentorat", "coaching", "programme d'accompagnement")):
            return "Le dispositif apporte principalement un accompagnement. Les avantages precis et les modalites doivent etre confirmes sur la source officielle."
        return "Le montant ou les avantages ne sont pas precises clairement par la source."
    return funding


def _eligibility_content(device: dict[str, Any]) -> str:
    if _is_bpifrance_iph_d(device):
        return _bpifrance_iph_d_eligibility()
    existing = clean_editorial_text(device.get("eligibility_criteria") or "")
    if existing:
        return existing
    if str(device.get("device_type") or "") == "institutional_project":
        return (
            "Les criteres d'eligibilite detailles ne sont pas exposes dans la source structuree. "
            "La page officielle doit etre consultee pour confirmer les beneficiaires et conditions d'acces."
        )
    return build_contextual_eligibility(
        text=(device.get("source_raw") or "") or (device.get("short_description") or ""),
        beneficiaries=device.get("beneficiaries"),
        country=device.get("country"),
        geographic_scope=device.get("geographic_scope"),
    )


def _procedure_content(device: dict[str, Any], source: dict[str, Any] | None) -> str:
    existing = clean_editorial_text(device.get("procedure") or device.get("application_process") or "")
    if existing:
        return existing
    organism = clean_editorial_text(device.get("organism") or "")
    source_name = clean_editorial_text((source or {}).get("name") or "")
    if "les-aides.fr" in source_name.lower():
        return "La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle Les-aides.fr."
    if organism:
        return f"La demarche doit etre confirmee aupres de {organism} via la source officielle."
    return "La consultation detaillee et la candidature se font depuis la source officielle."


def _official_source_content(device: dict[str, Any], source: dict[str, Any] | None) -> str:
    source_url = clean_editorial_text(device.get("source_url") or "")
    source_name = clean_editorial_text((source or {}).get("name") or device.get("organism") or "")
    reliability = (source or {}).get("reliability")
    parts = []
    if source_name:
        parts.append(f"Source de reference : {source_name}.")
    if source_url:
        parts.append("Lien officiel conserve dans le champ source_url de la fiche.")
    if reliability:
        parts.append(f"Fiabilite source : {reliability}/5.")
    return "\n".join(parts) or "Source officielle a confirmer."


def build_content_sections(device: dict[str, Any], source: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    tags = list(device.get("tags") or [])
    if _is_bpifrance_iph_d(device, source):
        presentation = _bpifrance_iph_d_presentation()
    else:
        presentation = _business_clean(device.get("short_description") or "", device, source)
    if not presentation:
        presentation = _business_clean(device.get("full_description") or "", device, source).split("\n\n", 1)[0]
    if not presentation:
        presentation = "La source ne fournit pas encore de presentation editoriale exploitable."

    eligibility = _business_clean(_eligibility_content(device), device, source)
    funding = _business_clean(_funding_content(device), device, source)
    if str(device.get("device_type") or "") == "institutional_project" and not clean_editorial_text(device.get("funding_details") or ""):
        funding = "Le financement correspond au projet institutionnel reference par la source. Les modalites operationnelles doivent etre confirmees sur la page officielle."
    procedure = _procedure_content(device, source)

    if _same(eligibility, presentation):
        eligibility = "Les criteres detailles doivent etre confirmes sur la source officielle."
    if _same(funding, presentation) or _same(funding, eligibility) or _too_similar(funding, presentation) or _too_similar(funding, eligibility):
        funding = "Le montant ou les avantages ne sont pas precises clairement par la source."
    if _same(procedure, presentation) or _same(procedure, eligibility) or _same(procedure, funding):
        procedure = "La consultation detaillee et la candidature se font depuis la source officielle."

    checks = _quality_labels(tags)
    if not checks:
        checks.append("Certaines conditions doivent etre confirmees sur le site officiel avant toute decision.")

    sections = [
        _section("presentation", presentation, confidence=80, source="short_description"),
        _section("eligibility", eligibility, confidence=70, source="eligibility_criteria"),
        _section("funding", funding, confidence=70, source="funding_details"),
        _section("calendar", _calendar_content(device, tags), confidence=85, source="deadline_classifier"),
        _section("procedure", procedure, confidence=60, source="derived"),
        _section("official_source", _official_source_content(device, source), confidence=90, source="source_url"),
        _section("checks", "\n".join(f"- {item}" for item in checks), confidence=65, source="quality_gate"),
    ]
    return [section for section in sections if section["content"]]


def render_sections_markdown(sections: list[dict[str, Any]]) -> str:
    ordered = sorted(sections, key=lambda item: SECTION_ORDER.index(item["key"]) if item.get("key") in SECTION_ORDER else 99)
    return "\n\n".join(f"## {item['title']}\n{item['content']}" for item in ordered if item.get("content")).strip()
