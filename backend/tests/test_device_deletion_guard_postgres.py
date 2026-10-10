"""Fusion, purge et suppression : jamais de suppression physique d'une fiche archivée ou journalisée (PostgreSQL jetable).

Contexte : la migration b7d3a91c5e24 a ajouté ``device_archive_log`` et ``device_duplicate_candidates`` sans mettre à
jour les listes de relations codées en dur ; les fusions/purges administratives échouaient (fermées). Ces tests figent
le comportement voulu : les 2 tables sont connues, le journal de restauration n'est JAMAIS cascadé, et un schéma qui
gagnerait une relation inconnue continue de faire échouer l'opération au lieu de cascader en silence.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.archive_guard import DeviceDeletionForbidden, allow_journaled_delete
from app.models.catalog_cleanup import ARCHIVED_STATUS, DeviceArchiveLog, DuplicateCandidate
from app.models.device import Device
from app.services.dedup_service import DedupService
from app.services.device_deletion_guard import (
    DEVICE_REFERENCE_TABLES, REASON_ARCHIVED, REASON_HAS_ARCHIVE_LOG, REASON_MERGE_TARGET, find_non_deletable,
)
from app.services.device_service import DeviceService
from pg_support import make_device, pg_session_factory, requires_pg  # noqa: F401

pytestmark = requires_pg


def log_row(device_id, *, action="archive", run_id="RUN-T", merged_into_id=None, restored=False):
    return DeviceArchiveLog(
        run_id=run_id, batch="C_doublons_certains", device_id=device_id, action=action, merged_into_id=merged_into_id,
        previous_validation_status="auto_published", previous_status="open",
        restored_at=datetime.now(timezone.utc) if restored else None,
    )


async def _exists(factory, device_id) -> bool:
    async with factory() as db:
        return (await db.execute(select(Device.id).where(Device.id == device_id))).first() is not None


async def _add(factory, *devices):
    async with factory() as db:
        for d in devices:
            db.add(d)
        await db.commit()


# ---------------------------------------------------------------- référence unique ---

def test_reference_tables_include_the_two_phase1_tables():
    assert {"device_archive_log", "device_duplicate_candidates"} <= DEVICE_REFERENCE_TABLES
    assert len(DEVICE_REFERENCE_TABLES) == 7


# ------------------------------------------------------------------------ fusion ---

@pytest.mark.asyncio
async def test_merge_works_again_and_resolves_the_review_queue(pg_session_factory):
    keep, dup, other = make_device(title="Aide A"), make_device(title="Aide A bis"), make_device(title="Aide tierce")
    await _add(pg_session_factory, keep, dup, other)
    async with pg_session_factory() as db:
        db.add(DuplicateCandidate(device_id=dup.id, other_device_id=other.id, tier="probable", status="open"))
        db.add(DuplicateCandidate(device_id=keep.id, other_device_id=dup.id, tier="certain", status="open"))
        await db.commit()
    async with pg_session_factory() as db:
        result = await DedupService(db).merge_group(str(keep.id), [str(dup.id)])
    assert result["deleted"] == 1
    assert not await _exists(pg_session_factory, dup.id)
    async with pg_session_factory() as db:
        pairs = {(r.device_id, r.other_device_id) for r in (await db.execute(select(DuplicateCandidate))).scalars()}
    # (dup, other) a suivi la fusion ; (keep, dup) est devenue (keep, keep) et a disparu
    assert pairs == {(keep.id, other.id)}


@pytest.mark.asyncio
async def test_merge_refuses_an_archived_duplicate_and_keeps_its_journal(pg_session_factory):
    keep = make_device(title="Aide A")
    dup = make_device(title="Aide A", validation_status=ARCHIVED_STATUS)
    await _add(pg_session_factory, keep, dup)
    async with pg_session_factory() as db:
        db.add(log_row(dup.id))
        await db.commit()
    async with pg_session_factory() as db:
        with pytest.raises(DeviceDeletionForbidden):
            await DedupService(db).merge_group(str(keep.id), [str(dup.id)])
    assert await _exists(pg_session_factory, dup.id)
    async with pg_session_factory() as db:
        assert (await db.execute(select(DeviceArchiveLog).where(DeviceArchiveLog.device_id == dup.id))).first() is not None


@pytest.mark.asyncio
async def test_merge_refuses_a_duplicate_that_only_has_an_ai_hold_journal(pg_session_factory):
    keep, dup = make_device(title="Aide A"), make_device(title="Aide A")
    await _add(pg_session_factory, keep, dup)
    async with pg_session_factory() as db:
        db.add(log_row(dup.id, action="ai_hold"))
        await db.commit()
    async with pg_session_factory() as db:
        with pytest.raises(DeviceDeletionForbidden):
            await DedupService(db).merge_group(str(keep.id), [str(dup.id)])
    assert await _exists(pg_session_factory, dup.id)


@pytest.mark.asyncio
async def test_merge_refuses_an_archived_keeper(pg_session_factory):
    keep = make_device(title="Aide A", validation_status=ARCHIVED_STATUS)
    dup = make_device(title="Aide A")
    await _add(pg_session_factory, keep, dup)
    async with pg_session_factory() as db:
        with pytest.raises(DeviceDeletionForbidden):
            await DedupService(db).merge_group(str(keep.id), [str(dup.id)])
    assert await _exists(pg_session_factory, dup.id)


@pytest.mark.asyncio
async def test_auto_merge_never_pulls_an_archived_device_into_a_group(pg_session_factory):
    """Avant correction, merge_duplicates_auto chargeait TOUTES les fiches : une archivée aurait été supprimée."""
    live = make_device(title="Aide A", title_normalized="aide a", country="France")
    archived = make_device(title="Aide A", title_normalized="aide a", country="France", validation_status=ARCHIVED_STATUS)
    await _add(pg_session_factory, live, archived)
    async with pg_session_factory() as db:
        db.add(log_row(archived.id))
        await db.commit()
    async with pg_session_factory() as db:
        result = await DedupService(db).merge_duplicates_auto()
    assert result["deleted"] == 0 and result["merged_groups"] == 0
    assert await _exists(pg_session_factory, live.id) and await _exists(pg_session_factory, archived.id)


@pytest.mark.asyncio
async def test_merge_repoints_the_journal_of_a_device_archived_into_the_merged_duplicate(pg_session_factory):
    """X archivée dans D ; D fusionnée dans C : le journal de X doit pointer vers C (restauration préservée)."""
    c, d, x = make_device(title="Aide A"), make_device(title="Aide A"), make_device(title="Aide A", validation_status=ARCHIVED_STATUS)
    await _add(pg_session_factory, c, d, x)
    async with pg_session_factory() as db:
        db.add(log_row(x.id, merged_into_id=d.id))
        await db.commit()
    async with pg_session_factory() as db:
        result = await DedupService(db).merge_group(str(c.id), [str(d.id)])
    assert result["deleted"] == 1
    async with pg_session_factory() as db:
        entry = (await db.execute(select(DeviceArchiveLog).where(DeviceArchiveLog.device_id == x.id))).scalar_one()
        assert entry.merged_into_id == c.id


@pytest.mark.asyncio
async def test_a_relation_unknown_to_the_code_still_fails_closed(pg_session_factory):
    keep, dup = make_device(title="Aide A"), make_device(title="Aide A")
    await _add(pg_session_factory, keep, dup)
    async with pg_session_factory() as db:
        await db.execute(text("CREATE TABLE zz_future_ref (id uuid PRIMARY KEY, device_id uuid REFERENCES devices(id))"))
        await db.commit()
    async with pg_session_factory() as db:
        with pytest.raises(ValueError, match="non prises en charge"):
            await DedupService(db).merge_group(str(keep.id), [str(dup.id)])
    assert await _exists(pg_session_factory, dup.id)


# ------------------------------------------------------------------------ purge ---

@pytest.mark.asyncio
async def test_purge_protects_journaled_devices_and_still_purges_the_others(pg_session_factory):
    thin_journaled = make_device(title="Mince journalisée", validation_status="pending_review")
    thin_plain = make_device(title="Mince simple", validation_status="pending_review")
    await _add(pg_session_factory, thin_journaled, thin_plain)
    async with pg_session_factory() as db:
        db.add(log_row(thin_journaled.id, action="ai_hold", restored=True))
        await db.commit()
    async with pg_session_factory() as db:
        dry = await DeviceService(db).purge_unenrichable_devices(actor_id="test", dry_run=True)
    assert dry["matched"] == 2 and dry["journaled"] == 1 and dry["deleted"] == 0
    async with pg_session_factory() as db:
        done = await DeviceService(db).purge_unenrichable_devices(actor_id="test", dry_run=False)
    assert done["deleted"] == 1 and done["journaled"] == 1
    assert await _exists(pg_session_factory, thin_journaled.id)
    assert not await _exists(pg_session_factory, thin_plain.id)


# --------------------------------------------------------------- suppression directe ---

@pytest.mark.asyncio
async def test_find_non_deletable_reasons(pg_session_factory):
    archived = make_device(title="A", validation_status=ARCHIVED_STATUS)
    journaled = make_device(title="B")
    target = make_device(title="C")
    free = make_device(title="D")
    gone = make_device(title="E", validation_status=ARCHIVED_STATUS)
    await _add(pg_session_factory, archived, journaled, target, free, gone)
    async with pg_session_factory() as db:
        db.add(log_row(journaled.id, run_id="R1"))
        db.add(log_row(gone.id, run_id="R2", merged_into_id=target.id))
        await db.commit()
    async with pg_session_factory() as db:
        blocked = await find_non_deletable(db, [archived.id, journaled.id, target.id, free.id])
        assert blocked == {str(archived.id): REASON_ARCHIVED, str(journaled.id): REASON_HAS_ARCHIVE_LOG,
                           str(target.id): REASON_MERGE_TARGET}
        allowed = await find_non_deletable(db, [target.id, free.id], allow_merge_target=True)
        assert allowed == {}


@pytest.mark.asyncio
async def test_service_delete_refuses_an_archived_device(pg_session_factory):
    archived = make_device(title="Archivée", validation_status=ARCHIVED_STATUS)
    await _add(pg_session_factory, archived)
    async with pg_session_factory() as db:
        with pytest.raises(DeviceDeletionForbidden):
            await DeviceService(db).delete(archived.id)
    assert await _exists(pg_session_factory, archived.id)


@pytest.mark.asyncio
async def test_orm_hook_is_the_safety_net_for_any_other_code_path(pg_session_factory):
    journaled = make_device(title="Journalisée")
    await _add(pg_session_factory, journaled)
    async with pg_session_factory() as db:
        db.add(log_row(journaled.id))
        await db.commit()
    async with pg_session_factory() as db:
        device = (await db.execute(select(Device).where(Device.id == journaled.id))).scalar_one()
        await db.delete(device)
        with pytest.raises(DeviceDeletionForbidden):
            await db.flush()
        await db.rollback()
    assert await _exists(pg_session_factory, journaled.id)


@pytest.mark.asyncio
async def test_raw_sql_delete_is_refused_by_the_database_even_with_the_orm_guard_open(pg_session_factory):
    """Défense en profondeur : RESTRICT sur device_archive_log, indépendamment du code applicatif.

    Ne s'applique qu'une fois la migration c8e1f4a7b2d9 appliquée (étape 2 du déploiement) : tant que la clé étrangère
    est en CASCADE, la protection repose sur le code (autres tests de ce fichier)."""
    async with pg_session_factory() as db:
        rule = (await db.execute(text(
            "SELECT confdeltype FROM pg_constraint WHERE conrelid = 'device_archive_log'::regclass AND contype = 'f' "
            "AND confrelid = 'devices'::regclass AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE "
            "attrelid = 'device_archive_log'::regclass AND attname = 'device_id')]"))).scalar()
    if rule != "r":
        pytest.skip("clé étrangère device_archive_log.device_id non RESTRICT : migration c8e1f4a7b2d9 non appliquée")
    journaled = make_device(title="Journalisée")
    await _add(pg_session_factory, journaled)
    async with pg_session_factory() as db:
        db.add(log_row(journaled.id))
        await db.commit()
    async with pg_session_factory() as db:
        with pytest.raises(IntegrityError):
            await db.execute(text("DELETE FROM devices WHERE id = :i"), {"i": journaled.id})
        await db.rollback()
    # même l'ouverture explicite du garde-fou ORM ne contourne pas la base
    async with pg_session_factory() as db:
        device = (await db.execute(select(Device).where(Device.id == journaled.id))).scalar_one()
        with allow_journaled_delete():
            await db.delete(device)
            with pytest.raises(IntegrityError):
                await db.flush()
        await db.rollback()
    assert await _exists(pg_session_factory, journaled.id)
    async with pg_session_factory() as db:
        assert (await db.execute(select(DeviceArchiveLog).where(DeviceArchiveLog.device_id == journaled.id))).first() is not None


@pytest.mark.asyncio
async def test_a_plain_device_without_journal_is_still_deletable(pg_session_factory):
    plain = make_device(title="Simple")
    await _add(pg_session_factory, plain)
    async with pg_session_factory() as db:
        await DeviceService(db).delete(plain.id)
    assert not await _exists(pg_session_factory, plain.id)
