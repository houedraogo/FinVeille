from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx
from unidecode import unidecode

from app.config import settings
from app.services.content_section_builder import SECTION_ORDER, SECTION_TITLES
from app.utils.text_utils import clean_editorial_text, looks_english_text


REWRITE_PENDING = "pending"
REWRITE_DONE = "done"
REWRITE_FAILED = "failed"
REWRITE_NEEDS_REVIEW = "needs_review"

REWRITABLE_SECTION_KEYS = (
    "presentation",
    "eligibility",
    "funding",
    "calendar",
    "procedure",
    "checks",
)


@dataclass(frozen=True)
class AIRewriteResult:
    status: str
    sections: list[dict[str, Any]]
    model: str | None
    checked_at: datetime
    issues: list[str]


class AIRewriter:
    """Reformule les sections metier sans changer les faits source."""

    def __init__(self, *, provider: str | None = None, model: str | None = None) -> None:
        self.provider = (provider or settings.AI_REWRITE_PROVIDER or "openai").strip().lower()
        self.model = (model or settings.AI_REWRITE_MODEL or "gpt-4o-mini").strip()

    def can_rewrite(self) -> bool:
        if self.provider == "openai":
            return bool(settings.OPENAI_API_KEY)
        return False

    async def rewrite_device(self, device: dict[str, Any]) -> AIRewriteResult:
        checked_at = datetime.now(timezone.utc)
        source_sections = _source_sections(device)
        if not source_sections:
            return AIRewriteResult(REWRITE_FAILED, [], self.model, checked_at, ["sections_source_absentes"])

        if not self.can_rewrite():
            return AIRewriteResult(REWRITE_FAILED, [], self.model, checked_at, ["ia_non_configuree"])

        try:
            payload = await self._call_provider(device, source_sections)
        except Exception as exc:
            return AIRewriteResult(REWRITE_FAILED, [], self.model, checked_at, [f"appel_ia_echoue:{type(exc).__name__}"])

        sections = _normalize_rewritten_sections(payload)
        issues = validate_rewritten_sections(sections, source_sections, device)
        status = REWRITE_DONE if not issues else REWRITE_NEEDS_REVIEW
        return AIRewriteResult(status, sections, self.model, checked_at, issues)

    async def _call_provider(self, device: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        if self.provider != "openai":
            raise RuntimeError(f"Provider IA non supporte: {self.provider}")
        return await self._call_openai(device, sections)

    async def _call_openai(self, device: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = build_rewrite_prompt(device, sections)
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es un redacteur metier pour une plateforme de veille financement. "
                        "Tu reformules en francais clair sans inventer de faits."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=settings.AI_REWRITE_TIMEOUT_SECONDS) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


def build_rewrite_prompt(device: dict[str, Any], sections: list[dict[str, Any]]) -> str:
    compact_sections = [
        {
            "key": section.get("key"),
            "title": section.get("title"),
            "content": clean_editorial_text(section.get("content") or "")[:1800],
        }
        for section in sections
        if section.get("key") in REWRITABLE_SECTION_KEYS
    ]
    context = {
        "title": clean_editorial_text(device.get("title") or ""),
        "organism": clean_editorial_text(device.get("organism") or ""),
        "country": clean_editorial_text(device.get("country") or ""),
        "device_type": clean_editorial_text(device.get("device_type") or ""),
        "status": clean_editorial_text(device.get("status") or ""),
        "close_date": str(device.get("close_date") or ""),
        "amount_min": str(device.get("amount_min") or ""),
        "amount_max": str(device.get("amount_max") or ""),
        "currency": clean_editorial_text(device.get("currency") or ""),
        "sections": compact_sections,
    }
    return (
        "Reformule cette fiche en francais professionnel, clair et lisible.\n"
        "Contraintes strictes:\n"
        "- N'invente aucune information absente des champs fournis.\n"
        "- Conserve les dates, montants, pays, organisme et conditions tels qu'ils sont fournis.\n"
        "- Corrige accents, ponctuation, espaces, phrases collees et paragraphes.\n"
        "- Supprime les doublons, fil d'Ariane, menus, textes techniques et HTML.\n"
        "- N'ecris jamais de navigation du type 'Accueil', 'Documents a telecharger', 'FAQ', 'Deposez votre dossier'.\n"
        "- Ecris dans un style naturel, business et directement compréhensible par un lecteur francophone.\n"
        "- Pour les criteres, le calendrier et les points a verifier, utilise des listes courtes avec une ligne par point quand c'est pertinent.\n"
        "- Si une information manque, ecris 'Non communique par la source' ou 'A confirmer sur la source officielle'.\n"
        "- Retourne uniquement un objet JSON valide.\n\n"
        "Format JSON attendu:\n"
        "{\"sections\":[{\"key\":\"presentation\",\"title\":\"Présentation\",\"content\":\"...\"},"
        "{\"key\":\"eligibility\",\"title\":\"Critères d'éligibilité\",\"content\":\"...\"},"
        "{\"key\":\"funding\",\"title\":\"Montant / avantages\",\"content\":\"...\"},"
        "{\"key\":\"calendar\",\"title\":\"Calendrier\",\"content\":\"...\"},"
        "{\"key\":\"procedure\",\"title\":\"Démarche\",\"content\":\"...\"},"
        "{\"key\":\"checks\",\"title\":\"Points à vérifier\",\"content\":\"...\"}]}\n\n"
        "Attendus par section:\n"
        "- presentation : 1 a 2 paragraphes utiles, sans repetition.\n"
        "- eligibility : conditions ou publics cibles, de preference en liste si plusieurs points.\n"
        "- funding : montant, avantages ou accompagnement; sinon mention explicite que ce n'est pas communique.\n"
        "- calendar : reprendre la date limite si elle existe, avec une presentation claire.\n"
        "- procedure : expliquer brievement comment consulter ou candidater.\n"
        "- checks : seulement les incertitudes reelles a confirmer.\n\n"
        f"Donnees source:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )


def validate_rewritten_sections(
    sections: list[dict[str, Any]],
    source_sections: list[dict[str, Any]],
    device: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    keys = {section.get("key") for section in sections}
    missing = [key for key in REWRITABLE_SECTION_KEYS if key not in keys]
    if missing:
        issues.append("sections_manquantes:" + ",".join(missing))

    combined = " ".join(clean_editorial_text(section.get("content") or "") for section in sections)
    normalized = unidecode(combined.lower())
    if len(combined) < 250:
        issues.append("texte_reformule_trop_court")
    if looks_english_text(combined):
        issues.append("texte_anglais_restant")
    if any(marker in normalized for marker in ("<div", "<span", "javascript", "documents a telecharger")):
        issues.append("bruit_html_ou_navigation")

    close_date = str(device.get("close_date") or "")
    expected_dates = _expected_date_variants(close_date)
    normalized_dates = {unidecode(expected.lower()) for expected in expected_dates}
    if close_date and not any(expected in normalized for expected in normalized_dates):
        issues.append("date_limite_absente_de_la_reformulation")

    source_by_key = {section.get("key"): clean_editorial_text(section.get("content") or "") for section in source_sections}
    for section in sections:
        key = str(section.get("key") or "")
        content = clean_editorial_text(section.get("content") or "")
        if key in source_by_key and len(source_by_key[key]) >= 40 and len(content) < 25:
            issues.append(f"section_trop_pauvre:{key}")

    return issues[:8]


def _source_sections(device: dict[str, Any]) -> list[dict[str, Any]]:
    sections = device.get("content_sections_json")
    if not isinstance(sections, list):
        return []
    return [
        section
        for section in sections
        if isinstance(section, dict)
        and section.get("key") in SECTION_ORDER
        and clean_editorial_text(section.get("content") or "")
    ]


def _normalize_rewritten_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(raw_sections, list):
        return []

    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key not in REWRITABLE_SECTION_KEYS or key in seen:
            continue
        content = _normalize_rewrite_content(item.get("content") or "", key=key)
        if not content:
            continue
        seen.add(key)
        sections.append(
            {
                "key": key,
                "title": _normalize_rewrite_title(item.get("title") or SECTION_TITLES.get(key) or key, key=key),
                "content": content,
                "confidence": 80,
                "source": "ai_rewrite",
            }
        )

    return sorted(sections, key=lambda item: SECTION_ORDER.index(item["key"]) if item["key"] in SECTION_ORDER else 99)


def _normalize_rewrite_title(value: str, *, key: str) -> str:
    cleaned = clean_editorial_text(value or "")
    if cleaned:
        return cleaned
    fallback_titles = {
        "presentation": "Présentation",
        "eligibility": "Critères d'éligibilité",
        "funding": "Montant / avantages",
        "calendar": "Calendrier",
        "procedure": "Démarche",
        "checks": "Points à vérifier",
    }
    return fallback_titles.get(key, key)


def _normalize_rewrite_content(value: str, *, key: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return ""

    raw_lines = [line.strip() for line in text.split("\n")]
    cleaned_lines: list[str] = []
    last_blank = False

    for raw_line in raw_lines:
        if not raw_line:
            if cleaned_lines and not last_blank:
                cleaned_lines.append("")
            last_blank = True
            continue

        normalized_line = clean_editorial_text(raw_line)
        normalized_line = re.sub(
            r"^(Accueil|Documents a telecharger|Documentation|FAQ|Deposez votre dossier|Déposez votre dossier)\b[:\s-]*",
            "",
            normalized_line,
            flags=re.IGNORECASE,
        ).strip()
        if not normalized_line:
            continue

        if key in {"eligibility", "calendar", "checks"}:
            normalized_line = re.sub(r"^[-•]\s*", "- ", normalized_line)
            if not normalized_line.startswith("- "):
                normalized_line = f"- {normalized_line}"
        else:
            normalized_line = re.sub(r"^[-•]\s*", "", normalized_line)

        if cleaned_lines:
            previous = cleaned_lines[-1]
            if previous and unidecode(previous.lower()) == unidecode(normalized_line.lower()):
                continue

        cleaned_lines.append(normalized_line)
        last_blank = False

    normalized = "\n".join(cleaned_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?<!\n)- (?=[^\n]+:)", "- ", normalized)
    return normalized


def _expected_date_variants(close_date: str) -> set[str]:
    variants: set[str] = set()
    if not close_date or len(close_date) < 10:
        return variants

    variants.add(close_date[:10])
    try:
        parsed = date.fromisoformat(close_date[:10])
    except ValueError:
        return variants

    variants.add(parsed.strftime("%d/%m/%Y"))
    variants.add(parsed.strftime("%d-%m-%Y"))
    variants.add(parsed.strftime("%d.%m.%Y"))

    month_names = {
        1: "janvier",
        2: "fevrier",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "aout",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "decembre",
    }
    month_label = month_names.get(parsed.month)
    if month_label:
        variants.add(f"{parsed.day} {month_label} {parsed.year}")
        variants.add(f"{parsed.day:02d} {month_label} {parsed.year}")
    return variants
