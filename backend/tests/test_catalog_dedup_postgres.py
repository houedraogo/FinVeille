"""Dédoublonnage à l'ingestion, quarantaine, fiches archivées et suspension IA (PostgreSQL jetable)."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.collector.deduplicator import Deduplicator
from app.collector.pipeline import CollectionPipeline
from app.models.catalog_cleanup import DeviceRejection, DuplicateCandidate
from app.models.device import Device
from app.models.source import Source
from app.services.catalog_guard import is_quarantined, quarantine
from pg_support import make_device, pg_session_factory, requires_pg  # noqa: F401

pytestmark = requires_pg

GENERIC = "DGE / aides-entreprises.fr"


async def _source(db, name="Source test", url="https://exemple.fr"):
    source = Source(
        id=uuid4(), name=name, organism="Org", country="France", source_type="portail_officiel",
        level=2, url=url, collection_mode="api", reliability=3, category="public", is_active=True,
    )
    db.add(source)
    await db.flush()
    return source


def _incoming(source, **overrides):
    data = dict(
        title="Aide test", organism="Org test", country="France", device_type="subvention",
        source_url="https://exemple.fr/aide-test", source_id=source.id, source_hash="h-" + uuid4().hex,
    )
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_same_page_and_title_from_another_source_is_merged(pg_session_factory):
    async with pg_session_factory() as db:
        other = await _source(db, "Autre portail")
        existing = make_device(
            title="Fonds de soutien au commerce rural", source_url="https://anct.gouv.fr/commerce-rural",
            organism="ANCT", source_id=other.id,
        )
        db.add(existing)
        await db.flush()
        source = await _source(db)
        found = await Deduplicator(db).find_duplicate(_incoming(
            source, title="Fonds de soutien au commerce rural", organism=GENERIC,
            source_url="https://www.anct.gouv.fr/commerce-rural/",
        ))
        assert found is not None and found.id == existing.id


@pytest.mark.asyncio
async def test_homonymous_territorial_aids_are_never_merged(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        db.add(make_device(
            title="Aide à l'immobilier d'entreprise", organism=GENERIC, source_id=source.id,
            source_url="https://sologne-des-rivieres.fr/reglement-immo.pdf",
            title_normalized="aide a l'immobilier d'entreprise",
        ))
        await db.flush()
        dedup = Deduplicator(db)
        found = await dedup.find_duplicate(_incoming(
            source, title="Aide à l'immobilier d'entreprise", organism=GENERIC,
            source_url="https://www.grandreims.fr/reimsbusiness/services",
        ))
        assert found is None
        assert dedup.last_candidates == []  # homonyme : ni fusion ni alerte


@pytest.mark.asyncio
async def test_probable_duplicate_is_reported_but_never_merged(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        existing = make_device(
            title="Prêt d'honneur création", organism="Initiative France", source_id=source.id,
            source_url="https://initiative-france.fr/pret-a", title_normalized="pret d'honneur creation",
        )
        db.add(existing)
        await db.flush()
        other_source = await _source(db, "Second portail")
        dedup = Deduplicator(db)
        found = await dedup.find_duplicate(_incoming(
            other_source, title="Prêt d'honneur création", organism="Initiative France",
            source_url="https://initiative-france.fr/pret-b",
        ))
        assert found is None
        assert [candidate.id for candidate, _a in dedup.last_candidates] == [existing.id]


@pytest.mark.asyncio
async def test_recollected_item_with_changed_url_in_same_source_is_the_same_item(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        existing = make_device(
            title="Fonds régional vidéaste", organism="Pictanovo", source_id=source.id,
            source_url="https://pictanovo.com/ancienne-page", title_normalized="fonds regional videaste",
        )
        db.add(existing)
        await db.flush()
        found = await Deduplicator(db).find_duplicate(_incoming(
            source, title="Fonds régional vidéaste", organism="Pictanovo", source_url="https://pictanovo.com/nouvelle-page",
        ))
        assert found is not None and found.id == existing.id


@pytest.mark.asyncio
async def test_listing_page_shared_by_many_titles_is_not_a_duplicate_proof(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        listing = "https://opendata.afd.fr/explore/dataset/les-projets-de-l-afd"
        for i in range(4):
            db.add(make_device(
                title=f"Projet distinct numéro {i}", organism="AFD", source_id=source.id, source_url=listing,
                title_normalized=f"projet distinct numero {i}",
            ))
        await db.flush()
        found = await Deduplicator(db).find_duplicate(_incoming(
            source, title="Projet totalement nouveau", organism="AFD", source_url=listing,
        ))
        assert found is None


@pytest.mark.asyncio
async def test_structural_quarantine_always_applies_and_is_idempotent(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        url = "https://projects.worldbank.org/en/projects-operations/project-detail/P123456"
        first = await quarantine(
            db, source_id=source.id, source_url=url, title="Projet", content_hash="a",
            rule="scope_worldbank_project_record", reason="projet institutionnel",
        )
        second = await quarantine(
            db, source_id=source.id, source_url=url, title="Projet", content_hash="b",
            rule="scope_worldbank_project_record", reason="projet institutionnel",
        )
        assert first.id == second.id
        assert (await db.execute(select(DeviceRejection))).scalars().all().__len__() == 1
        # Règle structurelle : s'applique même si le contenu a changé.
        assert await is_quarantined(db, source_id=source.id, source_url=url, content_hash="zzz") is not None


@pytest.mark.asyncio
async def test_manual_quarantine_is_lifted_when_source_content_changes(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        url = "https://exemple.fr/fiche-refusee"
        await quarantine(db, source_id=source.id, source_url=url, title="Fiche", content_hash="v1", rule="manual_review", reason="refus")
        assert await is_quarantined(db, source_id=source.id, source_url=url, content_hash="v1") is not None
        assert await is_quarantined(db, source_id=source.id, source_url=url, content_hash="v2") is None


# --- pipeline -------------------------------------------------------------

def _pipeline(db, source):
    pipeline = CollectionPipeline(db, {"id": source.id, "name": source.name, "level": 2, "url": source.url})
    return pipeline


def _fake_normalizer(pipeline, payload):
    pipeline.normalizer = SimpleNamespace(normalize=lambda _raw: dict(payload))


def _payload(source, **overrides):
    data = dict(
        title="Subvention pour les PME innovantes du numérique", organism="Région Test", country="France",
        device_type="subvention", source_url="https://region-test.fr/aides/pme-numerique", source_id=source.id,
        short_description="Aide financière pour les PME innovantes du numérique avec un budget dédié et un dépôt en ligne.",
        full_description="## Présentation\nSubvention de la région pour les PME du numérique.\n\n## Montant\nJusqu'à 50 000 euros.",
        eligibility_criteria="PME de la région.", amount_max=50000, currency="EUR", status="open",
        beneficiaries=["pme"], sectors=["numerique"], language="fr", tags=[],
    )
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_worldbank_project_record_is_quarantined_once_and_never_created(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db, "Banque Mondiale - projets Kenya", "https://search.worldbank.org/api")
        pipeline = _pipeline(db, source)
        payload = _payload(
            source, title="Kenya Water Supply Project", organism="Banque mondiale",
            source_url="https://projects.worldbank.org/en/projects-operations/project-detail/P111",
        )
        _fake_normalizer(pipeline, payload)
        assert await pipeline._process_item(object()) == "skipped"
        assert await pipeline._process_item(object()) == "skipped"
        assert (await db.execute(select(Device))).scalars().all() == []
        rejections = (await db.execute(select(DeviceRejection))).scalars().all()
        assert len(rejections) == 1 and rejections[0].rule == "scope_worldbank_project_record"


@pytest.mark.asyncio
async def test_real_worldbank_call_page_is_not_excluded(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db, "Banque Mondiale - appels", "https://www.worldbank.org")
        pipeline = _pipeline(db, source)
        _fake_normalizer(pipeline, _payload(
            source, title="Appel à projets pour les PME africaines", organism="Banque mondiale",
            source_url="https://www.worldbank.org/fr/programs/appels-a-projets/pme-afrique",
        ))
        assert await pipeline._process_item(object()) == "new"
        assert len((await db.execute(select(Device))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_archived_device_is_not_reactivated_or_modified_by_collection(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        archived = make_device(
            title="Subvention pour les PME innovantes du numérique", organism="Région Test",
            source_url="https://region-test.fr/aides/pme-numerique", source_id=source.id,
            validation_status="archived", ai_rewrite_status="on_hold", status="expired",
            title_normalized="subvention pour les pme innovantes du numerique",
        )
        db.add(archived)
        await db.flush()
        pipeline = _pipeline(db, source)
        _fake_normalizer(pipeline, _payload(source))
        assert await pipeline._process_item(object()) == "skipped"
        await db.refresh(archived)
        assert archived.validation_status == "archived" and archived.status == "expired"
        assert len((await db.execute(select(Device))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_new_device_that_is_not_publishable_does_not_enter_the_ai_queue(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db, "Global South Opportunities - Funding", "https://globalsouthopportunities.com/feed")
        pipeline = _pipeline(db, source)
        _fake_normalizer(pipeline, _payload(
            source, title="Opportunite - Business Plan Competition 2026", organism="Global South",
            source_url="https://globalsouthopportunities.com/business-plan-2026", language="en",
        ))
        assert await pipeline._process_item(object()) == "new"
        device = (await db.execute(select(Device))).scalars().one()
        assert device.validation_status != "auto_published"
        assert device.ai_rewrite_status == "on_hold"


@pytest.mark.asyncio
async def test_procurement_style_title_is_created_but_held_for_review_without_ai(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        pipeline = _pipeline(db, source)
        _fake_normalizer(pipeline, _payload(
            source, title="Être accompagné dans la définition d'un projet communal",
            source_url="https://departement.fr/ingenierie/accompagnement-projet",
        ))
        assert await pipeline._process_item(object()) == "new"
        device = (await db.execute(select(Device))).scalars().one()
        assert device.ai_rewrite_status == "on_hold"


@pytest.mark.asyncio
async def test_probable_duplicate_creates_the_device_and_a_review_candidate(pg_session_factory):
    async with pg_session_factory() as db:
        source = await _source(db)
        existing = make_device(
            title="Subvention pour les PME innovantes du numérique", organism="Région Test", source_id=source.id,
            source_url="https://region-test.fr/aides/version-a",
            title_normalized="subvention pour les pme innovantes du numerique",
        )
        db.add(existing)
        await db.flush()
        pipeline = _pipeline(db, await _source(db, "Second portail", "https://autre.fr"))
        _fake_normalizer(pipeline, _payload(pipeline.source and SimpleNamespace(id=pipeline.source["id"])))
        assert await pipeline._process_item(object()) == "new"
        assert len((await db.execute(select(Device))).scalars().all()) == 2
        candidates = (await db.execute(select(DuplicateCandidate))).scalars().all()
        assert len(candidates) == 1 and candidates[0].status == "open" and candidates[0].tier == "probable"
