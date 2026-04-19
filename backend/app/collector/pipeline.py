import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.collector.base_connector import CollectionResult
from app.collector.deduplicator import Deduplicator
from app.collector.enricher import Enricher
from app.collector.normalizer import Normalizer
from app.config import settings
from app.models.collection_log import CollectionLog
from app.schemas.device import DeviceCreate
from app.services.device_quality import DeviceQualityGate
from app.services.device_service import DeviceService
from app.utils.hash_utils import compute_content_hash

logger = logging.getLogger(__name__)

DEVICE_CREATE_FIELDS = set(DeviceCreate.model_fields.keys())
SUPPLEMENTAL_UPDATE_FIELDS = (
    "close_date",
    "open_date",
    "amount_min",
    "amount_max",
    "source_raw",
    "source_url",
    "status",
    "country",
    "full_description",
    "eligibility_criteria",
    "funding_details",
    "validation_status",
    "tags",
)


class CollectionPipeline:
    """
    Orchestrateur Extract -> Normalize -> Deduplicate -> Enrich -> Validate -> Store
    """

    def __init__(self, db: AsyncSession, source: dict):
        self.db = db
        self.source = source
        self.source_id = str(source["id"])
        self.source_level = source.get("level", 2)
        self.normalizer = Normalizer(source)
        self.deduplicator = Deduplicator(db)
        self.enricher = Enricher()
        self.quality_gate = DeviceQualityGate()
        self.device_service = DeviceService(db)

    async def process(self, collection_result: CollectionResult) -> dict:
        stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}
        item_errors: list[str] = []

        log = CollectionLog(
            source_id=self.source_id,
            status="running",
            items_found=len(collection_result.items),
        )
        self.db.add(log)
        await self.db.flush()

        for raw_item in collection_result.items:
            try:
                outcome = await self._process_item(raw_item)
                stats[outcome] += 1
            except Exception as exc:
                logger.error(f"[Pipeline][{self.source_id}] Erreur item '{raw_item.title}': {exc}")
                stats["errors"] += 1
                if len(item_errors) < 3:
                    item_errors.append(str(exc))

        log.status = "success" if stats["errors"] == 0 else "partial"
        log.ended_at = datetime.now(timezone.utc)
        log.items_new = stats["new"]
        log.items_updated = stats["updated"]
        log.items_skipped = stats["skipped"]
        log.items_error = stats["errors"]
        if item_errors:
            log.error_message = " ; ".join(item_errors)
        await self.db.commit()

        logger.info(
            f"[Pipeline][{self.source_id}] "
            f"new={stats['new']} updated={stats['updated']} "
            f"skipped={stats['skipped']} errors={stats['errors']}"
        )
        return stats

    async def _process_item(self, raw) -> str:
        normalized = self.normalizer.normalize(raw)
        if not normalized or not normalized.get("title"):
            return "skipped"

        content_hash = compute_content_hash(
            (normalized.get("title") or "") + (normalized.get("short_description") or "")
        )
        normalized["source_hash"] = content_hash

        existing = await self.deduplicator.find_duplicate(normalized)

        if existing:
            if existing.source_hash == content_hash:
                supplemental_fields = {}
                for field in SUPPLEMENTAL_UPDATE_FIELDS:
                    new_value = normalized.get(field)
                    current_value = getattr(existing, field, None)
                    if field == "status":
                        if new_value and new_value != current_value:
                            supplemental_fields[field] = new_value
                    elif field == "source_url":
                        if new_value and new_value != current_value:
                            supplemental_fields[field] = new_value
                    elif field == "source_raw":
                        if new_value and (
                            not current_value or len(str(new_value)) > len(str(current_value)) + 200
                        ):
                            supplemental_fields[field] = new_value
                    elif field in {"full_description", "eligibility_criteria", "funding_details"}:
                        if new_value and (
                            not current_value
                            or (
                                field == "full_description"
                                and str(new_value).startswith("## ")
                                and not str(current_value).startswith("## ")
                            )
                            or len(str(new_value)) > len(str(current_value)) + 80
                        ):
                            supplemental_fields[field] = new_value
                    elif field == "validation_status":
                        if new_value and new_value != current_value:
                            supplemental_fields[field] = new_value
                    elif field == "tags":
                        if new_value:
                            merged_tags = sorted(set((current_value or []) + (new_value or [])))
                            if merged_tags != (current_value or []):
                                supplemental_fields[field] = merged_tags
                    elif field == "country":
                        if new_value and new_value != current_value:
                            supplemental_fields[field] = new_value
                    elif current_value is None and new_value is not None:
                        supplemental_fields[field] = new_value

                if supplemental_fields:
                    supplemental_fields["source_hash"] = content_hash
                    await self.device_service.update_raw(existing.id, supplemental_fields)
                    return "updated"

                from sqlalchemy import update

                await self.db.execute(
                    update(type(existing))
                    .where(type(existing).id == existing.id)
                    .values(last_verified_at=func.now())
                )
                await self.db.commit()
                return "skipped"

            update_fields = {
                key: value
                for key, value in normalized.items()
                if value is not None and key not in ("created_at", "first_seen_at", "source_id")
            }
            await self.device_service.update_raw(existing.id, update_fields)
            return "updated"

        enriched = self.enricher.enrich(normalized, source_level=self.source_level)
        quality_decision = self.quality_gate.evaluate(enriched)
        enriched["validation_status"] = quality_decision.validation_status
        enriched["quality_gate_score"] = quality_decision.score
        if quality_decision.reasons:
            enriched["tags"] = sorted(set((enriched.get("tags") or []) + [f"quality:{reason}" for reason in quality_decision.reasons]))

        create_data = {key: value for key, value in enriched.items() if key in DEVICE_CREATE_FIELDS}
        device_schema = DeviceCreate(**create_data)
        await self.device_service.create(device_schema, created_by="system")
        return "new"
