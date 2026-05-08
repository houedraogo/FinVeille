import asyncio
from datetime import date
from urllib.parse import urlparse

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import sanitize_text


SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises"

RECURRING_HOSTS = {
    "www.bpifrance.fr",
    "diag.bpifrance.fr",
    "diagecoconception.bpifrance.fr",
    "bpifrance-creation.fr",
    "www.inpi.fr",
    "www.siagi.com",
    "www.bretagneactive.org",
    "www.urssaf.fr",
    "scientipolecapital.fr",
    "www.bje-capital-risque.com",
    "www.bretagne-capital-solidaire.fr",
    "www.bretagne.bzh",
    "www.normandie.fr",
    "www.auvergnerhonealpes.fr",
    "www.paysdelaloire.fr",
    "www.vte-france.fr",
    "www.ademe.fr",
    "www.legifrance.gouv.fr",
    "e-vie.businessfrance.fr",
    "flash.bpifrance.fr",
}

BLOCKER_MARKERS = (
    "appel a projets",
    "appel à projets",
    "appel a candidature",
    "appel à candidature",
    "concours",
    "phase b",
    "jusqu'au ",
    "jusqu au ",
    "avant le ",
    "au plus tard le ",
)


def _text_blob(device: Device) -> str:
    return sanitize_text(
        " ".join(
            part
            for part in (
                device.title or "",
                device.short_description or "",
                device.full_description or "",
                device.source_raw or "",
            )
            if part
        )
    ).lower()


def _looks_like_recurring_product(device: Device) -> bool:
    if device.close_date is not None:
        return False
    host = (urlparse(device.source_url or "").netloc or "").lower()
    text = _text_blob(device)
    if any(marker in text for marker in BLOCKER_MARKERS):
        return False

    title = sanitize_text(device.title or "").lower()
    if host == "www.legifrance.gouv.fr" and any(
        marker in text or marker in title
        for marker in ("exoneration", "exonération", "abattement", "cotisation fonciere", "cotisation foncière")
    ):
        return True
    if host == "e-vie.businessfrance.fr" or "volontariat international en entreprise" in title:
        return True
    if host == "flash.bpifrance.fr":
        return True

    if host not in RECURRING_HOSTS:
        return False

    recurring_types = {"pret", "garantie", "accompagnement", "investissement", "autre", "exoneration"}
    if (device.device_type or "") in recurring_types:
        return True

    recurring_markers = (
        "catalogue-offres",
        "diagnostic",
        "diag",
        "garantie",
        "pret",
        "prêt",
        "credit-bail",
        "crédit-bail",
        "fonds direct",
        "pass pi",
        "redevances brevets",
    )
    return any(marker in text for marker in recurring_markers)


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if not source:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                    Device.validation_status != "rejected",
                )
            )
        ).scalars().all()

        updated = 0
        validated = 0
        pending_review = 0
        preview = []

        for device in devices:
            before_status = device.status
            before_validation = device.validation_status
            changed = False

            if device.close_date:
                if device.close_date < date.today():
                    next_status = "expired"
                else:
                    next_status = "open"
                if device.status != next_status:
                    device.status = next_status
                    changed = True
                if device.is_recurring:
                    device.is_recurring = False
                    changed = True
                if device.recurrence_notes:
                    device.recurrence_notes = None
                    changed = True
            elif _looks_like_recurring_product(device):
                if device.status != "recurring":
                    device.status = "recurring"
                    changed = True
                if not device.is_recurring:
                    device.is_recurring = True
                    changed = True
                note = (
                    "Classe comme dispositif permanent: la source publique presente une offre ou un produit"
                    " sans fenetre de cloture unique exploitable."
                )
                if device.recurrence_notes != note:
                    device.recurrence_notes = note
                    changed = True
            else:
                if device.status != "standby":
                    device.status = "standby"
                    changed = True
                if device.is_recurring:
                    device.is_recurring = False
                    changed = True
                note = "Date limite non communiquee par la source : verification manuelle conseillee avant recommandation."
                if device.recurrence_notes != note:
                    device.recurrence_notes = note
                    changed = True
                if device.validation_status == "auto_published":
                    device.validation_status = "pending_review"
                    changed = True

            if device.status in {"open", "recurring", "expired"} and device.validation_status == "pending_review":
                device.validation_status = "auto_published"
                changed = True

            if changed:
                updated += 1
                if len(preview) < 15:
                    preview.append(
                        {
                            "title": device.title,
                            "host": (urlparse(device.source_url or "").netloc or "").lower(),
                            "status": f"{before_status} -> {device.status}",
                            "validation": f"{before_validation} -> {device.validation_status}",
                        }
                    )

            if device.validation_status == "auto_published":
                validated += 1
            elif device.validation_status == "pending_review":
                pending_review += 1

        await db.commit()

        return {
            "source": SOURCE_NAME,
            "updated": updated,
            "auto_published": validated,
            "pending_review": pending_review,
            "preview": preview,
        }


def main():
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
