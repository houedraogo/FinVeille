from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


URL_FIXES = {
    "CCI-BF Parcours du createur - financement de 60 initiatives d'entreprises": {
        "source_url": "http://www.cci.bf/?q=fr%2Fdownload%2Ffile%2Ffid%2F1125",
        "note": "Correction HTTPS -> HTTP : le certificat cci.bf est expire, mais le document reste accessible en HTTP.",
    },
    "ZAD Bobo - souscription pour projets productifs a Bobo-Dioulasso": {
        "source_url": "https://primature.gov.bf/amenagement-de-la-zad-de-bobo-dioulasso-le-premier-ministre-lance-officiellement-les-souscriptions-aux-parcelles/",
        "note": "Remplacement temporaire : la plateforme ZAD officielle a un certificat expire, on conserve une page gouvernementale publiant la date et le contexte.",
    },
}


ADMIN_ONLY_REASONS = {
    "ECOTEC Burkina Faso - fonds de partenariat pour MPME": "Source officielle indisponible au contrôle (HTTP 500). A garder en veille admin jusqu'au retour du site.",
    "PMF-FEM Burkina Faso - microfinancements environnement": "Source PNUD bloque les controles automatiques et l'appel stocke ressemble a une actualite ponctuelle. A verifier avant republication.",
    "Prix PEEB Burkina Faso pour entrepreneurs et industriels": "Source media, pas de page officielle de candidature conservee. A verifier avant affichage utilisateur.",
    "Orange Digital Center Burkina Faso - programme Damina": "Source media et fenetre de candidature non structuree. A verifier sur une source Orange officielle avant affichage utilisateur.",
    "African Cashew Alliance - appels et opportunites cajou": "Source avec certificat invalide au controle. A verifier avant affichage utilisateur.",
    "AECF IIW Burkina Faso - entrepreneuriat feminin et economie verte": "Le PDF source correspond a une fenetre ponctuelle publiee debut 2026. A verifier avant de continuer a l'afficher comme opportunite active.",
    "BeoogoLAB Burkina Faso - startup studio et accompagnement tech": "Source officielle en timeout au controle qualite. A verifier avant affichage utilisateur.",
    "WELA Rise - preparation a la levee de fonds pour femmes entrepreneures": "Source non resolue par le controle qualite backend. A verifier avant affichage utilisateur.",
}

EXPIRED_TITLES = {
    "AECF IIW Burkina Faso - entrepreneuriat feminin et economie verte",
}


def _append_tag(device: Device, tag: str) -> None:
    tags = list(device.tags or [])
    if tag not in tags:
        tags.append(tag)
    device.tags = tags


def _decision(reason: str) -> dict[str, Any]:
    return {
        "go_no_go": "a_verifier",
        "recommended_priority": "faible",
        "why_interesting": "Cette opportunite peut rester utile comme signal de veille, mais la source doit etre confirmee avant de la proposer aux utilisateurs.",
        "why_cautious": reason,
        "points_to_confirm": "Verifier l'URL officielle, la fenetre de candidature, les conditions et la date limite directement aupres de l'organisme.",
        "recommended_action": "Conserver en veille admin et republier uniquement apres verification manuelle.",
        "urgency_level": "faible",
        "difficulty_level": "moyenne",
        "effort_level": "moyenne",
        "eligibility_score": 45,
        "strategic_interest": 55,
        "model": "burkina-source-cleanup-v1",
    }


async def _sync_source_url(db, device: Device, url: str, note: str, apply: bool) -> bool:
    changed = False
    if device.source_url != url:
        device.source_url = url
        changed = True
    if device.source_id:
        source = await db.get(Source, device.source_id)
        if source:
            if source.url != url:
                source.url = url
                changed = True
            if note not in (source.notes or ""):
                source.notes = "\n".join(filter(None, [source.notes, note]))[-4000:]
                changed = True
    if changed:
        _append_tag(device, "burkina_url_corrigee")
        device.last_verified_at = datetime.now(timezone.utc)
        device.updated_at = datetime.now(timezone.utc)
    return changed


def _mark_admin_only(device: Device, reason: str) -> bool:
    changed = False
    if device.validation_status != "admin_only":
        device.validation_status = "admin_only"
        changed = True
    _append_tag(device, "burkina_source_a_verifier")
    _append_tag(device, "masquee_utilisateur")
    device.decision_analysis = _decision(reason)
    device.ai_readiness_label = "A verifier avant recommandation"
    device.ai_readiness_score = min(device.ai_readiness_score or 0, 60)
    device.last_verified_at = datetime.now(timezone.utc)
    device.updated_at = datetime.now(timezone.utc)
    return changed


async def run(apply: bool = False) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        titles = list(URL_FIXES) + list(ADMIN_ONLY_REASONS)
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.title.in_(titles))
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated: list[dict[str, Any]] = []
        for device in devices:
            before = {
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "source_url": device.source_url,
            }
            changed = False

            if device.title in URL_FIXES:
                fix = URL_FIXES[device.title]
                changed = await _sync_source_url(db, device, fix["source_url"], fix["note"], apply) or changed

            if device.title in ADMIN_ONLY_REASONS:
                if device.title in EXPIRED_TITLES and device.status != "expired":
                    device.status = "expired"
                    changed = True
                changed = _mark_admin_only(device, ADMIN_ONLY_REASONS[device.title]) or changed

            if changed:
                updated.append(
                    {
                        "before": before,
                        "after": {
                            "title": device.title,
                            "status": device.status,
                            "validation_status": device.validation_status,
                            "source_url": device.source_url,
                            "reason": ADMIN_ONLY_REASONS.get(device.title) or URL_FIXES.get(device.title, {}).get("note"),
                        },
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "updated_count": len(updated), "updated": updated}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Corrige les opportunites Burkina avec sources fragiles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
