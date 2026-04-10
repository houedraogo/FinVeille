import math
import re
from datetime import date, timedelta, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_, update, delete as sql_delete, text, bindparam, String as SA_String
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.device_history import DeviceHistory
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceSearchParams
from app.utils.text_utils import normalize_title, generate_slug, compute_completeness, extract_keywords
from app.utils.hash_utils import compute_content_hash, compute_fingerprint


class DeviceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _visible_quality_filter():
        short_len = func.length(func.coalesce(Device.short_description, ""))
        full_len = func.length(func.coalesce(Device.full_description, ""))
        eligibility_len = func.length(func.coalesce(Device.eligibility_criteria, ""))

        # Masque les fiches quasi vides sans contenu enrichi exploitable.
        return or_(
            full_len >= 80,
            eligibility_len >= 40,
            short_len >= 140,
        )

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    async def get_by_id(self, device_id: UUID) -> Optional[Device]:
        result = await self.db.execute(select(Device).where(Device.id == device_id))
        return result.scalar_one_or_none()

    def _build_filter_query(self, params: DeviceSearchParams):
        """
        Construit la requête SQLAlchemy avec tous les filtres actifs,
        sans pagination ni tri. Réutilisée par search() et stream_for_export().
        """
        query = (
            select(Device)
            .where(Device.validation_status != "rejected")
            .where(self._visible_quality_filter())
        )

        if params.q:
            tsquery = func.plainto_tsquery("french", params.q)
            query = query.where(Device.search_vector.op("@@")(tsquery))

        if params.countries:
            query = query.where(Device.country.in_(params.countries))
        if params.device_types:
            query = query.where(Device.device_type.in_(params.device_types))
        if params.sectors:
            query = query.where(Device.sectors.overlap(params.sectors))
        if params.beneficiaries:
            query = query.where(Device.beneficiaries.overlap(params.beneficiaries))
        if params.status:
            query = query.where(Device.status.in_(params.status))
        if params.validation_status:
            query = query.where(Device.validation_status == params.validation_status)
        if params.closing_soon_days:
            deadline = date.today() + timedelta(days=params.closing_soon_days)
            query = query.where(
                and_(Device.close_date <= deadline, Device.close_date >= date.today())
            )
        if params.close_date_before:
            query = query.where(Device.close_date <= params.close_date_before)
        if params.close_date_after:
            query = query.where(Device.close_date >= params.close_date_after)
        if params.amount_min is not None:
            query = query.where(Device.amount_max >= params.amount_min)
        if params.amount_max is not None:
            query = query.where(Device.amount_min <= params.amount_max)
        if params.min_confidence is not None:
            query = query.where(Device.confidence_score >= params.min_confidence)
        if params.source_id:
            query = query.where(Device.source_id == params.source_id)

        return query

    async def search(self, params: DeviceSearchParams) -> dict:
        query = self._build_filter_query(params)

        # Comptage
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Tri
        if params.sort_by == "close_date":
            order_col = Device.close_date
        elif params.sort_by == "amount_max":
            order_col = Device.amount_max
        elif params.sort_by == "confidence":
            order_col = Device.confidence_score
        elif params.sort_by == "relevance" and params.q:
            tsq = func.plainto_tsquery("french", params.q)
            order_col = func.ts_rank(Device.search_vector, tsq)
        else:
            order_col = Device.updated_at

        if params.sort_desc:
            query = query.order_by(order_col.desc().nullslast())
        else:
            query = query.order_by(order_col.asc().nullslast())

        # Pagination
        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "pages": max(1, math.ceil(total / params.page_size)),
        }

    async def stream_for_export(self, params: DeviceSearchParams, limit: int = 5000):
        """
        Générateur async qui produit les dispositifs un par un pour l'export CSV.

        Utilise stream_scalars() + yield_per pour ne jamais charger plus de
        200 objets en mémoire à la fois, quelle que soit la taille du résultat.
        La session DB reste ouverte pendant tout le streaming grâce au
        yield-dependency get_db() de FastAPI.
        """
        query = (
            self._build_filter_query(params)
            .order_by(Device.updated_at.desc())
            .limit(limit)
            .execution_options(yield_per=200)
        )
        stream = await self.db.stream_scalars(query)
        async for device in stream:
            yield device

    async def get_history(self, device_id: UUID) -> list:
        result = await self.db.execute(
            select(DeviceHistory)
            .where(DeviceHistory.device_id == device_id)
            .order_by(DeviceHistory.changed_at.desc())
            .limit(50)
        )
        return result.scalars().all()

    async def get_stats(self) -> dict:
        today = date.today()
        week_ago = today - timedelta(days=7)
        closing_30 = today + timedelta(days=30)
        closing_7 = today + timedelta(days=7)

        stats = {}

        r = await self.db.execute(select(func.count()).where(Device.status == "open"))
        stats["total_active"] = r.scalar() or 0

        r = await self.db.execute(select(func.count()))
        stats["total"] = r.scalar() or 0

        r = await self.db.execute(
            select(func.count()).where(Device.first_seen_at >= week_ago)
        )
        stats["new_last_7_days"] = r.scalar() or 0

        r = await self.db.execute(
            select(func.count()).where(
                and_(Device.close_date <= closing_30, Device.close_date >= today, Device.status == "open")
            )
        )
        stats["closing_soon_30d"] = r.scalar() or 0

        r = await self.db.execute(
            select(func.count()).where(
                and_(Device.close_date <= closing_7, Device.close_date >= today, Device.status == "open")
            )
        )
        stats["closing_soon_7d"] = r.scalar() or 0

        r = await self.db.execute(
            select(func.count()).where(Device.validation_status == "pending_review")
        )
        stats["pending_validation"] = r.scalar() or 0

        r = await self.db.execute(
            select(Device.country, func.count().label("count"))
            .group_by(Device.country)
            .order_by(func.count().desc())
            .limit(15)
        )
        stats["by_country"] = [{"country": row[0], "count": row[1]} for row in r]

        r = await self.db.execute(
            select(Device.device_type, func.count().label("count"))
            .group_by(Device.device_type)
            .order_by(func.count().desc())
        )
        stats["by_type"] = [{"type": row[0], "count": row[1]} for row in r]

        r = await self.db.execute(
            select(Device.status, func.count().label("count"))
            .group_by(Device.status)
        )
        stats["by_status"] = [{"status": row[0], "count": row[1]} for row in r]

        r = await self.db.execute(select(func.avg(Device.confidence_score)))
        avg = r.scalar()
        stats["avg_confidence"] = round(float(avg), 1) if avg else 0

        return stats

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    async def create(self, data: DeviceCreate, created_by: str = "system") -> Device:
        device_dict = data.model_dump(exclude_none=False)
        device_dict["title_normalized"] = normalize_title(data.title)
        device_dict["slug"] = await self._unique_slug(data.title)
        device_dict["source_hash"] = compute_content_hash(
            (data.title or "") + (data.short_description or "")
        )
        device_dict["completeness_score"] = compute_completeness(device_dict)
        if not device_dict.get("keywords"):
            device_dict["keywords"] = extract_keywords(data.title)

        # Calcul confidence basique (sans accès à la source ici)
        device_dict["confidence_score"] = min(device_dict["completeness_score"], 80)
        device_dict["relevance_score"] = device_dict["completeness_score"]

        device = Device(**{k: v for k, v in device_dict.items() if hasattr(Device, k)})
        self.db.add(device)
        await self.db.flush()

        history = DeviceHistory(
            device_id=device.id,
            changed_by=created_by,
            change_type="created",
            diff={"action": "initial_import"},
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def update(self, device_id: UUID, data: DeviceUpdate, updated_by: str = "system") -> Optional[Device]:
        device = await self.get_by_id(device_id)
        if not device:
            return None

        update_dict = data.model_dump(exclude_none=True)
        old_values = {}

        for key, value in update_dict.items():
            if hasattr(device, key):
                old_values[key] = getattr(device, key)
                setattr(device, key, value)

        # Recalcul scores
        device_dict = {c.name: getattr(device, c.name) for c in Device.__table__.columns}
        device.completeness_score = compute_completeness(device_dict)
        device.updated_at = datetime.now(timezone.utc)

        history = DeviceHistory(
            device_id=device.id,
            changed_by=updated_by,
            change_type="updated",
            diff={"before": old_values, "after": update_dict},
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(device)

        # Forcer le recalcul du search_vector si des champs texte ont changé
        text_fields = {"title", "organism", "country", "short_description",
                       "full_description", "eligibility_criteria", "keywords"}
        if text_fields & set(update_dict.keys()):
            await self.refresh_search_vector(device_id)

        return device

    async def update_raw(self, device_id: UUID, fields: dict, updated_by: str = "system"):
        """Mise à jour directe depuis le pipeline de collecte."""
        device = await self.get_by_id(device_id)
        if not device:
            return

        old_hash = device.source_hash
        for key, value in fields.items():
            if hasattr(device, key) and value is not None:
                setattr(device, key, value)

        device_dict = {c.name: getattr(device, c.name) for c in Device.__table__.columns}
        device.completeness_score = compute_completeness(device_dict)
        device.last_verified_at = datetime.now(timezone.utc)

        history = DeviceHistory(
            device_id=device.id,
            changed_by=updated_by,
            change_type="updated",
            diff={"source_hash_before": old_hash, "fields_updated": list(fields.keys())},
            source_hash=fields.get("source_hash"),
        )
        self.db.add(history)
        await self.db.commit()

        # Recalcul search_vector si champs texte impactés
        text_fields = {"title", "organism", "country", "short_description",
                       "full_description", "eligibility_criteria", "keywords"}
        if text_fields & set(fields.keys()):
            await self.refresh_search_vector(device_id)

    async def validate(self, device_id: UUID, validator_id: UUID) -> Optional[Device]:
        device = await self.get_by_id(device_id)
        if not device:
            return None
        device.validation_status = "approved"
        device.validated_by = validator_id
        device.validated_at = datetime.now(timezone.utc)
        history = DeviceHistory(
            device_id=device.id,
            changed_by=str(validator_id),
            change_type="validated",
            diff={"validation_status": "approved"},
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def reject(self, device_id: UUID, validator_id: UUID) -> Optional[Device]:
        device = await self.get_by_id(device_id)
        if not device:
            return None
        device.validation_status = "rejected"
        device.validated_by = validator_id
        device.validated_at = datetime.now(timezone.utc)
        history = DeviceHistory(
            device_id=device.id,
            changed_by=str(validator_id),
            change_type="rejected",
            diff={"validation_status": "rejected"},
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def delete(self, device_id: UUID):
        device = await self.get_by_id(device_id)
        if device:
            await self.db.delete(device)
            await self.db.commit()

    @staticmethod
    def has_thin_description(
        short_description: Optional[str],
        full_description: Optional[str] = None,
        eligibility_criteria: Optional[str] = None,
        min_short_length: int = 140,
        min_sentence_count: int = 2,
    ) -> bool:
        short_text = (short_description or "").strip()
        full_text = (full_description or "").strip()
        eligibility_text = (eligibility_criteria or "").strip()

        if full_text or eligibility_text:
            return False
        if not short_text:
            return True

        normalized = re.sub(r"\s+", " ", short_text)
        sentence_count = len(
            [chunk for chunk in re.split(r"(?<=[.!?])\s+", normalized) if chunk.strip()]
        )
        return len(normalized) < min_short_length or sentence_count < min_sentence_count

    async def purge_unenrichable_devices(
        self,
        actor_id: str = "system",
        limit: int = 200,
        dry_run: bool = True,
    ) -> dict:
        query = (
            select(Device)
            .where(Device.validation_status == "pending_review")
            .order_by(Device.updated_at.asc().nullslast(), Device.created_at.asc().nullslast())
            .limit(limit)
        )
        result = await self.db.execute(query)
        devices = result.scalars().all()

        candidates = [
            device
            for device in devices
            if self.has_thin_description(
                device.short_description,
                device.full_description,
                device.eligibility_criteria,
            )
        ]

        preview = [
            {
                "id": str(device.id),
                "title": device.title,
                "source_url": device.source_url,
                "short_description": device.short_description,
            }
            for device in candidates[:25]
        ]

        if dry_run or not candidates:
            return {
                "dry_run": dry_run,
                "matched": len(candidates),
                "deleted": 0,
                "preview": preview,
            }

        deleted = 0
        for device in candidates:
            self.db.add(
                DeviceHistory(
                    device_id=device.id,
                    changed_by=actor_id,
                    change_type="deleted",
                    diff={
                        "reason": "thin_description_unenrichable",
                        "short_description": device.short_description,
                    },
                )
            )
            await self.db.flush()
            await self.db.delete(device)
            deleted += 1

        await self.db.commit()
        return {
            "dry_run": False,
            "matched": len(candidates),
            "deleted": deleted,
            "preview": preview,
        }

    # ------------------------------------------------------------------
    # Actions groupées (bulk)
    # ------------------------------------------------------------------

    async def bulk_validate(self, ids: list, validator_id: UUID) -> dict:
        """Valide N dispositifs en une seule requête UPDATE … RETURNING."""
        result = await self.db.execute(
            update(Device)
            .where(Device.id.in_(ids))
            .values(
                validation_status="approved",
                validated_by=validator_id,
                validated_at=datetime.now(timezone.utc),
            )
            .returning(Device.id)
        )
        updated_ids = result.scalars().all()
        for did in updated_ids:
            self.db.add(DeviceHistory(
                device_id=did,
                changed_by=str(validator_id),
                change_type="validated",
                diff={"validation_status": "approved", "bulk": True},
            ))
        await self.db.commit()
        return {
            "action": "validate",
            "processed": len(updated_ids),
            "failed": len(ids) - len(updated_ids),
            "errors": [],
        }

    async def bulk_reject(self, ids: list, validator_id: UUID) -> dict:
        """Rejette N dispositifs en une seule requête UPDATE … RETURNING."""
        result = await self.db.execute(
            update(Device)
            .where(Device.id.in_(ids))
            .values(
                validation_status="rejected",
                validated_by=validator_id,
                validated_at=datetime.now(timezone.utc),
            )
            .returning(Device.id)
        )
        updated_ids = result.scalars().all()
        for did in updated_ids:
            self.db.add(DeviceHistory(
                device_id=did,
                changed_by=str(validator_id),
                change_type="rejected",
                diff={"validation_status": "rejected", "bulk": True},
            ))
        await self.db.commit()
        return {
            "action": "reject",
            "processed": len(updated_ids),
            "failed": len(ids) - len(updated_ids),
            "errors": [],
        }

    async def bulk_delete(self, ids: list) -> dict:
        """Supprime N dispositifs en une seule requête DELETE."""
        result = await self.db.execute(
            sql_delete(Device).where(Device.id.in_(ids))
        )
        await self.db.commit()
        processed = result.rowcount
        return {
            "action": "delete",
            "processed": processed,
            "failed": len(ids) - processed,
            "errors": [],
        }

    async def bulk_tag(self, ids: list, tags: list, actor_id: UUID) -> dict:
        """Ajoute des tags sur N dispositifs via PostgreSQL array_cat."""
        tags_array = list(set(tags))  # déduplique les tags en entrée
        # asyncpg interprète ":param::cast" comme deux tokens distincts, ce qui
        # lève une SyntaxError.  On utilise bindparam() avec des types explicites
        # pour éviter toute ambiguïté avec la syntaxe :: de PostgreSQL.
        stmt = text("""
            UPDATE devices
            SET tags = ARRAY(
                SELECT DISTINCT unnest(coalesce(tags, '{}') || :new_tags)
                ORDER BY 1
            ),
            updated_at = now()
            WHERE id = ANY(:ids)
        """).bindparams(
            bindparam("new_tags", type_=PG_ARRAY(SA_String)),
            bindparam("ids",      type_=PG_ARRAY(PG_UUID(as_uuid=False))),
        )
        await self.db.execute(stmt, {"new_tags": tags_array, "ids": [str(i) for i in ids]})
        await self.db.commit()
        return {
            "action": "tag",
            "processed": len(ids),
            "failed": 0,
            "errors": [],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def refresh_search_vector(self, device_id: UUID) -> None:
        """
        Recalcule le search_vector PostgreSQL pour un dispositif donné.
        Utile après une mise à jour manuelle ou un import en masse.
        Le trigger DB s'en charge automatiquement sur INSERT/UPDATE,
        mais cette méthode permet un recalcul explicite si nécessaire.
        """
        await self.db.execute(
            text("""
                UPDATE devices
                SET search_vector =
                    setweight(to_tsvector('french', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('french', coalesce(organism, '')), 'B') ||
                    setweight(to_tsvector('french', coalesce(country, '')), 'B') ||
                    setweight(to_tsvector('french', coalesce(short_description, '')), 'C') ||
                    setweight(to_tsvector('french', coalesce(array_to_string(keywords, ' '), '')), 'C') ||
                    setweight(to_tsvector('french', coalesce(left(full_description, 3000), '')), 'D') ||
                    setweight(to_tsvector('french', coalesce(left(eligibility_criteria, 2000), '')), 'D')
                WHERE id = :device_id
            """),
            {"device_id": str(device_id)},
        )
        await self.db.commit()

    async def _unique_slug(self, title: str) -> str:
        base = generate_slug(title)
        slug = base
        counter = 1
        while True:
            r = await self.db.execute(select(Device.id).where(Device.slug == slug).limit(1))
            if not r.scalar():
                return slug
            slug = f"{base}-{counter}"
            counter += 1
