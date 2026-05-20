from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.user_quality import compute_user_quality
from app.utils.text_utils import compute_completeness, generate_slug, normalize_title


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "CIFEA Burkina Faso - incubation entrepreneuriat agricole",
        "organism": "Ministere de l'Agriculture / CIFEA",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "incubateur_officiel",
        "level": 1,
        "url": "https://cifea.me.bf/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Programme national a suivre manuellement: la page ne fournit pas toujours un flux d'appels structuré.",
        },
        "notes": "Incubateur public burkinabe utile pour les porteurs de projets agricoles, agroalimentaires et ruraux.",
    },
    {
        "name": "Benin - labellisation startups",
        "organism": "Ministere du Numerique et de la Digitalisation du Benin",
        "country": "Bénin",
        "region": "Bénin",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://numerique.gouv.bj/publications/actualites/lancement-de-la-labellisation-des-startups",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Dispositif institutionnel récurrent: la labellisation facilite l'accès aux programmes et appuis publics.",
        },
        "notes": "Source officielle pour suivre la labellisation des startups béninoises.",
    },
    {
        "name": "Cote d'Ivoire PME - AMI levee de fonds",
        "organism": "Agence Cote d'Ivoire PME",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://cipme.ci/appel-projets/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Portail officiel d'appels a projets et manifestations d'intérêt pour PME ivoiriennes.",
        },
        "notes": "Source prioritaire pour les appels Côte d'Ivoire PME, levée de fonds et accompagnement.",
    },
    {
        "name": "Common Fund for Commodities - appels a propositions",
        "organism": "Common Fund for Commodities",
        "country": "Afrique",
        "region": "Afrique de l'Ouest",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.common-fund.org/call-for-proposals",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Appels périodiques avec dates; les fiches doivent être mises à jour à chaque round.",
        },
        "notes": "Appels internationaux utiles pour PME, cooperatives et entreprises de chaines de valeur agricoles.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "CIFEA Burkina Faso - incubation entrepreneuriat agricole",
        "title": "CIFEA Burkina Faso - incubation et accompagnement des projets agricoles",
        "organism": "Ministere de l'Agriculture / CIFEA",
        "organism_type": "institution publique",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation",
        "sectors": ["agriculture", "agroalimentaire", "entrepreneuriat", "formation"],
        "beneficiaries": ["porteur projet", "startup", "pme", "entrepreneur", "jeune entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme national à suivre: les cohortes et appels peuvent ouvrir selon les sessions du CIFEA.",
        "source_url": "https://cifea.me.bf/",
        "source_raw": "Le CIFEA accompagne les porteurs de projets et jeunes entreprises dans les secteurs agricoles et agroalimentaires au Burkina Faso.",
        "presentation": "Le CIFEA est une piste utile pour les entrepreneurs agricoles au Burkina Faso qui cherchent un accompagnement structuré, de l'incubation, du renforcement de capacités et une mise en relation avec l'écosystème agricole.",
        "eligibility": "La cible principale concerne les porteurs de projets, startups, PME et jeunes entrepreneurs actifs dans l'agriculture, l'agroalimentaire ou les services liés aux chaînes de valeur agricoles.",
        "funding": "Le dispositif est surtout un accompagnement. Les appuis financiers éventuels dépendent des programmes, cohortes ou partenaires associés; ils doivent être confirmés sur la source officielle.",
        "calendar": "Dispositif à suivre de manière récurrente. Les fenêtres de candidature ne sont pas toujours affichées sous forme de calendrier permanent.",
        "procedure": "Consulter la page officielle du CIFEA, vérifier les appels ou cohortes en cours, puis contacter l'équipe ou utiliser le formulaire indiqué par le programme.",
        "checks": "Confirmer la cohorte ouverte, les secteurs admissibles, les critères d'âge ou de maturité du projet, et l'existence éventuelle d'un appui financier.",
    },
    {
        "source_name": "Benin - labellisation startups",
        "title": "Bénin - labellisation officielle des startups",
        "organism": "Ministere du Numerique et de la Digitalisation du Benin",
        "organism_type": "institution publique",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "labellisation",
        "sectors": ["numerique", "innovation", "startup", "entrepreneuriat"],
        "beneficiaries": ["startup", "entrepreneur", "pme", "entreprise innovante"],
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "La labellisation est un dispositif institutionnel à surveiller pour les startups béninoises.",
        "source_url": "https://numerique.gouv.bj/publications/actualites/lancement-de-la-labellisation-des-startups",
        "source_raw": "Le Gouvernement du Bénin a lancé une démarche de labellisation des startups afin de structurer l'écosystème et de faciliter l'accès aux mesures de soutien.",
        "presentation": "La labellisation officielle des startups au Bénin permet aux entreprises innovantes d'être mieux identifiées par l'écosystème public et privé. Elle peut faciliter l'accès aux programmes d'accompagnement, appels, partenariats et mesures de soutien.",
        "eligibility": "Le dispositif cible les startups et entreprises innovantes basées au Bénin. Les critères exacts de maturité, d'innovation, de secteur et de constitution juridique doivent être vérifiés sur le portail officiel.",
        "funding": "Ce n'est pas une subvention directe. L'intérêt principal est l'accès à une reconnaissance officielle et à de futurs dispositifs d'appui ou de financement.",
        "calendar": "Dispositif institutionnel à suivre. La source ne publie pas toujours une date limite unique; vérifier l'ouverture du dépôt sur le portail officiel.",
        "procedure": "Consulter la page officielle, vérifier les critères de labellisation, préparer les informations sur l'entreprise et suivre la procédure indiquée par le Ministère du Numérique.",
        "checks": "Confirmer si une fenêtre de dépôt est ouverte, les pièces requises, les délais de traitement et les avantages concrets associés au label.",
    },
    {
        "source_name": "Cote d'Ivoire PME - AMI levee de fonds",
        "title": "Côte d'Ivoire PME - appels à projets et accompagnement levée de fonds",
        "organism": "Agence Cote d'Ivoire PME",
        "organism_type": "agence nationale",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "accompagnement_financement",
        "sectors": ["entrepreneuriat", "pme", "finance", "innovation"],
        "beneficiaries": ["pme", "startup", "entreprise", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Portail national à surveiller pour les appels PME, cohortes et manifestations d'intérêt.",
        "source_url": "https://cipme.ci/appel-projets/",
        "source_raw": "L'Agence Côte d'Ivoire PME publie des appels à projets, manifestations d'intérêt et programmes pour accompagner les PME ivoiriennes.",
        "presentation": "Le portail Côte d'Ivoire PME est une source prioritaire pour les entreprises ivoiriennes qui cherchent des appels à projets, de l'accompagnement, une préparation à la levée de fonds ou des programmes de structuration.",
        "eligibility": "Les opportunités publiées ciblent généralement les PME, startups et entreprises ivoiriennes. Les critères varient selon chaque appel: secteur, maturité, chiffre d'affaires, formalisation et capacité de croissance.",
        "funding": "Selon l'appel, l'appui peut prendre la forme d'accompagnement, coaching, mise en relation, préparation à l'investissement ou accès à des partenaires financiers.",
        "calendar": "Source récurrente. Les dates changent selon chaque appel publié par l'agence.",
        "procedure": "Surveiller la page officielle des appels, ouvrir l'appel pertinent, vérifier les critères et déposer le dossier selon les modalités indiquées.",
        "checks": "Vérifier la date limite de l'appel concerné, les secteurs ciblés, les pièces demandées et la nature exacte de l'appui financier.",
    },
    {
        "source_name": "Common Fund for Commodities - appels a propositions",
        "title": "Common Fund for Commodities - appel à propositions pour PME agricoles",
        "organism": "Common Fund for Commodities",
        "organism_type": "institution internationale",
        "country": "Afrique",
        "region": "Afrique de l'Ouest",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "aap",
        "aid_nature": "financement_mixte",
        "sectors": ["agriculture", "agroalimentaire", "commerce", "impact", "chaine de valeur"],
        "beneficiaries": ["pme", "cooperative", "entreprise sociale", "entreprise", "organisation de producteurs"],
        "amount_min": Decimal("300000"),
        "amount_max": Decimal("2000000"),
        "currency": "USD",
        "open_date": date(2026, 4, 1),
        "close_date": date(2026, 10, 1),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.common-fund.org/call-for-proposals",
        "source_raw": "The Common Fund for Commodities invites proposals from SMEs, cooperatives and enterprises active in commodity value chains, with a call deadline indicated for October 2026.",
        "presentation": "Le Common Fund for Commodities finance des projets d'entreprises, coopératives et organisations de producteurs qui améliorent les chaînes de valeur agricoles et les revenus des petits producteurs. C'est pertinent pour des PME ou projets agroalimentaires en Afrique de l'Ouest.",
        "eligibility": "La cible comprend des PME, coopératives, entreprises sociales et organisations actives dans les chaînes de valeur des matières premières ou produits agricoles. Le projet doit avoir un modèle économique crédible et un impact sur les petits producteurs.",
        "funding": "Les tickets indicatifs peuvent aller d'environ 300 000 à 2 000 000 USD selon le type de financement et la structure du projet. Les conditions exactes doivent être confirmées sur l'appel officiel.",
        "calendar": "L'appel en cours est indiqué avec une date limite au 1er octobre 2026.",
        "procedure": "Consulter l'appel officiel, préparer la note conceptuelle, le modèle économique, les impacts attendus et les pièces demandées, puis soumettre via la procédure CFC.",
        "checks": "Confirmer le round exact, la date limite, la devise, les tickets applicables, les pays admissibles et la forme du financement avant candidature.",
    },
]


def _sections(device: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": "presentation", "title": "Présentation", "content": device["presentation"], "confidence": 86, "source": "curation_afrique_round2"},
        {"key": "eligibility", "title": "Pour qui ?", "content": device["eligibility"], "confidence": 82, "source": "curation_afrique_round2"},
        {"key": "funding", "title": "Montant / avantages", "content": device["funding"], "confidence": 80, "source": "curation_afrique_round2"},
        {"key": "calendar", "title": "Calendrier", "content": device["calendar"], "confidence": 78, "source": "curation_afrique_round2"},
        {"key": "procedure", "title": "Démarche", "content": device["procedure"], "confidence": 80, "source": "curation_afrique_round2"},
        {"key": "checks", "title": "Points à vérifier", "content": device["checks"], "confidence": 76, "source": "curation_afrique_round2"},
    ]


def _full_description(device: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"## Présentation\n{device['presentation']}",
            f"## Pour qui ?\n{device['eligibility']}",
            f"## Montant / avantages\n{device['funding']}",
            f"## Calendrier\n{device['calendar']}",
            f"## Démarche\n{device['procedure']}",
            f"## Points à vérifier\n{device['checks']}",
        ]
    )


def _short_description(device: dict[str, Any]) -> str:
    return device["presentation"][:420].rstrip()


async def upsert_source(db, data: dict[str, Any]) -> Source:
    row = await db.execute(select(Source).where(Source.name == data["name"]))
    source = row.scalar_one_or_none()
    if source is None:
        source = Source(**data)
        db.add(source)
        await db.flush()
        return source

    for key, value in data.items():
        setattr(source, key, value)
    return source


async def upsert_device(db, data: dict[str, Any], source: Source) -> str:
    row = await db.execute(select(Device).where(Device.source_url == data["source_url"]))
    device = row.scalar_one_or_none()
    created = False
    if device is None:
        device = Device(source_url=data["source_url"])
        db.add(device)
        created = True

    full_description = _full_description(data)
    payload = {
        "title": data["title"],
        "title_normalized": normalize_title(data["title"]),
        "slug": generate_slug(data["title"]),
        "organism": data["organism"],
        "organism_type": data["organism_type"],
        "country": data["country"],
        "region": data["region"],
        "zone": data["zone"],
        "geographic_scope": data["geographic_scope"],
        "device_type": data["device_type"],
        "aid_nature": data["aid_nature"],
        "sectors": data["sectors"],
        "beneficiaries": data["beneficiaries"],
        "short_description": _short_description(data),
        "full_description": full_description,
        "content_sections_json": _sections(data),
        "ai_rewritten_sections_json": _sections(data),
        "ai_rewrite_status": "done",
        "ai_rewrite_model": "curation_afrique_round2",
        "ai_rewrite_checked_at": NOW,
        "eligibility_criteria": data["eligibility"],
        "funding_details": data["funding"],
        "amount_min": data.get("amount_min"),
        "amount_max": data.get("amount_max"),
        "currency": data.get("currency", "EUR"),
        "open_date": data.get("open_date"),
        "close_date": data.get("close_date"),
        "is_recurring": data.get("is_recurring", False),
        "recurrence_notes": data.get("recurrence_notes"),
        "status": data["status"],
        "source_id": source.id,
        "source_url": data["source_url"],
        "source_raw": data["source_raw"],
        "language": "fr",
        "keywords": list(dict.fromkeys([data["country"], data["organism"], *data["sectors"]])),
        "confidence_score": 90,
        "ai_readiness_score": 88,
        "ai_readiness_label": "pret_pour_recommandation_ia",
        "ai_readiness_reasons": ["source officielle", "contenu curé", "sections métier complètes"],
        "validation_status": "auto_published",
        "last_verified_at": NOW,
        "updated_at": NOW,
    }
    payload["completeness_score"] = compute_completeness(payload)
    quality = compute_user_quality(payload)
    payload["user_quality_score"] = quality.score
    payload["user_quality_decision"] = quality.decision
    payload["user_quality_reasons"] = quality.reasons

    for key, value in payload.items():
        setattr(device, key, value)
    if created:
        device.first_seen_at = NOW
        device.created_at = NOW

    return "created" if created else "updated"


async def publish_foname_if_present(db) -> bool:
    row = await db.execute(select(Device).where(Device.title.ilike("%FONAME%Côte d'Ivoire%")))
    device = row.scalar_one_or_none()
    if not device:
        row = await db.execute(select(Device).where(Device.title.ilike("%FONAME Cote d'Ivoire%")))
        device = row.scalar_one_or_none()
    if not device:
        return False

    device.title = "FONAME Côte d'Ivoire - appel à projets énergie"
    device.title_normalized = normalize_title(device.title)
    device.slug = generate_slug(device.title)
    device.device_type = "aap"
    device.status = "recurring"
    device.is_recurring = True
    device.validation_status = "auto_published"
    device.user_quality_decision = "publish_with_caution"
    device.user_quality_score = 82
    device.user_quality_reasons = ["source_fiable", "contenu_lisible", "action_possible", "date_a_confirmer"]
    device.ai_readiness_label = "utilisable_avec_prudence"
    device.ai_readiness_score = max(device.ai_readiness_score or 0, 80)
    device.updated_at = NOW
    return True


async def main():
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            source = await upsert_source(db, source_data)
            sources[source_data["name"]] = source

        counts = {"created": 0, "updated": 0}
        for device_data in DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        foname_updated = await publish_foname_if_present(db)
        await db.commit()
        print({"sources": len(sources), **counts, "foname_updated": foname_updated})


if __name__ == "__main__":
    asyncio.run(main())
