from typing import Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source
from app.models.collection_log import CollectionLog
from app.schemas.source import SourceCreate, SourceUpdate, SourceTestRequest


class SourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, country: Optional[str] = None, level: Optional[int] = None,
                      active_only: bool = False, category: Optional[str] = None) -> List[dict]:
        q = select(Source)
        if country:
            q = q.where(Source.country == country)
        if level is not None:
            q = q.where(Source.level == level)
        if active_only:
            q = q.where(Source.is_active == True)
        if category:
            q = q.where(Source.category == category)
        q = q.order_by(Source.level, Source.name)
        result = await self.db.execute(q)
        sources = result.scalars().all()
        return await self._serialize_sources_with_last_error(sources)

    async def get_by_id(self, source_id: UUID) -> Optional[dict]:
        result = await self.db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if not source:
            return None
        return (await self._serialize_sources_with_last_error([source]))[0]

    async def get_model_by_id(self, source_id: UUID) -> Optional[Source]:
        result = await self.db.execute(select(Source).where(Source.id == source_id))
        return result.scalar_one_or_none()

    def _merge_source_config(
        self,
        *,
        source_kind: str,
        collection_mode: str,
        config: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        merged = dict(config or {})
        merged["source_kind"] = source_kind

        if collection_mode == "manual" and source_kind in {"pdf_manual", "manual_import"}:
            merged.setdefault("document_type", "pdf")
            return merged

        if collection_mode != "html":
            return merged

        if source_kind in {"single_program_page", "institutional_project", "editorial_funding"}:
            merged.setdefault("list_selector", "body")
            merged.setdefault("item_title_selector", "h1")
            merged.setdefault("item_description_selector", "main, article, .content, .entry-content, .post-content, body")
            merged.setdefault("item_link_selector", "a[href='__none__']")
            merged.setdefault("detail_fetch", False)

        return merged

    def _prepare_source_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(payload)
        source_kind = prepared.pop("source_kind", None) or "listing"
        prepared["config"] = self._merge_source_config(
            source_kind=source_kind,
            collection_mode=prepared.get("collection_mode", "html"),
            config=prepared.get("config"),
        )
        return prepared

    def _read_source_kind(self, source: Source) -> str:
        config = source.config or {}
        return str(config.get("source_kind") or "listing")

    def _build_test_preview(
        self,
        *,
        source_kind: str,
        collection_mode: str,
        items_found: int,
        sample_items: list[Any],
    ) -> dict[str, Any]:
        mode_label = {
            "manual": "Source manuelle",
            "html": "Page editoriale" if source_kind in {"single_program_page", "institutional_project", "editorial_funding"} else "Collecte automatique",
        }.get(collection_mode, "Collecte automatique")

        if source_kind == "pdf_manual":
            summary = "La source servira surtout de reference documentaire ou de creation manuelle de fiche."
        elif source_kind == "manual_import":
            summary = "La source sert a rattacher des fiches importees ou gerees manuellement dans la plateforme."
        elif source_kind == "single_program_page":
            summary = "La collecte creera ou mettra a jour une fiche principale a partir d'une page unique."
        elif source_kind == "institutional_project":
            summary = "La collecte interpretera la page comme un projet institutionnel plutot qu'une liste d'appels."
        elif source_kind == "editorial_funding":
            summary = "La collecte interpretera la page comme une source editoriale et tentera d'en extraire des opportunites exploitables."
        else:
            summary = "La collecte cherchera une liste de dispositifs et generera une fiche par item detecte."

        titles = [getattr(item, "title", "") for item in sample_items if getattr(item, "title", "")]
        return {
            "badge": mode_label,
            "source_kind": source_kind,
            "headline": f"{items_found} fiche(s) pressentie(s)",
            "summary": summary,
            "examples": titles[:3],
        }

    async def create(self, data: SourceCreate) -> dict:
        source = Source(**self._prepare_source_payload(data.model_dump()))
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return (await self._serialize_sources_with_last_error([source]))[0]

    async def update(self, source_id: UUID, data: SourceUpdate) -> Optional[dict]:
        source = await self.get_model_by_id(source_id)
        if not source:
            return None
        prepared = self._prepare_source_payload({
            **{
                "name": source.name,
                "organism": source.organism,
                "country": source.country,
                "region": source.region,
                "source_type": source.source_type,
                "category": source.category,
                "level": source.level,
                "url": source.url,
                "collection_mode": source.collection_mode,
                "source_kind": self._read_source_kind(source),
                "check_frequency": source.check_frequency,
                "reliability": source.reliability,
                "is_active": source.is_active,
                "config": source.config,
                "notes": source.notes,
            },
            **data.model_dump(exclude_none=True),
        })
        for k, v in prepared.items():
            setattr(source, k, v)
        await self.db.commit()
        await self.db.refresh(source)
        return (await self._serialize_sources_with_last_error([source]))[0]

    async def delete(self, source_id: UUID):
        source = await self.get_model_by_id(source_id)
        if source:
            await self.db.delete(source)
            await self.db.commit()

    async def get_logs(self, source_id: UUID, limit: int = 20) -> List[CollectionLog]:
        result = await self.db.execute(
            select(CollectionLog)
            .where(CollectionLog.source_id == source_id)
            .order_by(CollectionLog.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_stats(self) -> dict:
        r = await self.db.execute(select(func.count()).where(Source.is_active == True))
        total_active = r.scalar() or 0

        r = await self.db.execute(
            select(Source.collection_mode, func.count().label("c"))
            .group_by(Source.collection_mode)
        )
        by_mode = [{"mode": row[0], "count": row[1]} for row in r]

        r = await self.db.execute(
            select(Source.country, func.count().label("c"))
            .group_by(Source.country)
            .order_by(func.count().desc())
        )
        by_country = [{"country": row[0], "count": row[1]} for row in r]

        r = await self.db.execute(
            select(func.count()).where(Source.consecutive_errors >= 3)
        )
        sources_in_error = r.scalar() or 0

        return {
            "total_active": total_active,
            "by_mode": by_mode,
            "by_country": by_country,
            "sources_in_error": sources_in_error,
        }

    async def _serialize_sources_with_last_error(self, sources: List[Source]) -> List[dict]:
        if not sources:
            return []

        source_ids = [source.id for source in sources]
        log_result = await self.db.execute(
            select(CollectionLog)
            .where(CollectionLog.source_id.in_(source_ids))
            .order_by(CollectionLog.source_id, CollectionLog.started_at.desc())
        )

        last_error_by_source: dict[UUID, str] = {}
        logs_by_source: dict[UUID, list[CollectionLog]] = {}
        for log in log_result.scalars().all():
            logs_by_source.setdefault(log.source_id, []).append(log)
            if log.source_id in last_error_by_source:
                continue
            message = (log.error_message or "").strip()
            if message:
                last_error_by_source[log.source_id] = message

        serialized = []
        for source in sources:
            source_logs = logs_by_source.get(source.id, [])
            health_score, health_label = self._compute_health(source, source_logs)
            payload = {
                "id": source.id,
                "name": source.name,
                "organism": source.organism,
                "country": source.country,
                "region": source.region,
                "source_type": source.source_type,
                "category": source.category,
                "level": source.level,
                "url": source.url,
                "collection_mode": source.collection_mode,
                "source_kind": self._read_source_kind(source),
                "check_frequency": source.check_frequency,
                "reliability": source.reliability,
                "is_active": source.is_active,
                "last_checked_at": source.last_checked_at,
                "last_success_at": source.last_success_at,
                "consecutive_errors": source.consecutive_errors,
                "config": source.config,
                "notes": source.notes,
                "last_error": last_error_by_source.get(source.id) or source.notes,
                "health_score": health_score,
                "health_label": health_label,
                "created_at": source.created_at,
            }
            serialized.append(payload)
        return serialized

    def _compute_health(self, source: Source, logs: List[CollectionLog]) -> tuple[int, str]:
        score = 100

        error_penalty = min((source.consecutive_errors or 0) * 18, 55)
        score -= error_penalty

        now = datetime.now(timezone.utc)
        expected_hours = {
            "hourly": 2,
            "daily": 36,
            "weekly": 24 * 10,
            "monthly": 24 * 40,
        }.get(source.check_frequency or "daily", 36)

        if source.last_success_at:
            last_success = source.last_success_at
            if last_success.tzinfo is None:
                last_success = last_success.replace(tzinfo=timezone.utc)
            hours_since_success = max((now - last_success).total_seconds() / 3600, 0)
            if hours_since_success > expected_hours:
                lateness_ratio = min(hours_since_success / expected_hours, 4)
                score -= int(min((lateness_ratio - 1) * 14, 28))
        else:
            score -= 20

        recent_cutoff = now - timedelta(days=30)
        recent_logs = []
        for log in logs:
            started_at = log.started_at
            if started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if started_at and started_at >= recent_cutoff:
                recent_logs.append(log)

        recent_volume = sum((log.items_new or 0) + (log.items_updated or 0) + (log.items_found or 0) for log in recent_logs)
        recent_successes = sum(1 for log in recent_logs if log.status in ("success", "partial"))

        if source.collection_mode != "manual":
            if recent_successes == 0:
                score -= 12
            elif recent_volume >= 25:
                score += 6
            elif recent_volume == 0:
                score -= 6

        score += max((source.reliability - 3) * 4, -8)

        if not source.is_active:
            score -= 10

        score = max(0, min(100, int(score)))

        if score >= 85:
            label = "excellent"
        elif score >= 70:
            label = "bon"
        elif score >= 50:
            label = "fragile"
        else:
            label = "critique"

        return score, label

    async def test_source(self, data: SourceTestRequest) -> dict:
        prepared = self._prepare_source_payload(data.model_dump())
        source_dict = {
            "id": "preview-source",
            "name": prepared["name"],
            "organism": prepared["organism"],
            "country": prepared["country"],
            "collection_mode": prepared["collection_mode"],
            "url": prepared["url"],
            "level": prepared["level"],
            "config": prepared.get("config") or {},
            "language": "fr",
        }

        if prepared["collection_mode"] == "manual":
            return {
                "success": True,
                "message": "Source manuelle: aucun test automatique a executer.",
                "collection_mode": prepared["collection_mode"],
                "items_found": 0,
                "sample_titles": [],
                "sample_urls": [],
                "can_activate": True,
                "preview": self._build_test_preview(
                    source_kind=str((prepared.get("config") or {}).get("source_kind") or "listing"),
                    collection_mode=prepared["collection_mode"],
                    items_found=0,
                    sample_items=[],
                ),
            }

        from app.collector.api_connector import APIConnector
        from app.collector.html_connector import HTMLConnector
        from app.collector.les_aides_connector import LesAidesConnector
        from app.collector.rss_connector import RSSConnector

        connectors = {
            "api": APIConnector,
            "html": HTMLConnector,
            "rss": RSSConnector,
            "atom": RSSConnector,
            "les_aides": LesAidesConnector,
        }

        connector_class = connectors.get(data.collection_mode)
        if not connector_class:
            return {
                "success": False,
                "message": f"Mode de collecte non supporte: {prepared['collection_mode']}",
                "collection_mode": prepared["collection_mode"],
                "items_found": 0,
                "sample_titles": [],
                "sample_urls": [],
                "can_activate": False,
            }

        connector = connector_class(source_dict)
        result = await connector.collect()

        sample_items = result.items[:5]
        message = (
            f"{len(result.items)} item(s) detecte(s)."
            if result.success
            else (result.error or "Echec du test de collecte.")
        )

        return {
            "success": result.success,
            "message": message,
            "collection_mode": data.collection_mode,
            "items_found": len(result.items),
            "sample_titles": [item.title for item in sample_items],
            "sample_urls": [item.url for item in sample_items],
            "can_activate": result.success and len(result.items) > 0,
            "preview": self._build_test_preview(
                source_kind=str((prepared.get("config") or {}).get("source_kind") or "listing"),
                collection_mode=prepared["collection_mode"],
                items_found=len(result.items),
                sample_items=sample_items,
            ),
        }
