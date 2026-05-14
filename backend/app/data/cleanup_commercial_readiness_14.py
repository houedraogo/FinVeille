from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import clean_editorial_text


LOCAL_MODEL = "local-commercial-readiness-fix-v1"


EXPIRED_IDS = {
    "d71b1353-c19e-4e08-b2f1-c3c1f85d6fa6": "Date limite depassee le 11/05/2026.",
    "fb787380-06ea-4273-8aa4-d831e5f13f38": "Date limite depassee le 11/05/2026.",
    "b04f5cd1-e372-424e-93c3-bc48fc804fae": "Date limite depassee le 12/05/2026.",
}


SUMMARY_FIXES = {
    "ffbed3a2-20fb-4ad9-9bc0-f95c46ea8037": (
        "Programme institutionnel de la Banque mondiale au Kenya visant a ameliorer l'acces a l'eau, "
        "a l'assainissement et a l'hygiene. La fiche sert surtout au suivi d'un projet public finance, "
        "et non a une candidature directe classique."
    ),
}


STANDBY_NOTES = {
    "c8e8390e-8222-45fa-bab6-5a494788091c": "Date limite non communiquee par la source officielle au moment du controle.",
    "e10b4fb1-10b5-46a1-9832-6595cc0e1140": "Date limite non communiquee par la source officielle au moment du controle.",
    "2947dedc-cb1e-4d59-a8ee-8fbb455b4a2f": "Date limite non communiquee par la source officielle au moment du controle.",
    "028ff2e8-c2c2-4fad-a44c-0f06644812e0": "Date limite non communiquee : avantage fiscal a verifier sur la source officielle.",
    "9cbf6253-65cc-43a8-927f-b678c373b922": "Date limite non communiquee : avantage fiscal a verifier sur la source officielle.",
}


TYPE_FIXES = {
    "2947dedc-cb1e-4d59-a8ee-8fbb455b4a2f": "subvention",
    "e0627c1f-6de7-42fd-8ef4-7b5431a561d1": "subvention",
}


GLOBAL_SOUTH_IDS = {
    "7e5b1888-ac88-41f3-bb0c-38e6a5bca476",
    "10358ded-450b-422c-89ff-64ce20372de2",
    "c8e8390e-8222-45fa-bab6-5a494788091c",
    "e10b4fb1-10b5-46a1-9832-6595cc0e1140",
    "fd88fb73-3608-496c-8a90-59513c5620f2",
    "a44be390-9998-4067-baf0-83b660092bb0",
    "2947dedc-cb1e-4d59-a8ee-8fbb455b4a2f",
    "e0627c1f-6de7-42fd-8ef4-7b5431a561d1",
}


def _section(key: str, title: str, content: str, confidence: int = 78) -> dict:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": "commercial_readiness_cleanup",
    }


def _amount_text(device: Device) -> str:
    if device.amount_max:
        return f"Montant maximal repere : {device.amount_max} {device.currency or ''}."
    return (
        "Le montant exact, la dotation ou les avantages associes doivent etre confirmes "
        "sur la page officielle avant toute decision."
    )


def _calendar_text(device: Device) -> str:
    if device.close_date:
        return f"Date limite reperee : {device.close_date.strftime('%d/%m/%Y')}."
    if device.recurrence_notes:
        return clean_editorial_text(device.recurrence_notes)
    return "La source ne communique pas de date limite exploitable a ce stade."


def _build_sections(device: Device) -> list[dict]:
    presentation = clean_editorial_text(
        device.short_description
        or f"{device.title} est une opportunite reperee par {device.organism}."
    )
    eligibility = clean_editorial_text(
        device.eligibility_criteria
        or "Les beneficiaires exacts doivent etre confirmes sur la source officielle. Verifier en priorite le pays, le profil du porteur, le secteur et les conditions de candidature."
    )
    funding = clean_editorial_text(device.funding_details or _amount_text(device))
    return [
        _section("presentation", "Presentation", presentation, 82),
        _section("eligibility", "Criteres d'eligibilite", eligibility, 72),
        _section("funding", "Montant / avantages", funding, 72),
        _section("calendar", "Calendrier", _calendar_text(device), 78),
        _section(
            "procedure",
            "Demarche",
            "Consulter la page officielle, verifier les criteres et suivre le lien de candidature ou les instructions publiees par l'organisme.",
            72,
        ),
    ]


async def run() -> dict:
    target_ids = set(EXPIRED_IDS) | set(SUMMARY_FIXES) | set(STANDBY_NOTES) | set(TYPE_FIXES) | GLOBAL_SOUTH_IDS
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Device).where(Device.id.in_([UUID(item) for item in target_ids]))
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []
        now = datetime.now(timezone.utc)

        for device in rows:
            before = {
                "id": str(device.id),
                "title": device.title,
                "status": device.status,
                "type": device.device_type,
            }
            changed = False
            device_id = str(device.id)

            if device_id in EXPIRED_IDS:
                device.status = "expired"
                device.validation_status = "auto_published"
                device.recurrence_notes = EXPIRED_IDS[device_id]
                changed = True

            if device_id in SUMMARY_FIXES:
                device.short_description = SUMMARY_FIXES[device_id]
                device.full_description = (
                    "## Presentation\n"
                    f"{SUMMARY_FIXES[device_id]}\n\n"
                    "## Points a verifier\n"
                    "Consulter la page officielle du projet pour verifier les beneficiaires, les modalites operationnelles et les documents publies."
                )
                changed = True

            if device_id in STANDBY_NOTES:
                device.status = "standby"
                device.recurrence_notes = STANDBY_NOTES[device_id]
                changed = True

            if device_id in TYPE_FIXES:
                device.device_type = TYPE_FIXES[device_id]
                changed = True

            if device_id in GLOBAL_SOUTH_IDS:
                if not device.funding_details or "confirmer" not in device.funding_details.lower():
                    device.funding_details = _amount_text(device)
                    changed = True
                device.eligibility_criteria = device.eligibility_criteria or (
                    "Verifier les criteres exacts sur la source officielle : profil du candidat, pays eligibles, secteur, niveau de maturite et documents demandes."
                )
                device.ai_rewritten_sections_json = _build_sections(device)
                device.ai_rewrite_status = "done"
                device.ai_rewrite_model = LOCAL_MODEL
                device.ai_rewrite_checked_at = now
                changed = True

            if device_id in SUMMARY_FIXES or device_id in STANDBY_NOTES or device_id in EXPIRED_IDS:
                if not device.ai_rewritten_sections_json:
                    device.ai_rewritten_sections_json = _build_sections(device)
                    device.ai_rewrite_status = "done"
                    device.ai_rewrite_model = LOCAL_MODEL
                    device.ai_rewrite_checked_at = now
                    changed = True

            if changed:
                updated += 1
                preview.append(
                    {
                        "before": before,
                        "after": {
                            "id": str(device.id),
                            "title": device.title,
                            "status": device.status,
                            "type": device.device_type,
                            "rewrite": device.ai_rewrite_status,
                        },
                    }
                )

        await db.commit()

    return {"updated": updated, "preview": preview}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
