"""Structure les montants detectables sur les fiches visibles.

Le script reste volontairement conservateur: il ne remplit amount_min/amount_max
que lorsqu'une devise ou une unite monetaire claire est presente, et il remplit
funding_rate pour les aides exprimees en pourcentage.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
VISIBLE_STATUSES = {"open", "recurring", "standby"}
MONETARY_CONTEXT = {
    "aide",
    "amount",
    "award",
    "budget",
    "cofinancement",
    "concours",
    "credit",
    "dotation",
    "enveloppe",
    "financement",
    "funding",
    "garantie",
    "grant",
    "investment",
    "montant",
    "plafond",
    "pret",
    "prime",
    "prize",
    "subvention",
    "ticket",
}
RATE_CONTEXT = {
    "abattement",
    "aide",
    "cofinancement",
    "couverture",
    "depenses",
    "exoneration",
    "financement",
    "garantie",
    "prise en charge",
    "quotite",
    "reduction",
    "subvention",
    "taux",
}
CURRENCY_ALIASES = {
    "$": "USD",
    "cad": "CAD",
    "cfa": "XOF",
    "fcfa": "XOF",
    "gbp": "GBP",
    "mad": "MAD",
    "tnd": "TND",
    "usd": "USD",
    "xof": "XOF",
    "£": "GBP",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
}


@dataclass
class StructuredAmount:
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    currency: str | None = None
    funding_rate: Decimal | None = None


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _flatten_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_json(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_json(item) for item in value)
    return str(value)


def _device_text(device: Device) -> str:
    if device.funding_details and len(device.funding_details.strip()) >= 30:
        return device.funding_details
    parts = [
        device.title,
        device.short_description,
        device.funding_details,
        device.eligibility_criteria,
        _flatten_json(device.content_sections_json),
        _flatten_json(device.ai_rewritten_sections_json),
    ]
    return " ".join(part for part in parts if part)


def _has_context(text: str, start: int, end: int, keywords: set[str], radius: int = 90) -> bool:
    window = _strip_accents(text[max(0, start - radius) : min(len(text), end + radius)]).lower()
    return any(keyword in window for keyword in keywords)


def _parse_number(raw: str) -> Decimal | None:
    value = raw.replace("\u00a0", " ").strip()
    value = re.sub(r"\s+", "", value)
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        value = "".join(parts) if len(parts[-1]) == 3 else value.replace(",", ".")
    elif value.count(".") > 1:
        value = value.replace(".", "")
    try:
        return Decimal(value)
    except Exception:
        return None


def _currency_from_token(token: str) -> str | None:
    normalized = _strip_accents(token).lower()
    for alias, currency in CURRENCY_ALIASES.items():
        if alias in normalized:
            return currency
    return None


def _multiplier_from_token(token: str) -> Decimal:
    normalized = _strip_accents(token).lower()
    if re.search(r"\b(k|k€|keur|k eur|thousand)\b", normalized):
        return Decimal("1000")
    if re.search(r"\b(m|m€|meur|m eur|million|millions)\b", normalized):
        return Decimal("1000000")
    if re.search(r"\b(milliard|milliards|billion)\b", normalized):
        return Decimal("1000000000")
    return Decimal("1")


def _extract_money_values(text: str) -> tuple[list[Decimal], str | None]:
    compact = re.sub(r"\s+", " ", text or "")
    values: list[Decimal] = []
    detected_currency: str | None = None

    range_pattern = re.compile(
        r"(?P<min>\d+(?:[\s\u00a0.,]\d{3})*(?:[,.]\d+)?|\d+(?:[,.]\d+)?)\s*"
        r"(?P<min_unit>k\s?€|m\s?€|k\s?eur|m\s?eur|keur|meur)?\s*"
        r"(?:-|–|a|à|to|et|entre)\s*"
        r"(?P<max>\d+(?:[\s\u00a0.,]\d{3})*(?:[,.]\d+)?|\d+(?:[,.]\d+)?)\s*"
        r"(?P<max_unit>k\s?€|m\s?€|k\s?eur|m\s?eur|keur|meur|€|eur|euros?|usd|\$|£|gbp|cad|fcfa|cfa|xof|mad|tnd)",
        re.IGNORECASE,
    )
    for match in range_pattern.finditer(compact):
        if not _has_context(compact, match.start(), match.end(), MONETARY_CONTEXT):
            continue
        min_value = _parse_number(match.group("min"))
        max_value = _parse_number(match.group("max"))
        if min_value is None or max_value is None:
            continue
        unit = f"{match.group('min_unit') or match.group('max_unit') or ''}"
        min_amount = (min_value * _multiplier_from_token(unit)).quantize(Decimal("0.01"))
        max_amount = (max_value * _multiplier_from_token(match.group("max_unit") or unit)).quantize(Decimal("0.01"))
        if Decimal("100") <= min_amount <= Decimal("1000000000") and Decimal("100") <= max_amount <= Decimal("1000000000"):
            values.extend([min_amount, max_amount])
            detected_currency = detected_currency or _currency_from_token(unit) or _currency_from_token(match.group("max_unit") or "") or "EUR"

    pattern = re.compile(
        r"(?P<prefix>[$€£])?\s*"
        r"(?P<number>\d+(?:[\s\u00a0.,]\d{3})*(?:[,.]\d+)?|\d+(?:[,.]\d+)?)\s*"
        r"(?P<suffix>"
        r"k\s?€|m\s?€|k\s?eur|m\s?eur|keur|meur|"
        r"millions?\s+d[' ]?euros?|millions?\s+(?:fcfa|cfa|xof|usd|eur)|"
        r"milliards?\s+d[' ]?euros?|milliards?\s+(?:fcfa|cfa|xof|usd|eur)|"
        r"€|eur|euros?|usd|\$|£|gbp|cad|fcfa|cfa|xof|mad|tnd"
        r")?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(compact):
        token = match.group(0)
        suffix = match.group("suffix") or ""
        prefix = match.group("prefix") or ""
        after = compact[match.end() : match.end() + 18].lower()
        before = compact[max(0, match.start() - 18) : match.start()].lower()

        has_currency = bool(prefix or _currency_from_token(suffix))
        has_large_unit = bool(re.search(r"million|milliard|m\s?€|m\s?eur|meur|k\s?€|k\s?eur|keur", suffix, re.I))
        if not has_currency and not has_large_unit:
            continue
        if re.search(r"^\s*(ans?|mois|jours?|semaines?|heures?|%|eme|er)\b", after, re.I):
            continue
        if re.search(r"\b(article|phase|annee|exercice|op|lot)\s*$", before, re.I):
            continue
        if not has_currency and not _has_context(compact, match.start(), match.end(), MONETARY_CONTEXT):
            continue

        number = _parse_number(match.group("number"))
        if number is None:
            continue
        value = number * _multiplier_from_token(token)
        if value < Decimal("100") or value > Decimal("1000000000"):
            continue
        values.append(value.quantize(Decimal("0.01")))
        detected_currency = detected_currency or _currency_from_token(f"{prefix} {suffix}") or "EUR"

    return values, detected_currency


def _extract_funding_rate(text: str) -> Decimal | None:
    compact = re.sub(r"\s+", " ", text or "")
    rates: list[Decimal] = []
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:[,.]\d+)?)\s*%", compact):
        window = _strip_accents(compact[max(0, match.start() - 70) : min(len(compact), match.end() + 70)]).lower()
        if any(term in window for term in ("taux fixe", "taux variable", "taux d'interet", "taux interet", "assurance emprunteur", "prefinancement")):
            continue
        if not _has_context(compact, match.start(), match.end(), RATE_CONTEXT, radius=80):
            continue
        value = _parse_number(match.group(1))
        if value is None or value <= 0 or value > 100:
            continue
        rates.append(value.quantize(Decimal("0.01")))
    return max(rates) if rates else None


def extract_structured_amount(device: Device) -> StructuredAmount:
    text = _device_text(device)
    values, currency = _extract_money_values(text)
    rate = _extract_funding_rate(text)
    if device.device_type in {"pret", "avance_remboursable"}:
        rate = None
    if not values and rate is None:
        return StructuredAmount()
    return StructuredAmount(
        amount_min=min(values) if len(set(values)) >= 2 else None,
        amount_max=max(values) if values else None,
        currency=currency,
        funding_rate=rate,
    )


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device)
            .where(
                Device.status.in_(VISIBLE_STATUSES),
                Device.validation_status.in_(VISIBLE_VALIDATION_STATUSES),
                or_(
                    Device.user_quality_decision.is_(None),
                    Device.user_quality_decision.in_(VISIBLE_USER_DECISIONS - {None}),
                ),
                Device.amount_min.is_(None),
                Device.amount_max.is_(None),
            )
            .order_by(Device.updated_at.desc())
        )
        devices = list(result.scalars().all())
        if limit:
            devices = devices[:limit]

        changes: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for device in devices:
            structured = extract_structured_amount(device)
            if structured.amount_max is None and structured.funding_rate is None:
                continue
            will_set_amount = structured.amount_min is not None or structured.amount_max is not None
            will_set_rate = structured.funding_rate is not None and device.funding_rate is None
            if not will_set_amount and not will_set_rate:
                continue

            row = {
                "id": str(device.id),
                "title": device.title,
                "country": device.country,
                "status": device.status,
                "amount_min": str(structured.amount_min) if structured.amount_min is not None else None,
                "amount_max": str(structured.amount_max) if structured.amount_max is not None else None,
                "currency": structured.currency,
                "funding_rate": str(structured.funding_rate) if structured.funding_rate is not None else None,
            }
            changes.append(row)

            if not apply:
                continue
            if structured.amount_min is not None:
                device.amount_min = structured.amount_min
            if structured.amount_max is not None:
                device.amount_max = structured.amount_max
            if structured.currency:
                device.currency = structured.currency
            if structured.funding_rate is not None and device.funding_rate is None:
                device.funding_rate = structured.funding_rate
            tags = set(device.tags or [])
            tags.add("quality:amount_structured_auto")
            device.tags = sorted(tags)
            device.updated_at = now

        if apply:
            await db.commit()

        return {
            "scanned": len(devices),
            "updated": len(changes) if apply else 0,
            "candidates": len(changes),
            "sample": changes[:30],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
