import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device


HTML_NOISE_RE = re.compile(r"<[^>]+>|&[a-zA-Z]+;|<!\[CDATA\[|\]\]>", re.IGNORECASE)
MOJIBAKE_RE = re.compile(r"�|[A-Za-zÀ-ÿ]\?[A-Za-zÀ-ÿ]|Ã©|Ã¨|Ãª|Ã |Ã¢|Ã´|Ã®|Ã§|â€™|â€“")
ENGLISH_HINT_RE = re.compile(
    r"\b(the|and|for|with|apply|applications?|funding|grant|deadline|eligibility|"
    r"entrepreneurs?|startup|program|programme|support|investment)\b",
    re.IGNORECASE,
)
FRENCH_HINT_RE = re.compile(
    r"\b(le|la|les|des|pour|avec|aide|financement|candidature|eligibilite|"
    r"éligibilité|montant|calendrier|demarche|démarche)\b",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value)


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _norm(value: Any) -> str:
    text = _compact(value).lower()
    text = re.sub(r"[^a-z0-9àâäçéèêëîïôöùûüÿñæœ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _section_count(device: Device) -> int:
    sections = device.ai_rewritten_sections_json or device.content_sections_json or {}
    if isinstance(sections, dict):
        return sum(1 for value in sections.values() if len(_compact(value)) >= 80)
    if isinstance(sections, list):
        return sum(1 for value in sections if len(_compact(value)) >= 80)
    return 0


def _has_amount(device: Device) -> bool:
    details = _compact(device.funding_details).lower()
    return bool(
        device.amount_min
        or device.amount_max
        or re.search(r"\b(€|eur|euro|usd|dollar|subvention|dotation|pret|prêt|investissement)\b", details)
        or "a confirmer" in details
        or "à confirmer" in details
    )


def _looks_english(device: Device) -> bool:
    blob = " ".join(
        [
            _compact(device.short_description),
            _compact(device.full_description)[:2000],
            _compact(device.eligibility_criteria)[:1000],
            _compact(device.funding_details)[:1000],
        ]
    )
    english_hits = len(ENGLISH_HINT_RE.findall(blob))
    french_hits = len(FRENCH_HINT_RE.findall(blob))
    return device.language == "en" or (english_hits >= 12 and english_hits > french_hits * 2)


def _duplicate_fields(device: Device) -> bool:
    # A summary naturally overlaps with the full description. We only flag
    # business blocks that should carry distinct information.
    named_values = [
        ("eligibility", _norm(device.eligibility_criteria)),
        ("funding", _norm(device.funding_details)),
        ("expenses", _norm(device.eligible_expenses)),
        ("conditions", _norm(device.specific_conditions)),
        ("documents", _norm(device.required_documents)),
    ]
    named_values = [(name, value) for name, value in named_values if len(value) >= 160]
    for idx, (_, value) in enumerate(named_values):
        value_tokens = set(value.split())
        if len(value_tokens) < 20:
            continue
        for _, other in named_values[idx + 1 :]:
            other_tokens = set(other.split())
            if len(other_tokens) < 20:
                continue
            overlap = len(value_tokens & other_tokens) / max(1, min(len(value_tokens), len(other_tokens)))
            length_ratio = min(len(value), len(other)) / max(len(value), len(other))
            if overlap >= 0.88 and length_ratio >= 0.65:
                return True
    return False


def _standby_is_explained(device: Device) -> bool:
    note = _norm(device.recurrence_notes)
    return bool(
        "date limite non communiquee" in note
        or "cloture non communiquee" in note
        or "sans date limite explicite" in note
    )


def _issues_for(device: Device) -> list[str]:
    issues: list[str] = []
    short_len = len(_compact(device.short_description))
    full_len = len(_compact(device.full_description))
    eligibility_len = len(_compact(device.eligibility_criteria))
    funding_len = len(_compact(device.funding_details))
    sections = _section_count(device)
    all_text = " ".join(
        [
            _compact(device.short_description),
            _compact(device.full_description),
            _compact(device.eligibility_criteria),
            _compact(device.funding_details),
        ]
    )

    if short_len < 120:
        issues.append("resume_trop_faible")
    if full_len < 350 and sections < 2:
        issues.append("contenu_insuffisant")
    if full_len > 6000:
        issues.append("texte_trop_long")
    if eligibility_len < 120:
        issues.append("criteres_manquants")
    if not _has_amount(device) and funding_len < 80:
        issues.append("montant_manquant")
    if device.close_date is None and not device.is_recurring and device.status not in {"recurring", "standby", "expired"}:
        issues.append("date_ambiguë")
    if device.status == "open" and device.close_date and device.close_date < date.today():
        issues.append("open_date_passee")
    if sections < 3:
        issues.append("sections_incompletes")
    if not device.ai_rewritten_sections_json:
        issues.append("reformulation_ia_absente")
    if HTML_NOISE_RE.search(all_text):
        issues.append("bruit_html")
    if MOJIBAKE_RE.search(all_text):
        issues.append("encodage_suspect")
    if _looks_english(device):
        issues.append("texte_anglais")
    if _duplicate_fields(device):
        issues.append("doublons_champs")
    if device.device_type in {"autre", "", None}:
        issues.append("type_trop_generique")
    if (
        device.status in {"standby", "unknown"}
        and device.validation_status == "auto_published"
        and device.device_type != "institutional_project"
        and not _standby_is_explained(device)
    ):
        issues.append("statut_peu_decisionnel")

    return issues


def _decision_level(issues: list[str]) -> str:
    blocking = {
        "contenu_insuffisant",
        "resume_trop_faible",
        "date_ambiguë",
        "open_date_passee",
        "texte_anglais",
        "encodage_suspect",
    }
    caution = {
        "criteres_manquants",
        "montant_manquant",
        "sections_incompletes",
        "doublons_champs",
        "type_trop_generique",
        "statut_peu_decisionnel",
    }
    if any(issue in blocking for issue in issues):
        return "a_corriger"
    if any(issue in caution for issue in issues):
        return "utilisable_avec_prudence"
    return "pret_decision"


async def run(sample_limit: int = 20) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
            )
        ).scalars().all()

    issue_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    source_stats: dict[str, Counter[str]] = defaultdict(Counter)
    samples: list[dict[str, Any]] = []

    for device in rows:
        issues = _issues_for(device)
        level = _decision_level(issues)
        source_name = device.source.name if device.source else "Sans source"

        issue_counts.update(issues)
        level_counts[level] += 1
        source_stats[source_name]["total"] += 1
        source_stats[source_name][level] += 1
        for issue in issues:
            source_stats[source_name][issue] += 1

        if level == "a_corriger" and len(samples) < sample_limit:
            samples.append(
                {
                    "title": device.title,
                    "source": source_name,
                    "status": device.status,
                    "type": device.device_type,
                    "close_date": str(device.close_date) if device.close_date else None,
                    "issues": issues[:8],
                    "url": device.source_url,
                }
            )

    top_sources = sorted(
        (
            {
                "source": source_name,
                "total": stats["total"],
                "a_corriger": stats["a_corriger"],
                "utilisable_avec_prudence": stats["utilisable_avec_prudence"],
                "pret_decision": stats["pret_decision"],
                "principaux_problemes": [
                    {"issue": issue, "count": count}
                    for issue, count in stats.most_common()
                    if issue not in {"total", "a_corriger", "utilisable_avec_prudence", "pret_decision"}
                ][:5],
            }
            for source_name, stats in source_stats.items()
        ),
        key=lambda item: (item["a_corriger"], item["utilisable_avec_prudence"], item["total"]),
        reverse=True,
    )[:20]

    return {
        "audit_date": str(date.today()),
        "total_analyse": len(rows),
        "niveaux_decision": dict(level_counts),
        "problemes": dict(issue_counts.most_common()),
        "sources_prioritaires": top_sources,
        "echantillons_a_corriger": samples,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
