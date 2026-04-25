import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from unidecode import unidecode

from app.collector.base_connector import RawItem
from app.collector.normalizer import Normalizer
from app.collector.source_profiles import get_source_profile
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import (
    clean_editorial_text,
    compute_completeness,
    has_recurrence_evidence,
    localize_investment_text,
    looks_english_text,
    normalize_title,
    sanitize_text,
)


UNUSABLE_MARKERS = (
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

PURGE_SOURCE_DOMAINS = ("data.gouv.fr",)


@dataclass
class CleanupStats:
    scanned: int = 0
    restructured: int = 0
    translated: int = 0
    reclassified: int = 0
    pending_review: int = 0
    rejected: int = 0
    duplicate_rejected: int = 0
    purge_candidates: int = 0
    purged_devices: int = 0
    purged_sources: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _source_to_dict(source: Source | None) -> dict[str, Any]:
    if not source:
        return {
            "id": None,
            "name": "Source inconnue",
            "organism": "",
            "country": "",
            "url": "",
            "config": {},
            "language": "fr",
        }
    return {
        "id": str(source.id),
        "name": source.name,
        "organism": source.organism,
        "country": source.country,
        "url": source.url,
        "config": source.config or {},
        "language": (source.config or {}).get("language", "fr"),
    }


def _extract_metadata_from_source_raw(source_raw: str | None) -> tuple[str, dict[str, Any]]:
    raw = source_raw or ""
    if not raw.strip():
        return "", {}

    for marker in ("\n\n{", "\r\n\r\n{"):
        idx = raw.rfind(marker)
        if idx >= 0:
            candidate = raw[idx + len(marker) - 1 :].strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return raw[:idx].strip(), parsed
            except json.JSONDecodeError:
                pass

    idx = raw.rfind("{")
    if idx >= 0:
        try:
            parsed = json.loads(raw[idx:].strip())
            if isinstance(parsed, dict):
                return raw[:idx].strip(), parsed
        except json.JSONDecodeError:
            pass

    return raw.strip(), {}


def _quality_blob(device: Device) -> str:
    return unidecode(
        sanitize_text(
            " ".join(
                value or ""
                for value in (
                    device.title,
                    device.short_description,
                    device.full_description,
                    device.eligibility_criteria,
                    device.funding_details,
                    device.source_raw,
                    device.source_url,
                )
            )
        ).lower()
    )


def _is_unusable_device(device: Device) -> bool:
    blob = _quality_blob(device)
    if any(marker in blob for marker in UNUSABLE_MARKERS):
        return True
    if any(domain in (device.source_url or "").lower() for domain in PURGE_SOURCE_DOMAINS):
        text_len = len(clean_editorial_text((device.short_description or "") + " " + (device.full_description or "")))
        return text_len < 180
    return False


def _is_expired_with_bad_source(device: Device, source: Source | None) -> bool:
    if device.status != "expired" and not (device.close_date and device.close_date < date.today()):
        return False
    if source and (source.consecutive_errors or 0) >= 2:
        return True
    return any(marker in _quality_blob(device) for marker in ("404", "410", "url non publique", "impossible d'acceder"))


def _has_business_content(device: Device) -> bool:
    return any(
        [
            len(clean_editorial_text(device.eligibility_criteria or "")) >= 60,
            len(clean_editorial_text(device.funding_details or "")) >= 45,
            bool(device.amount_min or device.amount_max),
            bool(device.close_date),
        ]
    )


def _is_private_investor(device: Device, source: Source | None) -> bool:
    haystack = unidecode(f"{device.organism or ''} {source.name if source else ''} {source.url if source else ''}".lower())
    return any(
        marker in haystack
        for marker in (
            "africinvest",
            "bpifrance investissement",
            "bpi france investissement",
            "partech",
            "france angels",
            "femmes business angels",
            "amoon",
            "investisseurs & partenaires",
            "i&p",
        )
    )


def _patch_device_from_normalized(device: Device, normalized: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    writable_fields = {
        "short_description",
        "full_description",
        "eligibility_criteria",
        "funding_details",
        "close_date",
        "open_date",
        "status",
        "is_recurring",
        "recurrence_notes",
        "device_type",
        "aid_nature",
        "country",
        "region",
        "zone",
        "geographic_scope",
        "sectors",
        "beneficiaries",
        "amount_min",
        "amount_max",
        "currency",
        "keywords",
        "language",
    }
    for field in writable_fields:
        value = normalized.get(field)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if field in {"sectors", "beneficiaries", "keywords"} and value == []:
            continue
        current = getattr(device, field, None)
        if current != value:
            setattr(device, field, value)
            changed.append(field)
    return changed


def _normalized_description_is_better(device: Device, normalized: dict[str, Any]) -> bool:
    before = clean_editorial_text(device.full_description or "")
    after = clean_editorial_text(normalized.get("full_description") or "")
    if not after:
        return False
    if not before:
        return True

    before_norm = unidecode(before.lower())
    after_norm = unidecode(after.lower())

    generic_after_markers = (
        "ce projet est porte au france",
        "ce projet est porte en france",
        "les criteres detailles doivent etre confirmes sur la source officielle",
        "le montant ou les avantages ne sont pas precises clairement par la source",
    )
    generic_before_count = sum(1 for marker in generic_after_markers if marker in before_norm)
    generic_after_count = sum(1 for marker in generic_after_markers if marker in after_norm)
    if generic_after_count > generic_before_count:
        return False

    if len(after) < max(220, int(len(before) * 0.75)):
        return False

    before_sections = before.count("## ")
    after_sections = after.count("## ")
    if before_sections >= 4 and after_sections < before_sections:
        return False

    return True


def _reclassify_device(device: Device, source: Source | None) -> list[str]:
    changed: list[str] = []
    text_blob = sanitize_text(
        " ".join(
            value or ""
            for value in (
                device.title,
                device.short_description,
                device.full_description,
                device.source_raw,
                device.recurrence_notes,
            )
        )
    )
    profile = get_source_profile(_source_to_dict(source))

    if profile and profile.source_kind == "institutional_project" and device.device_type != "institutional_project":
        device.device_type = "institutional_project"
        changed.append("device_type")

    if device.status == "open" and not device.close_date:
        if has_recurrence_evidence(text_blob) or (profile and profile.default_status_without_close_date == "recurring"):
            if device.status != "recurring" or not device.is_recurring:
                device.status = "recurring"
                device.is_recurring = True
                device.recurrence_notes = device.recurrence_notes or (
                    "Classe automatiquement comme dispositif recurrent: preuve de fonctionnement sans fenetre unique."
                )
                changed.extend(["status", "is_recurring", "recurrence_notes"])
        else:
            tags = set(device.tags or [])
            tags.add("quality:unknown_deadline")
            if device.status != "standby":
                device.status = "standby"
                changed.append("status")
            if device.validation_status != "pending_review":
                device.validation_status = "pending_review"
                changed.append("validation_status")
            if sorted(tags) != (device.tags or []):
                device.tags = sorted(tags)
                changed.append("tags")

    return changed


def _apply_quality_decision(device: Device) -> list[str]:
    changed: list[str] = []
    gate = DeviceQualityGate()
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    decision = gate.evaluate(payload)
    tags = set(device.tags or [])
    tags.update(f"quality:{reason}" for reason in decision.reasons)

    if device.validation_status != decision.validation_status:
        device.validation_status = decision.validation_status
        changed.append("validation_status")
    if sorted(tags) != (device.tags or []):
        device.tags = sorted(tags)
        changed.append("tags")
    return changed


def _duplicate_key(device: Device) -> tuple[str, str, str]:
    return (
        normalize_title(device.title or ""),
        unidecode((device.organism or "").lower()).strip(),
        unidecode((device.country or "").lower()).strip(),
    )


def _choose_duplicate_winner(devices: list[Device]) -> Device:
    def score(device: Device) -> tuple[int, int, int]:
        validation_weight = {"approved": 4, "validated": 4, "auto_published": 3, "pending_review": 2, "rejected": 0}
        return (
            validation_weight.get(device.validation_status or "", 1),
            int(device.completeness_score or 0),
            len(clean_editorial_text(device.full_description or "")),
        )

    return sorted(devices, key=score, reverse=True)[0]


async def cleanup_catalog(
    *,
    apply: bool = False,
    limit: int | None = None,
    source_name: str | None = None,
    source_contains: str | None = None,
    purge: bool = False,
) -> dict[str, Any]:
    stats = CleanupStats()
    previews: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async with AsyncSessionLocal() as db:
        source_query = select(Source)
        if source_name:
            source_query = source_query.where(Source.name == source_name)
        if source_contains:
            needle = f"%{source_contains}%"
            source_query = source_query.where(Source.name.ilike(needle) | Source.organism.ilike(needle) | Source.url.ilike(needle))
        sources = (await db.execute(source_query)).scalars().all()
        sources_by_id = {source.id: source for source in sources}

        query = select(Device)
        if source_name:
            query = query.where(Device.source_id.in_(list(sources_by_id.keys())))
        if source_contains:
            query = query.where(Device.source_id.in_(list(sources_by_id.keys())))
        query = query.order_by(Device.updated_at.desc().nullslast())
        if limit:
            query = query.limit(limit)
        devices = (await db.execute(query)).scalars().all()

        duplicate_groups: dict[tuple[str, str, str], list[Device]] = defaultdict(list)
        for device in devices:
            duplicate_groups[_duplicate_key(device)].append(device)

        duplicate_losers = set()
        for group in duplicate_groups.values():
            if len(group) <= 1:
                continue
            winner = _choose_duplicate_winner(group)
            for device in group:
                if device.id != winner.id:
                    duplicate_losers.add(device.id)

        with db.no_autoflush:
            for device in devices:
                stats.scanned += 1
                source = sources_by_id.get(device.source_id)
                changed: list[str] = []

                if device.id in duplicate_losers:
                    if device.validation_status != "rejected":
                        if apply:
                            device.validation_status = "rejected"
                            tags = set(device.tags or [])
                            tags.add("quality:duplicate_candidate")
                            device.tags = sorted(tags)
                            changed.extend(["validation_status", "tags"])
                        stats.duplicate_rejected += 1
                        if len(previews["duplicates"]) < 8:
                            previews["duplicates"].append({"title": device.title, "source_url": device.source_url})

                purge_candidate = _is_unusable_device(device) or _is_expired_with_bad_source(device, source)
                if purge_candidate:
                    stats.purge_candidates += 1
                    if len(previews["purge_candidates"]) < 10:
                        previews["purge_candidates"].append(
                            {"title": device.title, "status": device.status, "source_url": device.source_url}
                        )
                    if purge and apply:
                        await db.delete(device)
                        stats.purged_devices += 1
                        continue
                    if device.validation_status != "rejected":
                        if apply:
                            device.validation_status = "rejected"
                            tags = set(device.tags or [])
                            tags.add("quality:purge_candidate")
                            device.tags = sorted(tags)
                            changed.extend(["validation_status", "tags"])
                        stats.rejected += 1

                raw_content, metadata = _extract_metadata_from_source_raw(device.source_raw)
                if raw_content or metadata:
                    normalizer = Normalizer(_source_to_dict(source))
                    normalized = normalizer.normalize(
                        RawItem(
                            title=device.title,
                            url=device.source_url,
                            raw_content=raw_content,
                            source_id=str(device.source_id) if device.source_id else None,
                            metadata=metadata,
                        )
                    )
                    if normalized:
                        before_full = device.full_description or ""
                        if not _normalized_description_is_better(device, normalized):
                            normalized.pop("full_description", None)
                        if apply:
                            changed.extend(_patch_device_from_normalized(device, normalized))
                            after_full = device.full_description or ""
                        else:
                            after_full = normalized.get("full_description") or before_full
                        if before_full != after_full:
                            stats.restructured += 1
                            if len(previews["restructured"]) < 8:
                                previews["restructured"].append(
                                    {
                                        "title": device.title,
                                        "before": before_full[:120],
                                        "after": after_full[:180],
                                    }
                                )

                if _is_private_investor(device, source) and looks_english_text(device.full_description or ""):
                    localized = localize_investment_text(device.full_description or device.source_raw or "")
                    if localized and localized != device.full_description:
                        if apply:
                            device.full_description = localized
                            device.language = "fr"
                            changed.extend(["full_description", "language"])
                        stats.translated += 1

                if apply:
                    reclass_changes = _reclassify_device(device, source)
                    if reclass_changes:
                        changed.extend(reclass_changes)
                        stats.reclassified += 1
                else:
                    original_status = device.status
                    original_type = device.device_type
                    text_blob = sanitize_text(
                        " ".join(
                            value or ""
                            for value in (
                                device.title,
                                device.short_description,
                                device.full_description,
                                device.source_raw,
                                device.recurrence_notes,
                            )
                        )
                    )
                    profile = get_source_profile(_source_to_dict(source))
                    would_reclassify = (
                        (profile and profile.source_kind == "institutional_project" and original_type != "institutional_project")
                        or (
                            original_status == "open"
                            and not device.close_date
                            and (
                                has_recurrence_evidence(text_blob)
                                or (profile and profile.default_status_without_close_date == "recurring")
                                or True
                            )
                        )
                    )
                    if would_reclassify:
                        stats.reclassified += 1

                if not _has_business_content(device) and device.validation_status != "rejected":
                    if device.validation_status != "pending_review":
                        if apply:
                            device.validation_status = "pending_review"
                            changed.append("validation_status")
                        stats.pending_review += 1
                    if apply:
                        tags = set(device.tags or [])
                        tags.add("quality:insufficient_business_content")
                        device.tags = sorted(tags)
                        changed.append("tags")

                if apply:
                    quality_changes = _apply_quality_decision(device)
                    if quality_changes:
                        changed.extend(quality_changes)

                if apply and changed:
                    device_dict = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                    device.completeness_score = compute_completeness(device_dict)

        inactive_source_query = select(Source).where(Source.is_active.is_(False), Source.last_success_at.is_(None))
        if source_name:
            inactive_source_query = inactive_source_query.where(Source.name == source_name)
        if source_contains:
            needle = f"%{source_contains}%"
            inactive_source_query = inactive_source_query.where(
                Source.name.ilike(needle) | Source.organism.ilike(needle) | Source.url.ilike(needle)
            )
        inactive_sources = (await db.execute(inactive_source_query)).scalars().all()
        for source in inactive_sources:
            device_count = (
                await db.execute(select(Device.id).where(Device.source_id == source.id).limit(1))
            ).scalar_one_or_none()
            if device_count is None:
                stats.purged_sources += 1
                if len(previews["inactive_sources"]) < 10:
                    previews["inactive_sources"].append({"name": source.name, "url": source.url})
                if purge and apply:
                    await db.execute(sql_delete(Source).where(Source.id == source.id))

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {
        "dry_run": not apply,
        "purge_enabled": purge,
        "source_name": source_name,
        "source_contains": source_contains,
        "limit": limit,
        "stats": stats.as_dict(),
        "previews": dict(previews),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie et reclasse le catalogue existant.")
    parser.add_argument("--apply", action="store_true", help="Applique les modifications. Sans ce flag: dry-run.")
    parser.add_argument("--purge", action="store_true", help="Supprime vraiment les candidats de purge avec --apply.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source-name", default=None)
    parser.add_argument("--source-contains", default=None)
    args = parser.parse_args()

    result = asyncio.run(
        cleanup_catalog(
            apply=args.apply,
            limit=args.limit,
            source_name=args.source_name,
            source_contains=args.source_contains,
            purge=args.purge,
        )
    )
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
