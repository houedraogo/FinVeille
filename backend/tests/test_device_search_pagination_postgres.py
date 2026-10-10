"""Pagination du catalogue public : ordre total deterministe (aucun doublon, aucune fiche sautee).

Constat du 10/10/2026 : ``GET /api/v1/devices/`` renvoyait 3 179 lignes pour 2 679 identifiants distincts. Le tri ne
portait que sur la colonne choisie puis ``updated_at`` ; les fiches mises a jour en lot partagent le meme ``updated_at``,
donc l'ordre entre egalites n'etait pas defini et OFFSET/LIMIT repetait ou sautait des fiches d'une page a l'autre
(la synchro Finnovatix, qui parcourt les pages, ne voyait qu'une partie du catalogue)."""
from datetime import datetime, timezone

import pytest

from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService
from pg_support import make_device, pg_session_factory, requires_pg  # noqa: F401

pytestmark = requires_pg

N = 53
PAGE = 7


async def _all_ids(factory, **params):
    seen, page = [], 1
    while True:
        async with factory() as db:
            out = await DeviceService(db).search(DeviceSearchParams(page=page, page_size=PAGE, include_low_quality=True, include_all_statuses=True, **params))
        items = out["items"]
        if not items:
            return seen
        seen += [str(i.id if hasattr(i, "id") else i["id"]) for i in items]
        page += 1
        if page > 40:
            raise AssertionError("pagination sans fin")


@pytest.mark.asyncio
@pytest.mark.parametrize("sort", ["updated_at", "relevance", "confidence", "close_date"])
async def test_every_device_is_returned_exactly_once_when_sort_keys_tie(pg_session_factory, sort):
    same = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    async with pg_session_factory() as db:
        for i in range(N):
            # tous les criteres de tri sont identiques : seul l'identifiant departage
            db.add(make_device(title=f"Aide {i}", title_normalized=f"aide {i}", updated_at=same, confidence_score=50,
                               source_url=f"https://exemple.fr/{i}"))
        await db.commit()
    ids = await _all_ids(pg_session_factory, sort_by=sort)
    assert len(ids) == N, f"{len(ids)} lignes renvoyees pour {N} fiches"
    assert len(set(ids)) == N, "doublons entre pages"
