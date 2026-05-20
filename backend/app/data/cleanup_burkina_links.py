from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


LINK_FIXES: dict[str, str] = {
    "CCI-BF Parcours du createur - financement de 60 initiatives d'entreprises": (
        "https://www.cci.bf/?q=fr%2Factualites%2Fappel-%C3%A0-projets-pour-le-financement-de-60-initiatives-dentreprises"
    ),
    "FAARF Burkina Faso - credit aux femmes pour activites generatrices de revenus": "https://www.faarf.bf/",
    "AFP-PME Burkina Faso - financement et promotion des PME": "https://afppme.bf/a-propos/",
    "FONRID Burkina Faso - appels a projets recherche et innovation": "https://fonrid.com/nos-appels-a-projets/",
    "FDCT Burkina Faso - financement culture et tourisme": "https://www.fdct-bf.org/-Appel-a-candidature-",
    "FAIJ Burkina Faso - financement de micro-projets jeunes": "https://www.faij.gov.bf/",
    "FASI Burkina Faso - financement de microprojets du secteur informel": "https://plaje.bf/fasi/",
    "Fonds MIWA+ - soutien aux organisations LBTQI francophones": "https://globalphilanthropyproject.org/grants/",
    "Burkina Faso - financement des microprojets de jeunes diplomes": (
        "https://servicepublic.gov.bf/fiches/emploi-financement-des-microprojets-des-jeunes-diplomes-du-superieur"
    ),
}

SOURCE_NAME_FIXES: dict[str, str] = {
    "FAARF Burkina Faso - credit aux femmes pour activites generatrices de revenus": (
        "FAARF Burkina Faso - crédits aux femmes"
    ),
    "FASI Burkina Faso - financement de microprojets du secteur informel": (
        "FASI Burkina Faso - secteur informel"
    ),
    "FAIJ Burkina Faso - financement de micro-projets jeunes": (
        "FAIJ Burkina Faso - micro-projets jeunes"
    ),
}


HIDE_FROM_USERS: dict[str, str] = {
    "CCI-BF Parcours du createur - financement de 60 initiatives d'entreprises": (
        "Appel ponctuel clos le 20 avril 2023 selon la page officielle CCI-BF. "
        "Fiche conservee uniquement en archive admin, a ne pas afficher aux utilisateurs."
    ),
    "Burkina Faso - financement des microprojets de jeunes diplomes": (
        "La fiche pointe vers le portail administratif servicepublic.gov.bf sans source metier ou guichet de candidature "
        "suffisamment direct. Masquee cote utilisateur en attendant une source officielle plus actionnable."
    ),
    "CIFEA Burkina Faso - incubation et accompagnement des projets agricoles": (
        "La source officielle CIFEA renvoie une erreur serveur lors du controle qualite. "
        "Fiche masquee cote utilisateur tant que le lien officiel n'est pas stable."
    ),
    "FAIJ Burkina Faso - financement de micro-projets jeunes": (
        "Le site officiel FAIJ existe mais presente un certificat SSL expire au controle qualite. "
        "Fiche masquee cote utilisateur pour eviter d'envoyer les utilisateurs vers un lien non fiable."
    ),
    "ZAD Bobo - souscription pour projets productifs a Bobo-Dioulasso": (
        "La plateforme officielle de souscription presente une erreur de certificat ou une indisponibilite. "
        "Fiche retiree du public tant que le lien de candidature n'est pas stable."
    ),
    "OSEZ - entrepreneurs d'Afrique occidentale francophone": (
        "Source indirecte media. Aucune page officielle de candidature fiable identifiee."
    ),
    "Fondation Facilite Sahel - prequalification ONG locales": (
        "Source indirecte. La fiche doit rester en veille admin tant que la page officielle n'est pas confirmee."
    ),
    "Afrique Innovante - competition femmes entrepreneures et PME tech": (
        "Source indirecte. A remettre en public uniquement avec une page officielle ou une fenetre active."
    ),
    "CORAF - veille innovations agricoles et Prix Abdoulaye Toure": (
        "Veille institutionnelle, pas une opportunite de candidature directe pour l'utilisateur."
    ),
}


def _append_admin_note(device: Device, note: str) -> None:
    current = device.decision_analysis if isinstance(device.decision_analysis, dict) else {}
    existing_notes = list(current.get("admin_notes") or [])
    if note not in existing_notes:
        existing_notes.append(note)
    current["admin_notes"] = existing_notes
    current["public_visibility_reason"] = "Masquee cote utilisateur pour eviter un lien de candidature indirect ou ambigu."
    device.decision_analysis = current


async def run(apply: bool) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        titles = set(LINK_FIXES) | set(HIDE_FROM_USERS)
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
                old_url = device.source_url
                report["fixed_links"].append(
                    {
                        "title": device.title,
                        "old_url": old_url,
                        "new_url": new_url,
                    }
                )
                if apply:
                    device.source_url = new_url
                    device.last_verified_at = now
                    if device.source_id:
                        source = await session.get(Source, device.source_id)
                        if source:
                            source.url = new_url
                            if device.title in SOURCE_NAME_FIXES:
                                source.name = SOURCE_NAME_FIXES[device.title]
                            source.updated_at = now

            if device.title in HIDE_FROM_USERS:
                report["hidden"].append(
                    {
                        "title": device.title,
                        "old_validation_status": device.validation_status,
                        "reason": HIDE_FROM_USERS[device.title],
                    }
                )
                if apply:
                    device.validation_status = "admin_only"
                    if device.title == "CCI-BF Parcours du createur - financement de 60 initiatives d'entreprises":
                        device.status = "expired"
                        device.open_date = datetime(2023, 4, 14).date()
                        device.close_date = datetime(2023, 4, 20).date()
                        device.user_quality_decision = "admin_only"
                        device.user_quality_score = 20
                        device.user_quality_reasons = ["appel_expire_2023", "archive_admin"]
                    else:
                        device.status = "pending_review"
                        if device.title == "Burkina Faso - financement des microprojets de jeunes diplomes":
                            device.user_quality_decision = "admin_only"
                            device.user_quality_score = 40
                            device.user_quality_reasons = ["source_administrative_generique", "guichet_direct_non_confirme"]
                    device.ai_readiness_label = "a_verifier"
                    _append_admin_note(device, HIDE_FROM_USERS[device.title])
                    device.last_verified_at = now

        if apply:
            await session.commit()

        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(apply=args.apply))
    import json

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
