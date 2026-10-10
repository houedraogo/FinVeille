"""Import CSV aides-entreprises : rattachement des lignes historiques, jamais de doublon (PostgreSQL jetable)."""
import csv
import io
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.data import import_aides_entreprises_csv as importer
from app.models.catalog_cleanup import DuplicateCandidate
from app.models.device import Device
from app.models.source import Source
from pg_support import make_device, pg_session_factory, requires_pg  # noqa: F401

pytestmark = requires_pg

COLUMNS = [
    "id_aid", "aid_nom", "aid_objet", "aid_conditions", "aid_montant", "aid_operations_el", "aid_benef",
    "date_fin", "natures", "profils", "id_domaine", "couverture_geo", "financeurs", "complements_sources", "status",
]
FUTURE = (datetime.now(timezone.utc) + timedelta(days=200)).strftime("%Y-%m-%d")
OBJET = (
    "Cette aide soutient les petites entreprises dans leurs investissements productifs en finançant une partie des "
    "dépenses éligibles, avec un dépôt de dossier en ligne auprès de la collectivité."
)


def csv_text(*rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, delimiter=";", quotechar='"')
    writer.writeheader()
    for row in rows:
        full = {c: "" for c in COLUMNS}
        full.update({"aid_objet": OBJET, "aid_conditions": "Entreprise de moins de 50 salariés.", "aid_montant": "Jusqu'à 20 000 euros",
                     "natures": "Subvention", "profils": "PME TPE", "id_domaine": "2", "date_fin": FUTURE, "status": "1"})
        full.update(row)
        writer.writerow(full)
    return out.getvalue()


@pytest.fixture
def use_db(pg_session_factory, monkeypatch):
    monkeypatch.setattr(importer, "AsyncSessionLocal", pg_session_factory)
    return pg_session_factory


async def _all(factory):
    async with factory() as db:
        return (await db.execute(select(Device).order_by(Device.slug))).scalars().all()


@pytest.mark.asyncio
async def test_first_import_creates_stable_slug_rows_with_quality_and_ai_status(use_db):
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "101", "aid_nom": "Aide à la modernisation des commerces", "complements_sources": "https://region-a.fr/aide-modernisation"},
        {"id_aid": "102", "aid_nom": "Prêt d'honneur pour les créateurs", "complements_sources": "https://region-b.fr/pret-honneur", "natures": "Prêt"},
    ))
    assert counts["insert"] == 2 and counts["errors"] == 0
    rows = await _all(use_db)
    assert [d.slug for d in rows] == ["fr-ae-101", "fr-ae-102"]
    for device in rows:
        assert device.user_quality_decision is not None  # plus jamais publié « jamais évalué »
        assert device.title_normalized == device.title_normalized.lower()
        assert device.ai_rewrite_status in ("pending", "on_hold")


@pytest.mark.asyncio
async def test_rerun_and_modified_rows_update_in_place_without_duplicates(use_db):
    first = csv_text({"id_aid": "101", "aid_nom": "Aide à la modernisation des commerces", "complements_sources": "https://region-a.fr/aide-modernisation"})
    await importer.main(csv_text=first)
    await importer.main(csv_text=first)
    changed = csv_text({"id_aid": "101", "aid_nom": "Aide à la modernisation des commerces", "aid_montant": "Jusqu'à 35 000 euros",
                        "complements_sources": "https://region-a.fr/aide-modernisation"})
    counts = await importer.main(csv_text=changed)
    rows = await _all(use_db)
    assert len(rows) == 1 and counts["insert"] == 0
    assert "35 000" in (rows[0].funding_details or "")


@pytest.mark.asyncio
async def test_legacy_title_slug_row_is_adopted_not_duplicated(use_db):
    """Cas de la vague du 2 octobre : l'ancienne ligne (slug titre) doit être rattachée, pas doublée."""
    title = "Aide à la modernisation des commerces"
    async with use_db() as db:
        source = await db.execute(text("SELECT 1"))
        src = Source(id=uuid4(), name=importer.SOURCE_NAME, organism=importer.SOURCE_ORGANISM, country="France",
                     source_type="portail_officiel", level=1, url=importer.CSV_URL, collection_mode="csv_import",
                     reliability=5, category="financement", is_active=True)
        db.add(src)
        await db.flush()
        legacy = make_device(
            title=title, slug="fr-ae-aide-la-modernisation-des-commerces", source_id=src.id, organism=importer.SOURCE_ORGANISM,
            source_url="https://region-a.fr/aide-modernisation", source_hash=importer.content_hash_for("101", title),
        )
        db.add(legacy)
        await db.commit()
        legacy_id = legacy.id
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "101", "aid_nom": title, "complements_sources": "https://region-a.fr/aide-modernisation"}))
    rows = await _all(use_db)
    assert len(rows) == 1 and counts["adopt"] == 1 and counts["insert"] == 0
    assert rows[0].id == legacy_id and rows[0].slug == "fr-ae-101"


@pytest.mark.asyncio
async def test_legacy_row_with_unmatched_hash_but_certain_twin_in_same_source_is_adopted(use_db):
    title = "Fonds de soutien au commerce rural"
    async with use_db() as db:
        src = Source(id=uuid4(), name=importer.SOURCE_NAME, organism=importer.SOURCE_ORGANISM, country="France",
                     source_type="portail_officiel", level=1, url=importer.CSV_URL, collection_mode="csv_import",
                     reliability=5, category="financement", is_active=True)
        db.add(src)
        await db.flush()
        db.add(make_device(title=title, slug="fr-ae-fonds-de-soutien-au-commerce-rural", source_id=src.id,
                           organism=importer.SOURCE_ORGANISM, source_url="https://anct.gouv.fr/commerce-rural",
                           source_hash="hash-ancien-format"))
        await db.commit()
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "10953", "aid_nom": title, "complements_sources": "https://www.anct.gouv.fr/commerce-rural/"}))
    assert counts["adopt"] == 1 and counts["insert"] == 0
    assert [d.slug for d in await _all(use_db)] == ["fr-ae-10953"]


@pytest.mark.asyncio
async def test_certain_twin_from_another_source_is_not_recreated(use_db):
    title = "Volontariat International en Entreprise (VIE)"
    async with use_db() as db:
        other = Source(id=uuid4(), name="Import manuel / historique", organism="Manuel", country="France",
                       source_type="autre", level=2, url="https://manuel.local", collection_mode="manual",
                       reliability=3, category="public", is_active=True)
        db.add(other)
        await db.flush()
        db.add(make_device(title=title, slug="volontariat-international-en-entreprise-vie", source_id=other.id,
                           organism="Business France", source_url="https://e-vie.businessfrance.fr/devis"))
        await db.commit()
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "777", "aid_nom": title, "complements_sources": "https://e-vie.businessfrance.fr/devis"}))
    assert counts["skip_duplicate"] == 1 and counts["insert"] == 0
    assert len(await _all(use_db)) == 1


@pytest.mark.asyncio
async def test_homonymous_aids_with_distinct_ids_and_pages_are_both_kept(use_db):
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "201", "aid_nom": "Aide à l'immobilier d'entreprise", "complements_sources": "https://sologne.fr/reglement-immo.pdf"},
        {"id_aid": "202", "aid_nom": "Aide à l'immobilier d'entreprise", "complements_sources": "https://grandreims.fr/immo-entreprise"},
    ))
    assert counts["insert"] == 2 and counts["skip_duplicate"] == 0
    assert len(await _all(use_db)) == 2


@pytest.mark.asyncio
async def test_archived_row_is_never_touched_by_the_import(use_db):
    title = "Aide à la modernisation des commerces"
    async with use_db() as db:
        src = Source(id=uuid4(), name=importer.SOURCE_NAME, organism=importer.SOURCE_ORGANISM, country="France",
                     source_type="portail_officiel", level=1, url=importer.CSV_URL, collection_mode="csv_import",
                     reliability=5, category="financement", is_active=True)
        db.add(src)
        await db.flush()
        db.add(make_device(title="Ancien titre archivé", slug="fr-ae-101", source_id=src.id, validation_status="archived",
                           status="expired", ai_rewrite_status="on_hold", source_url="https://region-a.fr/archive"))
        await db.commit()
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "101", "aid_nom": title, "complements_sources": "https://region-a.fr/aide-modernisation"}))
    rows = await _all(use_db)
    assert counts["skip_archived"] == 1 and len(rows) == 1
    assert rows[0].title == "Ancien titre archivé" and rows[0].validation_status == "archived" and rows[0].status == "expired"


@pytest.mark.asyncio
async def test_updates_follow_a_merged_duplicate_to_the_kept_device(use_db):
    """Le doublon archivé garde le slug stable : la fiche conservée doit tout de même être mise à jour."""
    from app.models.catalog_cleanup import DeviceArchiveLog

    async with use_db() as db:
        src = Source(id=uuid4(), name=importer.SOURCE_NAME, organism=importer.SOURCE_ORGANISM, country="France",
                     source_type="portail_officiel", level=1, url=importer.CSV_URL, collection_mode="csv_import",
                     reliability=5, category="financement", is_active=True)
        db.add(src)
        await db.flush()
        keeper = make_device(title="Aide à la modernisation des commerces", slug="fr-ae-aide-modernisation-ancien", source_id=src.id,
                             source_url="https://region-a.fr/aide-modernisation", funding_details="Ancien montant")
        dup = make_device(title="Aide à la modernisation des commerces", slug="fr-ae-101", source_id=src.id,
                          source_url="https://region-a.fr/aide-modernisation", validation_status="archived")
        db.add_all([keeper, dup])
        await db.flush()
        db.add(DeviceArchiveLog(run_id="r", batch="C_doublons_certains", device_id=dup.id, action="archive",
                                merged_into_id=keeper.id, previous_validation_status="auto_published"))
        await db.commit()
        keeper_id = keeper.id
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "101", "aid_nom": "Aide à la modernisation des commerces", "aid_montant": "Jusqu'à 99 000 euros",
         "complements_sources": "https://region-a.fr/aide-modernisation"}))
    assert counts["update_keeper"] == 1 and counts["insert"] == 0 and counts["skip_archived"] == 0
    rows = {d.id: d for d in await _all(use_db)}
    assert "99 000" in rows[keeper_id].funding_details
    assert len(rows) == 2 and any(d.validation_status == "archived" for d in rows.values())


@pytest.mark.asyncio
async def test_manual_qualification_status_survives_a_reimport(use_db):
    row = {"id_aid": "301", "aid_nom": "Programme régional de soutien", "complements_sources": "https://region-c.fr/programme"}
    await importer.main(csv_text=csv_text(row))
    async with use_db() as db:
        await db.execute(text("UPDATE devices SET status = 'recurring' WHERE slug = 'fr-ae-301'"))
        await db.commit()
    await importer.main(csv_text=csv_text(row))
    assert (await _all(use_db))[0].status == "recurring"


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(use_db):
    counts = await importer.main(dry_run=True, csv_text=csv_text(
        {"id_aid": "401", "aid_nom": "Aide simulée sans écriture", "complements_sources": "https://region-d.fr/simulee"}))
    assert counts["insert"] == 1
    assert await _all(use_db) == []


@pytest.mark.asyncio
async def test_probable_duplicate_is_queued_for_review_but_inserted(use_db):
    title = "Prêt d'honneur création"
    async with use_db() as db:
        other = Source(id=uuid4(), name="Autre portail", organism="X", country="France", source_type="portail_officiel",
                       level=2, url="https://autre.fr", collection_mode="api", reliability=3, category="public", is_active=True)
        db.add(other)
        await db.flush()
        db.add(make_device(title=title, slug="pret-d-honneur-creation", source_id=other.id, organism="Initiative France",
                           source_url="https://initiative-france.fr/pret-a"))
        await db.commit()
    counts = await importer.main(csv_text=csv_text(
        {"id_aid": "501", "aid_nom": title, "financeurs": "Initiative France", "complements_sources": "https://initiative-france.fr/pret-b"}))
    assert counts["insert"] == 1 and counts["candidates"] == 1
    async with use_db() as db:
        assert len((await db.execute(select(DuplicateCandidate))).scalars().all()) == 1
