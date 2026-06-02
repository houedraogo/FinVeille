"""Reformule les fiches VC4A visibles sans réécriture utilisateur propre."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import clean_editorial_text, compute_completeness, normalize_title


MODEL = "local-vc4a-visible-rewrite-20260601"

REWRITES: dict[str, dict[str, str]] = {
    "f6b6c3c6-1a73-478a-8042-4750f6d02aa9": {
        "title": "Accélérateur Africa HealthTech ExCon",
        "presentation": "Programme d'accélération repéré via VC4A pour des startups africaines de la santé numérique, des technologies médicales ou de l'innovation sanitaire. La fiche est utile pour identifier rapidement une opportunité d'accompagnement avec visibilité, réseau et accès à des partenaires sectoriels.",
        "eligibility": "À vérifier sur la page officielle : startups ou entreprises innovantes actives dans la santé, la healthtech, les dispositifs médicaux, les services numériques de santé ou les solutions améliorant la résilience sanitaire en Afrique.",
        "funding": "L'avantage principal est un accompagnement d'accélération : mentorat, préparation au développement, exposition auprès de partenaires et accès potentiel à un réseau santé/innovation. Le montant financier éventuel doit être confirmé sur la page VC4A ou auprès de l'organisateur.",
        "procedure": "Ouvrir la page VC4A, vérifier les critères détaillés, préparer les informations sur l'équipe, la solution, le marché, la traction et l'impact sanitaire, puis déposer la candidature avant la date limite indiquée.",
        "checks": "Confirmer le pays éligible, le stade minimum de la startup, les secteurs santé acceptés, les livrables demandés et la nature exacte des avantages avant de mobiliser du temps sur le dossier.",
    },
    "4e70bd3d-6380-4735-8b35-8628e9d087f1": {
        "title": "Boost'in Africa 2026 - programme d'accélération",
        "presentation": "Programme d'accompagnement visible via VC4A pour des startups ou PME africaines en phase de croissance. L'opportunité peut aider une équipe à structurer son développement, renforcer son modèle et accéder à un réseau d'experts ou de partenaires.",
        "eligibility": "À confirmer sur la source officielle : startups, PME ou entrepreneurs basés en Afrique, avec un projet déjà lancé et un besoin clair d'accompagnement pour passer à l'échelle.",
        "funding": "L'appui attendu porte surtout sur l'accélération, le mentorat, la préparation commerciale, la visibilité et la mise en relation. Si une dotation ou un financement direct existe, son montant doit être validé sur la page officielle.",
        "procedure": "Consulter la fiche VC4A, vérifier le format du programme, réunir les éléments de candidature demandés, puis compléter le formulaire avant l'échéance.",
        "checks": "Vérifier la durée du programme, les pays concernés, les secteurs prioritaires, les obligations de présence et la réalité d'un soutien financier éventuel.",
    },
    "a5de7f58-f384-483e-9453-b9e1ba33f009": {
        "title": "Programme Star Venture de la BERD",
        "presentation": "Programme d'accompagnement pour startups à fort potentiel repéré via VC4A. Il vise à renforcer des jeunes entreprises innovantes grâce à du conseil, du mentorat, une meilleure préparation à la croissance et un accès à un réseau d'experts.",
        "eligibility": "À vérifier sur la fiche officielle : startups innovantes situées dans les pays couverts par le programme, avec une équipe engagée, un produit ou service déjà structuré et un potentiel de croissance démontrable.",
        "funding": "L'avantage principal est l'accompagnement stratégique et opérationnel. Le programme peut donner accès à de l'expertise, du mentorat, des contacts investisseurs ou des services partenaires; tout financement direct doit être confirmé auprès de la BERD ou de VC4A.",
        "procedure": "Lire la fiche VC4A, vérifier les pays et stades éligibles, préparer une présentation claire de la startup, de la traction et des besoins, puis candidater via le canal indiqué.",
        "checks": "Confirmer l'éligibilité géographique, la langue de candidature, le calendrier, les documents attendus et les engagements demandés aux startups retenues.",
    },
    "bcf13ec9-df99-4c79-962c-f836df1c92a6": {
        "title": "TiE Women 2026 - entrepreneuriat féminin",
        "presentation": "Concours ou programme d'accompagnement repéré via VC4A pour des entrepreneures et fondatrices. Il peut offrir de la visibilité, du mentorat, une préparation au pitch et un accès à un réseau international d'entrepreneurs.",
        "eligibility": "À confirmer sur la page officielle : entreprises portées ou cofondées par des femmes, avec une solution active ou en développement et un potentiel de croissance ou d'impact.",
        "funding": "Les avantages peuvent inclure mentorat, coaching, pitch, visibilité et accès réseau. Les prix financiers éventuels, montants et conditions de versement doivent être vérifiés directement sur la source officielle.",
        "procedure": "Consulter la fiche VC4A, vérifier les critères du programme TiE Women, préparer les informations sur la fondatrice, l'entreprise, le marché, l'impact et la traction, puis candidater avant la date limite.",
        "checks": "Vérifier les pays admis, le rôle exact de la fondatrice, les pièces demandées, les étapes de sélection et les avantages réellement attribués aux finalistes.",
    },
    "8c41722e-e123-4ca7-8b1d-932cf2702b24": {
        "title": "Concours startups Raise Summit 2026",
        "presentation": "Concours de startups repéré via VC4A pour des entreprises innovantes qui veulent gagner en visibilité, pitcher devant un public qualifié et accéder à des partenaires, investisseurs ou mentors.",
        "eligibility": "À vérifier sur la source officielle : startups ou jeunes entreprises correspondant au thème du Raise Summit, avec une proposition claire, une équipe identifiée et un potentiel de marché ou d'impact.",
        "funding": "L'intérêt principal est la visibilité, le pitch, le réseau et les opportunités de partenariat. Les prix, dotations ou avantages financiers éventuels doivent être confirmés sur la page officielle du concours.",
        "procedure": "Lire les critères sur VC4A, préparer un dossier court et convaincant, vérifier les éléments de pitch demandés, puis soumettre la candidature avant la clôture.",
        "checks": "Confirmer les secteurs éligibles, les pays acceptés, les critères de sélection, le format du pitch et les avantages réellement associés au concours.",
    },
    "71bdc132-5463-44de-9fc0-3c7c58c2f55d": {
        "title": "RISE 2 - accompagnement des PME",
        "presentation": "Programme d'accompagnement visible via VC4A pour des PME ou entreprises en croissance. Il peut aider les dirigeants à renforcer leur modèle, leur gestion, leur accès au marché et leur préparation à de nouveaux financements.",
        "eligibility": "À confirmer sur la source officielle : PME, entrepreneurs ou entreprises africaines correspondant au périmètre RISE 2, avec un besoin concret d'accompagnement et un potentiel de développement.",
        "funding": "L'appui porte principalement sur l'accompagnement, le conseil, le mentorat et la mise en relation. Le montant d'un éventuel soutien financier direct doit être validé dans les documents officiels du programme.",
        "procedure": "Consulter la fiche VC4A, vérifier les critères, préparer les informations sur l'entreprise, les besoins d'accompagnement et les objectifs de croissance, puis déposer la candidature avant la date limite.",
        "checks": "Contrôler les pays ciblés, les secteurs admis, le stade de maturité attendu, les documents demandés et la nature exacte des bénéfices du programme.",
    },
    "c93e1f24-e561-4f0c-8ad8-ac2661928b2c": {
        "title": "M Ventures - programme d'accompagnement entrepreneurial",
        "presentation": "Opportunité d'accompagnement repérée via VC4A pour des entrepreneurs ou startups. Elle doit être analysée comme une piste de soutien à la structuration, au développement commercial, à la visibilité ou à la mise en relation.",
        "eligibility": "À vérifier sur la page officielle : entrepreneurs, startups ou PME correspondant au périmètre du programme M Ventures, avec une activité suffisamment claire pour être évaluée par les organisateurs.",
        "funding": "L'avantage exact doit être confirmé sur la source officielle. Il peut s'agir d'accompagnement, de mentorat, d'accès réseau, de services partenaires ou d'un soutien financier selon les conditions du programme.",
        "procedure": "Ouvrir la fiche VC4A, confirmer que la candidature est encore ouverte, réunir les informations demandées sur l'équipe, le projet et les besoins, puis déposer le dossier via le canal indiqué.",
        "checks": "Vérifier immédiatement la date limite, car l'échéance repérée est très proche. Confirmer aussi les pays éligibles, le format de sélection et la valeur concrète de l'appui proposé.",
    },
}


def _section(key: str, title: str, content: str, confidence: int = 82) -> dict[str, Any]:
    cleaned = clean_editorial_text(content).replace("VC 4 A", "VC4A")
    return {
        "key": key,
        "title": title,
        "content": cleaned,
        "confidence": confidence,
        "source": "reformulation_vc4a_visible_20260601",
    }


def _sections(device: Device, rewrite: dict[str, str]) -> list[dict[str, Any]]:
    deadline = (
        f"Date limite indiquée : {device.close_date:%d/%m/%Y}. Vérifier l'heure exacte de clôture sur VC4A avant de candidater."
        if device.close_date
        else "Aucune date limite fiable n'est confirmée dans la fiche. Vérifier le calendrier directement sur VC4A."
    )
    return [
        _section("presentation", "Présentation", rewrite["presentation"], 86),
        _section("eligibility", "Pour qui ?", rewrite["eligibility"], 80),
        _section("funding", "Ce que vous pouvez obtenir", rewrite["funding"], 78),
        _section("calendar", "Date limite", deadline, 86 if device.close_date else 70),
        _section("procedure", "Comment candidater", rewrite["procedure"], 82),
        _section("checks", "Points à vérifier", rewrite["checks"], 78),
    ]


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _full_description(device: Device, sections: list[dict[str, Any]]) -> str:
    deadline = (
        f"La candidature doit être vérifiée et déposée avant le {device.close_date:%d/%m/%Y}."
        if device.close_date
        else "Le calendrier doit être confirmé sur la source officielle avant de préparer le dossier."
    )
    return "\n\n".join(
        [
            f"## Présentation\n{sections[0]['content']}",
            f"## Éligibilité\n{sections[1]['content']}",
            f"## Avantages\n{sections[2]['content']}",
            f"## Calendrier\n{deadline}",
            f"## Démarche\n{sections[4]['content']}",
        ]
    )


def _apply_rewrite(device: Device, rewrite: dict[str, str]) -> None:
    sections = _sections(device, rewrite)
    device.title = rewrite["title"]
    device.title_normalized = normalize_title(device.title)
    device.short_description = sections[0]["content"]
    device.eligibility_criteria = sections[1]["content"]
    device.funding_details = sections[2]["content"]
    device.specific_conditions = sections[4]["content"]
    device.required_documents = (
        "À préparer selon la fiche officielle : présentation de l'équipe, description du projet, preuve de traction si disponible, "
        "informations juridiques de l'entreprise et pièces propres au programme."
    )
    device.full_description = _full_description(device, sections).replace("VC 4 A", "VC4A")
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = MODEL
    now = datetime.now(timezone.utc)
    device.ai_rewrite_checked_at = now
    device.language = "fr"
    tags = list(device.tags or [])
    for tag in ("audit:vc4a_rewritten", "quality:visible_french_rewrite"):
        if tag not in tags:
            tags.append(tag)
    device.tags = tags[:24]
    device.completeness_score = compute_completeness(_payload(device))
    device.user_quality_score = max(device.user_quality_score or 0, 92)
    device.updated_at = now


async def run() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        ids = [UUID(value) for value in REWRITES]
        devices = (await db.execute(select(Device).where(Device.id.in_(ids)))).scalars().all()
        changed = []

        for device in devices:
            rewrite = REWRITES.get(str(device.id))
            if not rewrite:
                continue
            before = {
                "id": str(device.id),
                "before_title": device.title,
                "before_ai_rewrite_status": device.ai_rewrite_status,
            }
            _apply_rewrite(device, rewrite)
            changed.append({**before, "after_title": device.title, "after_ai_rewrite_status": device.ai_rewrite_status})

        await db.commit()
        return {"changed": len(changed), "items": changed}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
