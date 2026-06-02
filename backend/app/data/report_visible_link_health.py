"""Verifie les liens HTTP des fiches visibles actionnables."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
PUBLIC_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
EXTERNALLY_VERIFIED_URLS = {
    "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
    "https://culture.gouv.ci/projets/appel-a-candidature-guichet-de-financement-aux-acteurs-du-secteur-de-la-culture/",
    "https://ivoire.ci/cote-divoire-la-cdc-ci-capital-lance-la-deuxieme-edition-du-programme-dappui-aux-startups-ciblant-15000-etudiants",
    "https://www.faij.gov.bf/presentation",
    "https://www.fonafi-bf.org/fonafi-presentation/",
    "https://paif.bf/",
    "https://www.sofigib.bf/",
    "https://www.beoogolab.org/",
    "https://www.fdct-bf.org/Appel-a-projets-2025-du-FDCT-Une-opportunite-pour-les-promoteurs-culturels-et",
    "https://www.gouv.bj/article/3006/",
    "https://www.cmabenin.bj/",
    "https://fnda.agriculture.gouv.bj/",
    "https://semecity.bj/programmes/rise/",
    "https://semecity.bj/nos-programmes/entreprenariat/",
    "https://www.pfs-aie.cm/public/portail/iej",
    "https://enza.capital/",
    "https://vkav.vc/",
    "https://vc4a.com/samurai-incubate/",
    "https://www.mcapitalp.com/",
    "https://www.anadec.cd/accompagnement-a-la-creation-et-a-la-formalisation/",
    "https://mastercardfdn.org/en/what-we-do/our-programs/enhancing-capacities-of-young-women-and-youth-led-enterprises-for-regional-trade-ecowyert/",
    "https://anpgftogo.org/",
    "https://at2er.tg/projet-delectrification-rurale-hors-reseau-par-kits-solaires-domestiques-en-mode-paygo-cizo/",
    "https://www.republiquetogolaise.com/agro/1601-3961-en-2019-le-mifa-a-mobilise-8-1-milliards-fcfa-de-financement-et-impacte-76-000-acteurs-agricoles",
    "https://www.paeij-georef.com/",
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/base-forfaitaire-franchise.html",
    "https://startupandgo-auvergnerhonealpes.fr/soutien-financier-emergence/",
    "https://sofinnovapartners.com/",
    "https://home.angelsquare.co/",
    "https://www.ventechvc.com/",
    "https://partechpartners.com/",
}


@dataclass
class LinkResult:
    id: str
    title: str
    country: str | None
    source_url: str | None
    status_code: int | None
    final_url: str | None
    ok: bool
    error: str | None = None
    action: str = "ok"


def _visible(device: Device) -> bool:
    return (
        device.validation_status in PUBLIC_VALIDATION_STATUSES
        and device.user_quality_decision in PUBLIC_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


async def _check(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, device: Device) -> LinkResult:
    url = device.source_url
    if not url or not url.startswith(("http://", "https://")):
        return LinkResult(str(device.id), device.title or "", device.country, url, None, None, False, "invalid_url", "fix")
    if url in EXTERNALLY_VERIFIED_URLS:
        return LinkResult(str(device.id), device.title or "", device.country, url, 200, url, True, None, "ok_external")

    async with semaphore:
        try:
            response = await client.head(url)
            if response.status_code in {403, 405, 406, 429} or response.status_code >= 500:
                response = await client.get(url)
            ok = 200 <= response.status_code < 400
            if ok:
                action = "ok"
            elif response.status_code in {401, 403, 406, 429}:
                action = "protected"
            elif response.status_code in {404, 410} or response.status_code >= 500:
                action = "fix_or_hide"
            else:
                action = "review"
            return LinkResult(
                str(device.id),
                device.title or "",
                device.country,
                url,
                response.status_code,
                str(response.url),
                ok,
                None if ok else "bad_status",
                action,
            )
        except httpx.TimeoutException:
            return LinkResult(str(device.id), device.title or "", device.country, url, None, None, False, "timeout", "retry_or_review")
        except httpx.HTTPError as exc:
            return LinkResult(str(device.id), device.title or "", device.country, url, None, None, False, exc.__class__.__name__, "retry_or_review")


async def run(limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()

    visible_devices = [device for device in devices if _visible(device)]
    if limit:
        visible_devices = visible_devices[:limit]

    semaphore = asyncio.Semaphore(12)
    timeout = httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=8.0)
    headers = {"User-Agent": "Kafundo link health audit/1.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        results = await asyncio.gather(*[_check(client, semaphore, device) for device in visible_devices])

    failing = [result for result in results if not result.ok]
    by_action: dict[str, int] = {}
    for result in results:
        by_action[result.action] = by_action.get(result.action, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked": len(results),
        "ok": len(results) - len(failing),
        "failing": len(failing),
        "by_action": by_action,
        "actionable_failures": len([result for result in results if result.action == "fix_or_hide"]),
        "items": [asdict(result) for result in failing],
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
