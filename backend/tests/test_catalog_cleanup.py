"""Moteur de nettoyage réversible : classification pure + archivage / restauration (PostgreSQL jetable)."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.models.catalog_cleanup import DeviceArchiveLog
from app.models.device import Device
from app.models.source import Source
from app.models.user import User
from app.models.workspace import FavoriteDevice
from app.services import catalog_cleanup as cleanup
from app.services.catalog_cleanup import (
    BATCH_A, BATCH_B, BATCH_C, BATCH_F, BATCH_G, BATCH_H, BATCH_Z, PlanMismatch, build_plan,
)
from app.services.catalog_quality import evaluate_unrated
from pg_support import make_device, pg_session_factory, requires_pg  # noqa: F401

GENERIC = "DGE / aides-entreprises.fr"
WB_URL = "https://projects.worldbank.org/en/projects-operations/project-detail/P100"


def row(**overrides):
    base = dict(
        id=uuid4(), title="Aide", organism="Org", country="France", source_url="https://exemple.fr/a",
        source_id=uuid4(), validation_status="auto_published", status="open", is_recurring=False,
        user_quality_decision="publish", ai_rewrite_status="pending", completeness_score=60,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc), source_name="Portail",
    )
    base.update(overrides)
    return base


# --- classification pure ------------------------------------------------------

def test_every_device_lands_in_exactly_one_batch():
    rows = [
        row(source_url=WB_URL, source_name="Banque Mondiale - projets Kenya", title="Projet Kenya"),
        row(validation_status="rejected", title="Rejetée"),
        row(status="expired", title="Expirée"),
        row(validation_status="pending_review", title="En revue"),
        row(validation_status="admin_only", user_quality_decision="admin_only", title="Admin"),
        row(title="Normale"),
    ]
    plan = build_plan(rows)
    placed = [i for ids in plan.batches.values() for i in ids]
    assert len(placed) == len(set(placed)) == len(rows)
    assert plan.counts() == {BATCH_A: 1, BATCH_B: 1, BATCH_F: 1, BATCH_G: 1, BATCH_H: 1, BATCH_Z: 1}


def test_recurring_expired_device_is_kept_out_of_the_expired_batch():
    plan = build_plan([row(status="expired", is_recurring=True), row(status="recurring")])
    assert BATCH_B not in plan.batches


def test_worldbank_call_page_is_not_in_the_institutional_batch():
    plan = build_plan([row(source_url="https://www.worldbank.org/fr/programs/appels-a-projets/pme", source_name="Banque Mondiale - projets Mali")])
    assert BATCH_A not in plan.batches


def test_certain_duplicates_keep_the_public_complete_oldest_and_never_homonyms():
    keeper = row(title="Fonds commerce rural", organism="ANCT", source_url="https://anct.gouv.fr/cr", completeness_score=80)
    twin = row(title="Fonds commerce rural", organism=GENERIC, source_url="https://www.anct.gouv.fr/cr/", completeness_score=40)
    homonym_a = row(title="Aide immobilier d'entreprise", organism=GENERIC, source_url="https://a.fr/reglement.pdf")
    homonym_b = row(title="Aide immobilier d'entreprise", organism=GENERIC, source_url="https://b.fr/immo")
    plan = build_plan([keeper, twin, homonym_a, homonym_b])
    assert plan.ids(BATCH_C) == [twin["id"]]
    assert plan.merged_into[twin["id"]] == keeper["id"]
    assert homonym_a["id"] not in plan.merged_into and homonym_b["id"] not in plan.merged_into


def test_externally_referenced_duplicate_is_protected_and_preferred_as_keeper():
    plain = row(title="Fonds commerce rural", organism="ANCT", source_url="https://anct.gouv.fr/cr", completeness_score=90)
    referenced = row(title="Fonds commerce rural", organism=GENERIC, source_url="https://www.anct.gouv.fr/cr/", completeness_score=20)
    plan = build_plan([plain, referenced], protected_ids=[str(referenced["id"])])
    # La fiche utilisée par les dossiers clients devient la fiche conservée, malgré une complétude plus faible.
    assert plan.ids(BATCH_C) == [plain["id"]]
    assert plan.merged_into[plain["id"]] == referenced["id"]
    assert cleanup.BATCH_P not in plan.batches


def test_two_externally_referenced_twins_are_both_kept_and_reported_in_batch_p():
    a = row(title="Fonds commerce rural", organism="ANCT", source_url="https://anct.gouv.fr/cr", completeness_score=90)
    b = row(title="Fonds commerce rural", organism=GENERIC, source_url="https://www.anct.gouv.fr/cr/", completeness_score=20)
    plan = build_plan([a, b], protected_ids=[str(a["id"]), str(b["id"])])
    assert BATCH_C not in plan.batches
    assert len(plan.ids(cleanup.BATCH_P)) == 1
    assert cleanup.BATCH_P not in cleanup.ARCHIVABLE_BATCHES


def test_already_archived_rows_are_ignored_and_fingerprint_is_stable_and_sensitive():
    archived = row(validation_status="archived")
    a, b = row(status="expired"), row(status="expired")
    plan = build_plan([archived, a, b])
    assert archived["id"] not in [i for ids in plan.batches.values() for i in ids]
    again = build_plan([b, a])
    assert plan.fingerprint(BATCH_B) == again.fingerprint(BATCH_B)
    assert plan.fingerprint(BATCH_B) != build_plan([a]).fingerprint(BATCH_B)


# --- intégration PostgreSQL ---------------------------------------------------------

pg = requires_pg


async def _setup(db):
    source = Source(id=uuid4(), name="Banque Mondiale - projets Kenya", organism="BM", country="Kenya", source_type="portail_officiel",
                    level=2, url="https://worldbank.org", collection_mode="api", reliability=3, category="public", is_active=True)
    db.add(source)
    await db.flush()
    wb = make_device(title="Kenya Water Project", source_id=source.id, source_url=WB_URL, validation_status="admin_only",
                     status="standby", user_quality_decision="admin_only", ai_rewrite_status="pending", tags=["source:wb"])
    expired = make_device(title="Appel terminé 2024", status="expired", ai_rewrite_status="pending", tags=["a", "b"])
    keep = make_device(title="Aide vivante en cours", status="open")
    db.add_all([wb, expired, keep])
    await db.commit()
    return wb, expired, keep


@pg
@pytest.mark.asyncio
async def test_archive_is_logged_reversible_and_never_deletes(pg_session_factory):
    async with pg_session_factory() as db:
        wb, expired, keep = await _setup(db)
        plan = await cleanup.plan_catalog(db)
        result = await cleanup.archive_batch(db, plan, BATCH_A, run_id="run-a", expected_hash=plan.fingerprint(BATCH_A), dry_run=False)
        assert result.archived == 1 and result.ai_held == 1
        await db.refresh(wb)
        assert wb.validation_status == "archived" and wb.ai_rewrite_status == "on_hold"
        assert any(tag.startswith("archive:A_") for tag in wb.tags)
        assert (await db.execute(text("SELECT count(*) FROM devices"))).scalar() == 3  # rien n'est supprimé
        log = (await db.execute(select(DeviceArchiveLog))).scalars().one()
        assert (log.previous_validation_status, log.previous_status, log.previous_ai_rewrite_status) == ("admin_only", "standby", "pending")

        stats = await cleanup.restore(db, run_id="run-a", dry_run=False)
        assert stats["restored"] == 1
        await db.refresh(wb)
        assert (wb.validation_status, wb.status, wb.user_quality_decision, wb.ai_rewrite_status) == ("admin_only", "standby", "admin_only", "pending")
        assert wb.tags == ["source:wb"]
        # restaurer deux fois ne refait rien
        assert (await cleanup.restore(db, run_id="run-a", dry_run=False))["entries"] == 0


@pg
@pytest.mark.asyncio
async def test_dry_run_changes_nothing_and_wrong_hash_aborts(pg_session_factory):
    async with pg_session_factory() as db:
        wb, _expired, _keep = await _setup(db)
        plan = await cleanup.plan_catalog(db)
        dry = await cleanup.archive_batch(db, plan, BATCH_A, run_id="run-x", expected_hash=plan.fingerprint(BATCH_A), dry_run=True)
        assert dry.planned == 1 and dry.archived == 0
        await db.refresh(wb)
        assert wb.validation_status == "admin_only"
        with pytest.raises(PlanMismatch):
            await cleanup.archive_batch(db, plan, BATCH_A, run_id="run-y", expected_hash="deadbeefdeadbeef", dry_run=False)
        with pytest.raises(PlanMismatch):
            await cleanup.archive_batch(db, plan, BATCH_A, run_id="run-y", expected_hash=None, dry_run=False)
        assert (await db.execute(select(DeviceArchiveLog))).scalars().all() == []


@pg
@pytest.mark.asyncio
async def test_an_archived_device_cannot_be_reactivated_by_a_stray_script(pg_session_factory):
    from app.models.archive_guard import ArchivedDeviceError

    async with pg_session_factory() as db:
        wb, _expired, _keep = await _setup(db)
        plan = await cleanup.plan_catalog(db)
        await cleanup.archive_batch(db, plan, BATCH_A, run_id="run-guard", expected_hash=plan.fingerprint(BATCH_A), dry_run=False)
        await db.refresh(wb)
        with pytest.raises(ArchivedDeviceError):
            wb.validation_status = "auto_published"
        wb.validation_status = "archived"  # réaffecter la même valeur reste permis
        await db.rollback()


@pg
@pytest.mark.asyncio
async def test_non_archivable_batches_are_refused(pg_session_factory):
    async with pg_session_factory() as db:
        await _setup(db)
        plan = await cleanup.plan_catalog(db)
        for batch in (BATCH_F, BATCH_H, BATCH_G, BATCH_Z):
            with pytest.raises(ValueError):
                await cleanup.archive_batch(db, plan, batch, run_id="r", expected_hash=plan.fingerprint(batch), dry_run=False)


@pg
@pytest.mark.asyncio
async def test_archiving_a_batch_twice_in_the_same_run_skips_already_archived(pg_session_factory):
    async with pg_session_factory() as db:
        await _setup(db)
        plan = await cleanup.plan_catalog(db)
        await cleanup.archive_batch(db, plan, BATCH_B, run_id="run-b", expected_hash=plan.fingerprint(BATCH_B), dry_run=False)
        plan2 = await cleanup.plan_catalog(db)  # l'archivée n'apparaît plus
        assert BATCH_B not in plan2.batches


@pg
@pytest.mark.asyncio
async def test_duplicate_archive_moves_user_references_and_restore_gives_them_back(pg_session_factory):
    async with pg_session_factory() as db:
        keeper = make_device(title="Fonds commerce rural", organism="ANCT", source_url="https://anct.gouv.fr/cr", completeness_score=80)
        twin = make_device(title="Fonds commerce rural", organism=GENERIC, source_url="https://www.anct.gouv.fr/cr/", completeness_score=30)
        user = User(id=uuid4(), email="u@test.fr", password_hash="x", full_name="U", role="reader", is_active=True)
        db.add_all([keeper, twin, user])
        await db.flush()
        db.add(FavoriteDevice(user_id=user.id, device_id=twin.id))
        await db.commit()
        keeper_id, twin_id = keeper.id, twin.id
        plan = await cleanup.plan_catalog(db)
        assert plan.ids(BATCH_C) == [twin_id]
        result = await cleanup.archive_batch(db, plan, BATCH_C, run_id="run-c", expected_hash=plan.fingerprint(BATCH_C), dry_run=False)
        assert result.archived == 1 and result.refs_moved == 1
        db.expire_all()  # les UPDATE SQL directs ne rafraîchissent pas l'identity map
        favs = (await db.execute(select(FavoriteDevice))).scalars().all()
        assert [f.device_id for f in favs] == [keeper_id]
        await cleanup.restore(db, run_id="run-c", dry_run=False)
        db.expire_all()
        favs = (await db.execute(select(FavoriteDevice))).scalars().all()
        assert [f.device_id for f in favs] == [twin_id]


@pg
@pytest.mark.asyncio
async def test_ai_hold_suspends_pending_rewrites_of_review_and_archive_batches_only(pg_session_factory):
    async with pg_session_factory() as db:
        wb, expired, keep = await _setup(db)
        keep.ai_rewrite_status = "pending"
        await db.commit()
        plan = await cleanup.plan_catalog(db)
        dry = await cleanup.hold_pending_ai(db, plan, run_id="ai-1", dry_run=True)
        assert dry.planned == 2
        await db.refresh(wb)
        assert wb.ai_rewrite_status == "pending"
        done = await cleanup.hold_pending_ai(db, plan, run_id="ai-1", dry_run=False)
        assert done.ai_held == 2
        for device in (wb, expired, keep):
            await db.refresh(device)
        assert (wb.ai_rewrite_status, expired.ai_rewrite_status, keep.ai_rewrite_status) == ("on_hold", "on_hold", "pending")
        assert wb.validation_status == "admin_only"  # seul le statut IA change
        await cleanup.restore(db, run_id="ai-1", dry_run=False)
        await db.refresh(wb)
        assert wb.ai_rewrite_status == "pending"


@pg
@pytest.mark.asyncio
async def test_quality_evaluation_is_report_only_unless_applied_and_never_changes_validation(pg_session_factory):
    async with pg_session_factory() as db:
        device = make_device(
            title="Aide complète pour les PME innovantes", user_quality_decision=None, status="open",
            short_description="Aide financière pour les PME innovantes avec dépôt de dossier en ligne et accompagnement.",
            full_description="## Présentation\nSubvention régionale pour les PME du numérique avec budget dédié.\n\n## Montant\n50 000 euros.",
            beneficiaries=["pme"],
        )
        db.add(device)
        await db.commit()
        report = await evaluate_unrated(db, limit=10, apply=False)
        assert report["evaluated"] == 1 and report["applied"] is False
        await db.refresh(device)
        assert device.user_quality_decision is None
        applied = await evaluate_unrated(db, limit=10, apply=True)
        await db.refresh(device)
        assert applied["applied"] is True and device.user_quality_decision is not None
        assert device.validation_status == "auto_published"
