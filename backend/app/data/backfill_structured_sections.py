import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    sanitize_text,
)


def _extract_presentation(device: Device) -> str:
    if device.short_description:
        return clean_editorial_text(device.short_description)

    source_raw = (device.source_raw or "").strip()
    if not source_raw:
        return ""

    first_block = source_raw.split("\n\n", 1)[0].strip()
    return clean_editorial_text(first_block)


def _format_amount(value: Decimal | None, currency: str) -> str:
    if value is None:
        return ""
    amount = float(value)
    if amount.is_integer():
        amount_str = f"{int(amount):,}".replace(",", " ")
    else:
        amount_str = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    symbol = "EUR" if not currency else currency
    return f"{amount_str} {symbol}"


def _extract_funding(device: Device) -> str:
    existing = clean_editorial_text(device.funding_details or "")
    normalized_existing = sanitize_text(existing).lower()
    if existing and not (
        "montant ou les avantages ne sont pas precises" in normalized_existing
        or "montant exact doit etre confirme" in normalized_existing
        or "modalites financieres exactes doivent etre confirmees" in normalized_existing
        or "avantages associes" in normalized_existing
    ):
        return existing

    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            return (
                f"Montant indicatif compris entre {_format_amount(device.amount_min, device.currency)} "
                f"et {_format_amount(device.amount_max, device.currency)}."
            )
        amount = device.amount_max or device.amount_min
        if amount:
            return f"Montant indicatif : {_format_amount(amount, device.currency)}."

    return build_contextual_funding(
        text=(device.source_raw or "") or (device.short_description or ""),
        device_type=device.device_type,
        amount_min=device.amount_min,
        amount_max=device.amount_max,
        currency=device.currency,
    )


def _extract_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    normalized_existing = sanitize_text(existing).lower()
    if existing and not (
        "criteres detailles doivent etre confirmes" in normalized_existing
        or "conditions detaillees de recevabilite doivent etre confirmees" in normalized_existing
    ):
        return existing
    return build_contextual_eligibility(
        text=(device.source_raw or "") or (device.short_description or ""),
        beneficiaries=device.beneficiaries,
        country=device.country,
        geographic_scope=device.geographic_scope,
    )


def _extract_procedure(device: Device, source_name: str) -> str:
    organism = sanitize_text(device.organism or "").strip()
    if "les-aides.fr" in source_name.lower():
        if organism:
            return (
                f"La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle, "
                f"avec instruction a confirmer aupres de {organism}."
            )
        return "La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle."
    if organism:
        return f"La consultation detaillee se fait aupres de {organism} via la source officielle."
        return "La consultation detaillee se fait depuis la source officielle."


def _is_generic_eligibility(value: str) -> bool:
    normalized = sanitize_text(value or "").lower()
    return (
        "criteres detailles doivent etre confirmes" in normalized
        or "conditions detaillees de recevabilite doivent etre confirmees" in normalized
    )


def _is_generic_funding(value: str) -> bool:
    normalized = sanitize_text(value or "").lower()
    return (
        "montant ou les avantages ne sont pas precises" in normalized
        or "montant exact doit etre confirme" in normalized
        or "modalites financieres exactes doivent etre confirmees" in normalized
        or "avantages associes" in normalized
    )


async def run_backfill(source_name: str, limit: int | None = None, dry_run: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == source_name))
        ).scalar_one_or_none()
        if not source:
            raise RuntimeError(f"Source introuvable: {source_name}")

        query = (
            select(Device)
            .where(Device.source_id == source.id)
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)

        devices = (await db.execute(query)).scalars().all()
        updated = 0
        matched = 0
        preview = []

        for device in devices:
            presentation = _extract_presentation(device)
            if not presentation:
                continue
            current_full = (device.full_description or "").strip()
            eligibility = _extract_eligibility(device)
            funding = _extract_funding(device)

            full_description = build_structured_sections(
                presentation=presentation,
                eligibility=eligibility or None,
                funding=funding or None,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=_extract_procedure(device, source.name),
                recurrence_notes=device.recurrence_notes,
            )
            if not full_description:
                continue

            needs_update = (
                not current_full.startswith("## Presentation")
                or not (device.eligibility_criteria or "").strip()
                or not (device.funding_details or "").strip()
                or _is_generic_eligibility(device.eligibility_criteria or "")
                or _is_generic_funding(device.funding_details or "")
            )
            if not needs_update:
                continue

            matched += 1

            if len(preview) < 5:
                preview.append({"title": device.title, "before": current_full[:120], "after": full_description[:180]})

            if not dry_run:
                device.full_description = full_description
                if eligibility:
                    device.eligibility_criteria = eligibility
                if funding:
                    device.funding_details = funding
                updated += 1

        if not dry_run:
            await db.commit()

        return {
            "source": source.name,
            "matched": matched,
            "updated": updated,
            "preview": preview,
            "dry_run": dry_run,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(run_backfill(args.source_name, limit=args.limit, dry_run=args.dry_run))
    print(result)


if __name__ == "__main__":
    main()
