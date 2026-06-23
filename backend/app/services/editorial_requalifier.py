"""Qualification prudente des flux editoriaux en fiches visibles premium."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.ai_readiness import compute_ai_readiness
from app.services.content_section_builder import build_content_sections, render_sections_markdown
from app.services.user_quality import compute_user_quality
from app.utils.text_utils import clean_editorial_text, normalize_title


PUBLIC_TYPES = {"subvention", "concours", "aap", "ami", "investissement", "accompagnement"}
EDITORIAL_SOURCE_KINDS = {"editorial_opportunities", "editorial_funding"}

NEGATIVE_MARKERS = (
    "bursary",
    "scholarship",
    "studentship",
    "internship",
    "graduate trainee",
    "fellowship",
    "journalism",
    "journalist",
    "media fellowship",
    "photography",
    "photo contest",
    "residency",
    "travel award",
    "conference",
    "essay",
    "award for writers",
    "doctoral",
    "postdoctoral",
    "learners",
    "consultancy",
    "up to $",
    "advanced grants",
    "unhcr innovation accelerator",
    "humanitarian solution",
)

ENGLISH_ACTION_MARKERS = (
    "applications are now open",
    "applications open",
    "opens applications",
    "opens funding",
    "apply by",
    "apply for funding",
    "apply now",
    "launches",
    "funding window",
    "call for applications",
)

POSITIVE_MARKERS = (
    "startup",
    "start-up",
    "entrepreneur",
    "sme",
    "pme",
    "msme",
    "enterprise",
    "business",
    "company",
    "venture",
    "agripreneur",
    "farmer",
    "agriculture",
    "innovation",
    "innovator",
    "accelerator",
    "grant",
    "fund",
    "funding",
    "open call",
    "call for proposals",
    "women entrepreneurs",
    "digital",
    "ai",
    "climate",
    "energy",
    "circular",
)

PATTERN_TITLES: tuple[tuple[str, str, str, list[str], list[str]], ...] = (
    (
        "sheconnects",
        "SheConnects Digital Accelerator 2026 - subventions pour solutions numériques à impact",
        "subvention",
        ["startup", "entrepreneur", "innovation", "numérique", "impact"],
        ["entreprises", "startups", "femmes entrepreneures"],
    ),
    (
        "inclusive ai innovations",
        "Inclusive AI Innovations in Africa 2026 - financement pour innovateurs IA africains",
        "subvention",
        ["intelligence artificielle", "innovation", "Afrique", "numérique"],
        ["startups", "PME", "innovateurs africains"],
    ),
    (
        "farmers for the future",
        "Farmers for the Future 2026 - subvention agripreneuriat Nigeria",
        "subvention",
        ["agriculture", "agripreneuriat", "Nigeria", "innovation"],
        ["entrepreneurs agricoles", "startups", "PME"],
    ),
    (
        "batn foundation",
        "Farmers for the Future 2026 - subvention agripreneuriat Nigeria",
        "subvention",
        ["agriculture", "agripreneuriat", "Nigeria", "innovation"],
        ["entrepreneurs agricoles", "startups", "PME"],
    ),
    (
        "fempreneur",
        "CIWiL Fempreneur Fund 2026 - subvention pour femmes entrepreneures",
        "subvention",
        ["entrepreneuriat féminin", "subvention", "croissance"],
        ["femmes entrepreneures", "PME"],
    ),
    (
        "power of diversity grants",
        "Power of Diversity Grants 2026 - appel à projets diversité et inclusion",
        "aap",
        ["diversité", "inclusion", "innovation", "subvention"],
        ["organisations", "entreprises", "porteurs de projet"],
    ),
    (
        "cosmic",
        "COSMIC Open Call 2 - financement IA et données pour transition verte",
        "aap",
        ["intelligence artificielle", "données", "transition verte", "innovation"],
        ["PME", "startups", "entreprises innovantes"],
    ),
    (
        "circuloos",
        "CIRCULOOS Open Call 3.2 - appel à projets chaînes de valeur circulaires",
        "aap",
        ["économie circulaire", "chaînes de valeur", "innovation"],
        ["PME", "startups", "entreprises industrielles"],
    ),
    (
        "odeon",
        "ODEON Open Call - financement services énergie data et cloud-edge AI",
        "aap",
        ["énergie", "données", "cloud-edge AI", "innovation"],
        ["PME", "startups", "entreprises technologiques"],
    ),
    (
        "gcsp prize",
        "GCSP Prize 2026 - concours innovation sécurité mondiale",
        "concours",
        ["innovation", "sécurité mondiale", "prix"],
        ["startups", "PME", "porteurs de projet"],
    ),
    (
        "developpp ventures",
        "develoPPP Ventures 2026 - financement startups africaines en croissance",
        "concours",
        ["startup", "Afrique", "croissance", "financement"],
        ["startups", "PME", "entrepreneurs"],
    ),
)

CURRENCY_ALIASES = {
    "$": "USD",
    "usd": "USD",
    "us$": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "chf": "CHF",
    "kes": "KES",
    "ksh": "KES",
    "ngn": "NGN",
    "naira": "NGN",
    "₦": "NGN",
    "xof": "XOF",
    "xaf": "XAF",
    "fcfa": "XOF",
}


@dataclass(frozen=True)
class Qualification:
    publishable: bool
    reason: str
    title: str | None = None
    device_type: str | None = None
    keywords: list[str] | None = None
    beneficiaries: list[str] | None = None
    amount_max: Decimal | None = None
    currency: str | None = None
    funding_details: str | None = None
    short_description: str | None = None
    eligibility_criteria: str | None = None


def _norm(value: Any) -> str:
    return unidecode(clean_editorial_text(str(value or "")).lower())


def _source_dict(source: Source) -> dict[str, Any]:
    return {
        "id": str(source.id),
        "name": source.name,
        "organism": source.organism,
        "country": source.country,
        "url": source.url,
        "collection_mode": source.collection_mode,
        "level": source.level,
        "reliability": source.reliability,
        "is_active": source.is_active,
        "config": source.config or {},
        "language": "fr",
    }


def _is_editorial_source(source: Source) -> bool:
    config = source.config if isinstance(source.config, dict) else {}
    return config.get("source_kind") in EDITORIAL_SOURCE_KINDS


def _clean_tags(tags: list[str] | None, *, publishable: bool, reason: str) -> list[str]:
    blocked = {
        "visibility:admin_only",
        "visibility:auto_published",
        "source:editorial_auto_admin_only",
        "quality:editorial_missing_reliable_deadline",
        "quality:editorial_english_title_admin_only",
        "quality:editorial_generic_type_admin_only",
        "quality:english_content_remaining",
        "quality:english_title_admin_only",
    }
    values = [tag for tag in (tags or []) if tag not in blocked and not tag.startswith("editorial_requalifier:")]
    values.append("source:editorial_auto")
    values.append(f"editorial_requalifier:{reason}")
    values.append("visibility:auto_published" if publishable else "visibility:admin_only")
    return sorted(set(values))[:24]


def _parse_number(raw: str, suffix: str | None = None) -> Decimal | None:
    cleaned = raw.replace("\u202f", " ").replace("'", "").strip()
    if re.search(r",\d{3}(\D|$)", cleaned) or re.search(r"\.\d{3}(\D|$)", cleaned):
        cleaned = cleaned.replace(",", "").replace(".", "")
    else:
        cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"\s+", "", cleaned)
    try:
        value = Decimal(cleaned)
    except Exception:
        return None
    suffix_norm = (suffix or "").lower()
    if suffix_norm in {"m", "million", "millions"}:
        value *= Decimal("1000000")
    elif suffix_norm in {"k", "thousand"}:
        value *= Decimal("1000")
    return value if Decimal("1") <= value <= Decimal("10000000000") else None


def _extract_amount(text: str) -> tuple[Decimal | None, str | None]:
    blob = clean_editorial_text(text)
    patterns = (
        r"(?P<cur>US\$|\$|€|CHF|KES|KSH|NGN|₦|XOF|XAF|FCFA|EUR|USD)\s*(?P<num>\d[\d\s,'.,]*)(?:\s*(?P<suf>million|millions|m|k|thousand))?",
        r"(?P<num>\d[\d\s,'.,]*)(?:\s*(?P<suf>million|millions|m|k|thousand))?\s*(?P<cur>US\$|\$|€|CHF|KES|KSH|NGN|₦|XOF|XAF|FCFA|EUR|USD|Naira)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, blob, flags=re.IGNORECASE):
            value = _parse_number(match.group("num"), match.groupdict().get("suf"))
            if not value:
                continue
            currency = CURRENCY_ALIASES.get(match.group("cur").lower(), match.group("cur").upper())
            return value, currency
    return None, None


def _classify_by_pattern(title: str) -> tuple[str, str, list[str], list[str]] | None:
    normalized = _norm(title)
    for marker, french_title, device_type, keywords, beneficiaries in PATTERN_TITLES:
        if marker in normalized:
            return french_title, device_type, keywords, beneficiaries
    return None


def _fallback_title(title: str, device_type: str) -> str:
    cleaned = clean_editorial_text(title)
    cleaned = re.sub(r"^\s*(applications?\s+(?:are\s+)?(?:now\s+)?open(?:\s+for)?|apply\s+now\s+for|call\s+for\s+applications?)\s*[:\-]?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\|\s*.*$", "", cleaned).strip()
    prefix = {
        "subvention": "Subvention",
        "concours": "Concours",
        "aap": "Appel à projets",
        "ami": "Appel à manifestation d'intérêt",
        "accompagnement": "Programme d'accompagnement",
        "investissement": "Opportunité d'investissement",
    }.get(device_type, "Opportunité")
    return f"{prefix} - {cleaned}"[:180]


def _fallback_is_safe(original_title: str, french_title: str) -> bool:
    original = _norm(original_title)
    rewritten = _norm(french_title)
    if any(marker in original or marker in rewritten for marker in ENGLISH_ACTION_MARKERS):
        return False
    english_tokens = (
        "open for",
        "up to $",
        "worth",
        "remote consultancy",
        "leadership and advocacy",
        "funding window",
        "major funding opportunity",
        "learners",
        "advanced grants",
        "unhcr innovation accelerator",
        "funding, mentor",
    )
    return not any(marker in original or marker in rewritten for marker in english_tokens)


def _infer_type(text: str) -> str:
    normalized = _norm(text)
    if any(marker in normalized for marker in ("accelerator", "incubator", "mentorship", "coaching")):
        return "accompagnement"
    if any(marker in normalized for marker in ("competition", "challenge", "prize", "award")):
        return "concours"
    if any(marker in normalized for marker in ("open call", "call for proposals", "call for applications")):
        return "aap"
    if any(marker in normalized for marker in ("investment", "venture capital", "seed funding")):
        return "investissement"
    if any(marker in normalized for marker in ("grant", "fund", "funding", "subvention")):
        return "subvention"
    return "autre"


def _target_score(text: str) -> int:
    normalized = _norm(text)
    score = sum(1 for marker in POSITIVE_MARKERS if marker in normalized)
    score -= 2 * sum(1 for marker in NEGATIVE_MARKERS if marker in normalized)
    return score


def _build_descriptions(device: Device, source: Source, title: str, device_type: str, amount: Decimal | None, currency: str | None) -> tuple[str, str, str]:
    source_name = clean_editorial_text(source.name)
    raw = clean_editorial_text(device.source_raw or "")
    close = device.close_date.strftime("%d/%m/%Y") if device.close_date else "à confirmer"
    amount_label = ""
    if amount and currency:
        amount_label = f" Le montant repéré dans la source est de {int(amount):,} {currency} maximum.".replace(",", " ")
    type_label = {
        "subvention": "un financement non dilutif",
        "aap": "un appel à projets",
        "concours": "un concours ou prix",
        "accompagnement": "un programme d'accompagnement",
        "investissement": "une opportunité de financement privé",
    }.get(device_type, "une opportunité")
    short = (
        f"{title} est {type_label} identifié via {source_name}. "
        f"La fiche a été qualifiée automatiquement pour les entrepreneurs et PME, avec une date limite au {close}."
        f"{amount_label}"
    )
    eligibility = (
        "La cible doit être confirmée sur la page source. Les signaux détectés indiquent une opportunité pertinente "
        "pour startups, PME, entrepreneurs, innovateurs ou organisations porteuses de projet selon les critères de l'appel."
    )
    if any(marker in _norm(raw) for marker in ("women", "female", "fempreneur")):
        eligibility = "La source cible particulièrement les femmes entrepreneures, startups ou PME portées par des femmes."
    elif any(marker in _norm(raw) for marker in ("farmer", "agri", "agripreneur")):
        eligibility = "La source cible des entrepreneurs agricoles, agripreneurs, startups ou PME du secteur agroalimentaire."
    funding = (
        f"Montant indicatif : {int(amount):,} {currency} maximum.".replace(",", " ")
        if amount and currency
        else "Le montant ou les avantages exacts doivent être confirmés sur la source officielle."
    )
    return short, eligibility, funding


def qualify_device(device: Device, source: Source) -> Qualification:
    raw = clean_editorial_text(device.source_raw or device.full_description or device.short_description or "")
    title = clean_editorial_text(device.title or "")
    combined = f"{title}\n{raw}"
    normalized_title = _norm(title)

    if device.status not in {"open", "standby", "recurring"}:
        return Qualification(False, "not_open")
    if device.close_date and device.close_date < date.today():
        return Qualification(False, "expired")
    if not device.close_date and device.status != "recurring":
        return Qualification(False, "missing_deadline")
    if any(marker in normalized_title or marker in _norm(raw[:1600]) for marker in NEGATIVE_MARKERS):
        return Qualification(False, "negative_scope")

    matched = _classify_by_pattern(title)
    if matched:
        french_title, device_type, keywords, beneficiaries = matched
        matched_pattern = True
    else:
        device_type = _infer_type(combined)
        keywords = ["entrepreneuriat", "innovation", "financement"]
        beneficiaries = ["PME", "startups", "entrepreneurs"]
        french_title = _fallback_title(title, device_type)
        matched_pattern = False

    if device_type not in PUBLIC_TYPES:
        return Qualification(False, "unsupported_type")
    if not matched_pattern and not _fallback_is_safe(title, french_title):
        return Qualification(False, "fallback_title_not_premium")
    if _target_score(combined) < 2:
        return Qualification(False, "weak_business_signal")
    if _norm(french_title).count(" ") < 2 or any(marker in _norm(french_title) for marker in ("applications open", "apply now", "call for applications")):
        return Qualification(False, "title_not_rewritten")

    amount, currency = _extract_amount(raw)
    if not amount:
        amount, currency = _extract_amount(title)
    short, eligibility, funding = _build_descriptions(device, source, french_title, device_type, amount, currency)
    return Qualification(
        True,
        "premium_auto_qualified",
        title=french_title,
        device_type=device_type,
        keywords=keywords,
        beneficiaries=beneficiaries,
        amount_max=amount,
        currency=currency,
        funding_details=funding,
        short_description=short,
        eligibility_criteria=eligibility,
    )


async def requalify_editorial_auto_sources(days: int = 21, batch_size: int = 80) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        sources = (await db.execute(select(Source).where(Source.is_active.is_(True)))).scalars().all()
        source_by_id = {source.id: source for source in sources if _is_editorial_source(source)}
        if not source_by_id:
            return {"published": 0, "hidden": 0, "skipped": 0, "items": []}

        devices = (
            await db.execute(
                select(Device)
                .where(
                    Device.source_id.in_(list(source_by_id.keys())),
                    Device.created_at >= now - timedelta(days=days),
                    Device.validation_status.in_(("admin_only", "auto_published")),
                )
                .order_by(Device.created_at.desc())
                .limit(batch_size)
            )
        ).scalars().all()

        for device in devices:
            source = source_by_id.get(device.source_id)
            if not source:
                continue
            qualification = qualify_device(device, source)

            if not qualification.publishable:
                if device.validation_status == "auto_published":
                    device.validation_status = "admin_only"
                    device.user_quality_decision = "admin_only"
                    device.user_quality_score = min(device.user_quality_score or 55, 55)
                    device.user_quality_reasons = [qualification.reason]
                    device.tags = _clean_tags(device.tags, publishable=False, reason=qualification.reason)
                    device.updated_at = now
                    hidden.append({"id": str(device.id), "title": device.title, "reason": qualification.reason})
                else:
                    skipped.append({"id": str(device.id), "title": device.title, "reason": qualification.reason})
                continue

            device.title = qualification.title or device.title
            device.title_normalized = normalize_title(device.title)
            device.device_type = qualification.device_type or device.device_type
            device.keywords = sorted(set((device.keywords or []) + (qualification.keywords or [])))[:20]
            device.beneficiaries = sorted(set((device.beneficiaries or []) + (qualification.beneficiaries or [])))[:12]
            device.short_description = qualification.short_description
            device.eligibility_criteria = qualification.eligibility_criteria
            device.funding_details = qualification.funding_details
            device.amount_max = qualification.amount_max
            if qualification.currency:
                device.currency = qualification.currency
            device.status = "open" if device.close_date and device.close_date >= date.today() else device.status
            device.validation_status = "auto_published"
            device.user_quality_decision = "publish_with_caution"
            device.user_quality_reasons = ["qualification_auto_flux_editorial", "source_a_verifier"]
            device.ai_rewrite_status = "done"
            device.ai_rewrite_model = "editorial_requalifier_v1"
            device.ai_rewrite_checked_at = now
            device.tags = _clean_tags(device.tags, publishable=True, reason=qualification.reason)
            device.updated_at = now

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            payload["tags"] = device.tags
            sections = build_content_sections(payload, _source_dict(source))
            device.content_sections_json = sections
            device.ai_rewritten_sections_json = sections
            rendered = render_sections_markdown(sections)
            if rendered:
                device.full_description = rendered

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            payload["tags"] = device.tags
            readiness = compute_ai_readiness(payload, _source_dict(source))
            quality = compute_user_quality(payload)
            device.ai_readiness_score = readiness.score
            device.ai_readiness_label = readiness.label
            device.ai_readiness_reasons = readiness.reasons
            device.user_quality_score = quality.score
            if quality.decision in {"admin_only", "reject"}:
                device.validation_status = "admin_only"
                device.user_quality_decision = "admin_only"
                device.user_quality_reasons = quality.reasons + ["quality_gate_after_rewrite"]
                hidden.append({"id": str(device.id), "title": device.title, "reason": "quality_gate_after_rewrite"})
                continue

            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source": source.name,
                    "type": device.device_type,
                    "close_date": str(device.close_date) if device.close_date else None,
                    "amount_max": float(device.amount_max) if device.amount_max is not None else None,
                    "currency": device.currency,
                    "user_quality_score": device.user_quality_score,
                }
            )

        await db.commit()

    return {
        "published": len(changed),
        "hidden": len(hidden),
        "skipped": len(skipped),
        "items": changed,
        "hidden_sample": hidden[:10],
        "skipped_sample": skipped[:10],
    }
