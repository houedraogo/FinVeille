import argparse
import asyncio
import json
from datetime import date
from typing import Any

from sqlalchemy import or_, select
from unidecode import unidecode

from app.collector.base_connector import RawItem
from app.collector.normalizer import Normalizer
from app.data.cleanup_existing_catalog import _extract_metadata_from_source_raw, _source_to_dict
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


def _clean_sentence(text: str | None) -> str:
    value = clean_editorial_text(text or "")
    value = value.replace(" :", ":")
    value = " ".join(value.split())
    return value.strip(" .")


def _country_phrase(country: str) -> str:
    cleaned = _clean_sentence(country)
    if not cleaned:
        return "dans le pays cible"
    normalized = unidecode(cleaned.lower())
    if normalized in {"madagascar"}:
        return f"à {cleaned}"
    if normalized.startswith(("a", "e", "i", "o", "u", "y")):
        return f"en {cleaned}"
    if normalized in {"tunisie", "guinee", "mauritanie", "ethiopie", "cote d'ivoire"}:
        return f"en {cleaned}"
    return f"au {cleaned}"


def _append_sentence(parts: list[str], text: str | None) -> None:
    value = _clean_sentence(text)
    if not value:
        return
    if not value.endswith((".", "!", "?")):
        value += "."
    normalized = unidecode(value.lower())
    if normalized not in {unidecode(part.lower()) for part in parts}:
        parts.append(value)


def _format_amount(raw_amount: Any) -> str | None:
    if raw_amount in (None, "", "0", 0):
        return None
    try:
        value = float(str(raw_amount).replace(",", ""))
    except ValueError:
        return _clean_sentence(str(raw_amount)) or None
    if value <= 0:
        return None
    if value.is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _pick_country(device: Device, source: Source, normalized: dict[str, Any], normalizer: Normalizer, metadata: dict[str, Any]) -> str:
    source_country = normalizer._canonicalize_country_name(source.country) or source.country or device.country  # noqa: SLF001
    metadata_country = normalizer._canonicalize_country_name(  # noqa: SLF001
        metadata.get("countryshortname") or normalized.get("country") or device.country
    )
    if metadata_country and metadata_country != "France":
        return metadata_country
    if source_country:
        return source_country
    return metadata_country or device.country or "Pays non precise"


def _localized_sectors(device: Device, normalized: dict[str, Any], normalizer: Normalizer, metadata: dict[str, Any]) -> list[str]:
    sector_values = []
    for key in ("sector1.Name", "sector2.Name", "sector.Name", "mjsector_namecode"):
        value = normalizer._get_nested_metadata_value(metadata, key)  # noqa: SLF001
        if value:
            sector_values.append(str(value))
    for existing in normalized.get("sectors") or device.sectors or []:
        sector_values.append(str(existing))

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in sector_values:
        localized = normalizer._localize_sector_label(value)  # noqa: SLF001
        localized = _clean_sentence(localized)
        if not localized:
            continue
        key = unidecode(localized.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(localized)
    return cleaned[:3]


def _build_summary(
    *,
    device: Device,
    source: Source,
    normalized: dict[str, Any],
    normalizer: Normalizer,
    metadata: dict[str, Any],
    country: str,
) -> str:
    parts: list[str] = []
    sectors = _localized_sectors(device, normalized, normalizer, metadata)
    approval_date = normalizer._format_iso_date(metadata.get("boardapprovaldate"))  # noqa: SLF001
    close_date = normalized.get("close_date") or device.close_date
    total_commitment = _format_amount(metadata.get("totalcommamt") or normalized.get("amount_max") or device.amount_max)

    _append_sentence(parts, f"Ce projet institutionnel de la Banque mondiale est porté {_country_phrase(country)}")
    if sectors:
        _append_sentence(parts, "Il concerne principalement les secteurs suivants : " + ", ".join(sectors))
    if total_commitment:
        _append_sentence(parts, f"L'engagement total annonce atteint {total_commitment}")
    if approval_date:
        _append_sentence(parts, f"La date d'approbation indiquée est le {approval_date}")
    if close_date:
        _append_sentence(parts, f"La clôture prévisionnelle est fixée au {close_date.strftime('%d/%m/%Y')}")
    else:
        _append_sentence(parts, "La source ne communique pas de date de clôture exploitable à ce stade")
    _append_sentence(parts, "Les conditions opérationnelles doivent être confirmées sur la page officielle du projet")
    summary = " ".join(parts)
    if len(clean_editorial_text(summary)) < 120:
        _append_sentence(
            parts,
            "Cette fiche suit un projet institutionnel de financement public, et non un appel à candidatures classique",
        )
        summary = " ".join(parts)
    return summary


def _build_eligibility(country: str) -> str:
    return (
        f"Il s'agit d'un projet institutionnel porté {_country_phrase(country)}. "
        "La source ne présente pas de critères d'éligibilité comparables à un appel à candidatures classique ; "
        "les bénéficiaires, partenaires et modalités d'intervention doivent donc être vérifiés sur la page officielle du projet."
    )


def _build_funding(metadata: dict[str, Any], normalized: dict[str, Any]) -> str:
    total_commitment = _format_amount(metadata.get("totalcommamt") or normalized.get("amount_max"))
    if total_commitment:
        return (
            f"L'engagement total annoncé pour ce projet atteint {total_commitment}. "
            "La ventilation détaillée des financements et des composantes doit être confirmée sur la source officielle."
        )
    return (
        "La Banque mondiale référence ici un projet institutionnel sans montant détaillé directement exploitable "
        "dans le flux actuel. Les enveloppes et composantes financières doivent être confirmées sur la source officielle."
    )


def _build_procedure() -> str:
    return (
        "La consultation détaillée se fait depuis la page officielle du projet World Bank. "
        "Cette fiche sert surtout à suivre un projet, ses dates clés et ses informations publiques de référence."
    )


def _build_rejected_summary(country: str) -> str:
    return (
        f"Projet World Bank conservé pour traçabilité interne {_country_phrase(country)}. "
        "La fiche n'est pas publiée car les informations éditoriales exploitables restent insuffisantes dans le flux actuel."
    )


def _apply_status(device: Device, normalized: dict[str, Any]) -> None:
    close_date = normalized.get("close_date") or device.close_date
    device.is_recurring = False
    device.recurrence_notes = None
    if close_date and close_date < date.today():
        device.status = "expired"
        return
    if close_date:
        device.status = "open"
        return
    device.status = "standby"


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    stats = {
        "scanned": 0,
        "updated": 0,
        "auto_published": 0,
        "expired": 0,
        "standby": 0,
        "open": 0,
    }
    preview: list[dict[str, Any]] = []
    gate = DeviceQualityGate()

    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .join(Source, Source.id == Device.source_id)
            .where(
                or_(
                    Device.organism.ilike("%World Bank%"),
                    Source.organism.ilike("%World Bank%"),
                    Source.name.ilike("%Banque Mondiale%"),
                    Source.url.ilike("%worldbank%"),
                ),
            )
            .order_by(Source.country.asc(), Device.title.asc())
        )
        if limit:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

        for device, source in rows:
            stats["scanned"] += 1
            raw_content, metadata = _extract_metadata_from_source_raw(device.source_raw)
            normalizer = Normalizer(_source_to_dict(source))
            country = _pick_country(device, source, {}, normalizer, metadata)

            if device.validation_status == "rejected":
                rejected_summary = _build_rejected_summary(country)
                device.country = country
                device.short_description = rejected_summary[:500]
                device.full_description = build_structured_sections(
                    presentation=rejected_summary,
                    eligibility="Informations insuffisantes pour une publication utilisateur dans l'état actuel du flux source.",
                    funding="Aucun montant exploitable n'a pu être confirmé de manière fiable pour publication.",
                    open_date=device.open_date,
                    close_date=device.close_date,
                    procedure="Fiche conservée uniquement pour traçabilité interne et contrôle qualité.",
                    recurrence_notes=None,
                )
                payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                device.completeness_score = compute_completeness(payload)
                stats["updated"] += 1
                continue

            normalized = normalizer.normalize(
                RawItem(
                    title=device.title,
                    url=device.source_url,
                    raw_content=raw_content,
                    source_id=str(device.source_id),
                    metadata=metadata,
                )
            ) or {}

            country = _pick_country(device, source, normalized, normalizer, metadata)
            summary = _build_summary(
                device=device,
                source=source,
                normalized=normalized,
                normalizer=normalizer,
                metadata=metadata,
                country=country,
            )
            eligibility = _build_eligibility(country)
            funding = _build_funding(metadata, normalized)
            procedure = _build_procedure()
            close_date = normalized.get("close_date") or device.close_date
            open_date = normalized.get("open_date") or device.open_date
            full_description = build_structured_sections(
                presentation=summary,
                eligibility=eligibility,
                funding=funding,
                open_date=open_date,
                close_date=close_date,
                procedure=procedure,
                recurrence_notes=None,
            )

            before = {
                "short_description": device.short_description,
                "validation_status": device.validation_status,
                "status": device.status,
                "country": device.country,
            }

            device.device_type = "institutional_project"
            device.country = country
            device.short_description = summary[:500]
            device.full_description = full_description
            device.eligibility_criteria = eligibility
            device.funding_details = funding
            if normalized.get("amount_max") is not None:
                device.amount_max = normalized.get("amount_max")
            if normalized.get("amount_min") is not None:
                device.amount_min = normalized.get("amount_min")
            if close_date is not None:
                device.close_date = close_date
            if open_date is not None:
                device.open_date = open_date

            localized_sectors = _localized_sectors(device, normalized, normalizer, metadata)
            if localized_sectors:
                device.sectors = localized_sectors

            _apply_status(device, normalized)
            device.language = "fr"

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            decision = gate.evaluate(payload)
            device.validation_status = decision.validation_status
            if device.device_type == "institutional_project" and device.status in {"standby", "open", "expired"}:
                if len(clean_editorial_text(device.short_description or "")) >= 120:
                    device.validation_status = "auto_published"
            device.completeness_score = compute_completeness(payload)

            after = {
                "short_description": device.short_description,
                "validation_status": device.validation_status,
                "status": device.status,
                "country": device.country,
            }
            if before != after or before["short_description"] != after["short_description"]:
                stats["updated"] += 1
                stats[device.status] = stats.get(device.status, 0) + 1
                if device.validation_status == "auto_published":
                    stats["auto_published"] += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "country": device.country,
                            "status": device.status,
                            "validation_status": device.validation_status,
                            "before": (before["short_description"] or "")[:140],
                            "after": (after["short_description"] or "")[:220],
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les fiches World Bank existantes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
