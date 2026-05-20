from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


LINK_FIXES: dict[str, str] = {}


HIDE_FROM_USERS: dict[str, str] = {
    "ADPME Benin - accompagnement et acces au financement des PME": (
        "La plateforme officielle ADPME/e-PME ne repond pas de facon stable lors de la verification. "
        "Fiche retiree du public tant que le lien n'est pas fiable."
    ),
    "ADERIZ Cote d'Ivoire - veille des appels et appuis filiere riz": (
        "Site officiel indisponible au moment de la verification. Pas de lien de candidature stable."
    ),
    "Cote d'Ivoire PME - veille des appels a projets pour PME": (
        "Le lien officiel redirige vers une URL externe non fiable. Fiche retiree du public."
    ),
    "FONAME Côte d'Ivoire - portefeuille national de projets énergie": (
        "Projet institutionnel/portefeuille public, pas une opportunite directe de candidature utilisateur."
    ),
    "OIF Cote d'Ivoire - consolidation de l'initiative cuisson propre": (
        "Lien source bloque ou non accessible automatiquement. A republier seulement avec une page de candidature stable."
    ),
    "PMF-FEM Cote d'Ivoire - microfinancements environnement et communautes": (
        "Certificat SSL de la source expire. Fiche retiree du public tant que le lien officiel n'est pas stable."
    ),
    "ProPME Benin - croissance et competitivite des MPME": (
        "Page programme institutionnelle sans candidature ouverte clairement exploitable."
    ),
    "WEDAF Benin - entrepreneuriat feminin et acces au financement": (
        "Programme institutionnel annonce, sans guichet de candidature utilisateur clairement ouvert."
    ),
}


def _append_admin_note(device: Device, note: str) -> None:
    current = device.decision_analysis if isinstance(device.decision_analysis, dict) else {}
    notes = list(current.get("admin_notes") or [])
    if note not in notes:
        notes.append(note)
    current["admin_notes"] = notes
    current["public_visibility_reason"] = "Masquee cote utilisateur : source non actionnable ou lien insuffisamment fiable."
    device.decision_analysis = current


async def run(apply: bool) -> dict[str, Any]:
    titles = set(LINK_FIXES) | set(HIDE_FROM_USERS)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Device).where(Device.title.in_(titles)))
        devices = list(result.scalars().all())

        report: dict[str, Any] = {"fixed_links": [], "hidden": [], "missing": []}
        found_titles = {device.title for device in devices}
        for title in sorted(titles - found_titles):
            report["missing"].append(title)

        now = datetime.now(timezone.utc)
        for device in devices:
            if device.title in LINK_FIXES:
                new_url = LINK_FIXES[device.title]
                report["fixed_links"].append(
                    {
                        "title": device.title,
                        "old_url": device.source_url,
                        "new_url": new_url,
                    }
                )
                if apply:
                    device.source_url = new_url
                    device.last_verified_at = now

            if device.title in HIDE_FROM_USERS:
                reason = HIDE_FROM_USERS[device.title]
                report["hidden"].append(
                    {
                        "title": device.title,
                        "old_status": device.status,
                        "old_validation_status": device.validation_status,
                        "reason": reason,
                    }
                )
                if apply:
                    device.validation_status = "admin_only"
                    device.status = "pending_review"
                    device.ai_readiness_label = "a_verifier"
                    _append_admin_note(device, reason)
                    device.last_verified_at = now

        if apply:
            await session.commit()
        else:
            await session.rollback()

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
