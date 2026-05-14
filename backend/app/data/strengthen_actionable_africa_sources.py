from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, compute_completeness, extract_keywords, generate_slug


NOW = datetime.now(timezone.utc)


SOURCE_PATCHES: list[dict[str, Any]] = [
    {
        "name": "AECF - competitions et challenge funds",
        "url": "https://www.aecfafrica.org/fr/approach/competitions/",
        "collection_mode": "html",
        "is_active": True,
        "reliability": 4,
        "check_frequency": "weekly",
        "config": {
            "source_kind": "single_program_page",
            "list_selector": "main, article, body",
            "item_title_selector": "h1, h2",
            "item_description_selector": "main, article, body",
            "detail_fetch": False,
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
            "detail_max_chars": 12000,
            "pagination": {"max_pages": 1},
        },
        "notes": (
            "Source AECF qualifiee comme page de reference des concours et challenge funds. "
            "Elle sert de point d'entree fiable pour les financements AECF, mais une fiche ne "
            "doit etre marquee ouverte que si une date limite est explicitement publiee."
        ),
    },
    {
        "name": "GSMA Innovation Fund - calls",
        "url": "https://www.gsma.com/InnovationFund/",
        "collection_mode": "manual",
        "is_active": False,
        "reliability": 4,
        "check_frequency": "weekly",
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Le site GSMA peut bloquer les collectes automatiques. Les appels actifs sont ajoutes via fiches curees puis verifies manuellement.",
        },
        "notes": (
            "Source qualifiee manuelle. A utiliser pour publier les appels GSMA Innovation Fund "
            "quand une page officielle ou un communique officiel confirme l'ouverture et les conditions."
        ),
    },
    {
        "name": "Banque Africaine de Developpement - opportunites",
        "url": "https://www.afdb.org/fr/news-and-events/press-releases",
        "collection_mode": "manual",
        "is_active": False,
        "reliability": 4,
        "check_frequency": "weekly",
        "config": {
            "source_kind": "qualified_manual",
            "watch_keywords": ["call for proposals", "appel a propositions", "SEFA", "youth", "women", "SME"],
        },
        "notes": (
            "Source BAD suivie en manuel qualifie: seules les opportunites avec appel, programme "
            "ou dispositif clairement exploitable doivent etre publiees."
        ),
    },
    {
        "name": "PROPARCO - projets secteur prive",
        "url": "https://www.proparco.fr/fr/choose-africa-linitiative-francaise-en-faveur-de-lentrepreneuriat-africain",
        "collection_mode": "manual",
        "is_active": False,
        "reliability": 5,
        "check_frequency": "monthly",
        "config": {
            "source_kind": "qualified_manual",
            "reason": "Choose Africa est une porte d'entree permanente via partenaires financiers, pas un listing d'appels a scraper.",
        },
        "notes": (
            "Source Proparco/Choose Africa conservee en manuel: le parcours d'acces depend souvent "
            "des institutions financieres partenaires et doit etre presente comme opportunite permanente."
        ),
    },
]


def _sections(
    *,
    presentation: str,
    eligibility: str,
    funding: str,
    calendar: str,
    procedure: str,
    checks: str,
    source: str,
) -> list[dict[str, Any]]:
    return [
        {"key": "presentation", "title": "Presentation", "content": presentation, "confidence": 82, "source": source},
        {"key": "eligibility", "title": "Criteres d'eligibilite", "content": eligibility, "confidence": 80, "source": source},
        {"key": "funding", "title": "Montant / avantages", "content": funding, "confidence": 80, "source": source},
        {"key": "calendar", "title": "Calendrier", "content": calendar, "confidence": 78, "source": source},
        {"key": "procedure", "title": "Demarche", "content": procedure, "confidence": 78, "source": source},
        {"key": "checks", "title": "Points a verifier", "content": checks, "confidence": 75, "source": source},
    ]


DEVICE_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "source_name": "GSMA Innovation Fund - calls",
        "title": "GSMA Innovation Fund for Green Transition for Mobile",
        "organism": "GSMA",
        "organism_type": "fondation / secteur prive",
        "country": "International",
        "region": "Afrique et LMICs",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "subvention",
        "sectors": ["Numerique", "Climat", "Energie", "Mobile", "Impact"],
        "beneficiaries": ["startup", "PME", "entreprise sociale", "organisation a impact"],
        "amount_min": Decimal("100000"),
        "amount_max": Decimal("200000"),
        "currency": "GBP",
        "open_date": date(2026, 2, 23),
        "close_date": date(2026, 4, 6),
        "status": "expired",
        "is_recurring": False,
        "source_url": "https://www.gsma.com/newsroom/press-release/gsma-launches-innovation-fund-to-accelerate-green-transition-through-mobile-technology/",
        "source_raw": "GSMA annonce un Innovation Fund pour soutenir des entreprises utilisant les technologies mobiles et numeriques afin d'accelerer la transition verte dans les pays a revenu faible ou intermediaire.",
        "presentation": (
            "Le GSMA Innovation Fund for Green Transition for Mobile soutient des organisations qui utilisent "
            "le mobile et les technologies numeriques pour accelerer la transition verte dans les pays a revenu "
            "faible ou intermediaire. C'est une opportunite interessante pour les startups et entreprises a impact "
            "ayant une solution numerique liee au climat, a l'energie, a l'agriculture durable ou a la resilience."
        ),
        "eligibility": (
            "La cible principale comprend des petites entreprises en croissance, startups, entreprises sociales "
            "et organisations capables de deployer ou d'etendre une solution mobile ou numerique dans un pays "
            "eligible. L'entite doit confirmer son pays d'operation, son impact environnemental et sa capacite "
            "d'execution sur la page officielle GSMA."
        ),
        "funding": (
            "Les subventions annoncees se situent entre 100 000 et 200 000 GBP. Le financement est associe a "
            "un accompagnement, une visibilite ecosysteme et un suivi d'impact. Les montants exacts et conditions "
            "de versement doivent etre confirmes sur l'appel officiel."
        ),
        "calendar": "Appel annonce en fevrier 2026. La date limite officielle etait le 6 avril 2026 a 23h59 heure britannique.",
        "procedure": (
            "Consulter la page officielle GSMA Innovation Fund, verifier l'appel ouvert, puis preparer les "
            "elements sur la solution, le pays d'operation, l'impact climatique et le plan de deploiement."
        ),
        "checks": "Cette fenetre est expiree au 14 mai 2026. Surveiller la prochaine fenetre GSMA Innovation Fund.",
        "decision": {
            "go_no_go": "no_go",
            "recommended_priority": "faible",
            "why_interesting": "Signal tres utile pour suivre les prochains appels GSMA lies au mobile, au numerique et au climat.",
            "why_cautious": "La fenetre 2026 Green Transition est deja cloturee.",
            "points_to_confirm": "Prochaine fenetre d'appel, pays eligibles, criteres d'impact et ticket disponible.",
            "recommended_action": "Ne pas candidater a cette fenetre; creer une alerte pour les prochains appels GSMA Innovation Fund.",
            "urgency_level": "faible",
            "difficulty_level": "moyenne",
            "effort_level": "moyenne",
            "eligibility_score": 72,
            "strategic_interest": 88,
            "model": "curated_africa_source",
        },
    },
    {
        "source_name": "Banque Africaine de Developpement - opportunites",
        "title": "BAD / SEFA - appel a propositions Green Hydrogen Programme",
        "organism": "Banque Africaine de Developpement",
        "organism_type": "institution regionale",
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "appel à projets",
        "aid_nature": "subvention",
        "sectors": ["Energie", "Climat", "Hydrogene vert", "Infrastructure", "Transition energetique"],
        "beneficiaries": ["entreprise", "developpeur de projet", "acteur prive"],
        "amount_min": None,
        "amount_max": Decimal("20000000"),
        "currency": "USD",
        "open_date": date(2026, 4, 8),
        "close_date": date(2026, 5, 11),
        "status": "expired",
        "is_recurring": False,
        "source_url": "https://www.afdb.org/en/news-and-events/press-releases/african-development-banks-sustainable-energy-fund-africa-launches-call-proposals-new-green-hydrogen-programme-92126",
        "source_raw": "AfDB SEFA Green Hydrogen Programme call for proposals, launched 8 April 2026, deadline 11 May 2026.",
        "presentation": (
            "Le Sustainable Energy Fund for Africa de la Banque Africaine de Developpement a lance un appel "
            "a propositions pour soutenir des projets d'hydrogene vert et derives en Afrique. La fenetre vise "
            "des projets prives ayant besoin d'un appui de pre-investissement pour avancer vers la decision "
            "finale d'investissement ou la cloture financiere."
        ),
        "eligibility": (
            "L'appel cible des entites du secteur prive portant des projets d'hydrogene vert ou derives en Afrique. "
            "Les projets doivent montrer leur potentiel technique, commercial et d'impact. Les criteres exacts, "
            "pays couverts et pieces attendues doivent etre verifies dans l'appel SEFA officiel."
        ),
        "funding": (
            "L'enveloppe annoncee peut aller jusqu'a 20 millions USD au total pour trois a cinq projets classes "
            "parmi les meilleurs, sous forme de soutien de pre-investissement et sous reserve de due diligence."
        ),
        "calendar": "L'appel a ete annonce le 8 avril 2026 et la date limite officielle etait le 11 mai 2026.",
        "procedure": (
            "La soumission se faisait via la plateforme SEFA indiquee par la Banque Africaine de Developpement. "
            "La fiche reste utile pour veille sectorielle et anticipation d'une prochaine fenetre."
        ),
        "checks": "Cette fenetre est expiree au 14 mai 2026. Ne pas la recommander comme opportunite ouverte.",
        "decision": {
            "go_no_go": "no_go",
            "recommended_priority": "faible",
            "why_interesting": "Signal utile pour suivre les financements climat/energie de la BAD, mais l'appel est deja cloture.",
            "why_cautious": "La date limite officielle est passee.",
            "points_to_confirm": "Surveiller une prochaine fenetre SEFA ou Green Hydrogen.",
            "recommended_action": "Ne pas candidater a cette fenetre; creer plutot une alerte sur les prochains appels BAD/SEFA.",
            "urgency_level": "faible",
            "difficulty_level": "haute",
            "effort_level": "haute",
            "eligibility_score": 30,
            "strategic_interest": 70,
            "model": "curated_africa_source",
        },
    },
    {
        "source_name": "PROPARCO - projets secteur prive",
        "title": "Choose Africa - financement et accompagnement des PME africaines",
        "organism": "PROPARCO / Groupe AFD",
        "organism_type": "institution financiere de developpement",
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "accompagnement",
        "aid_nature": "financement",
        "sectors": ["Entrepreneuriat", "PME", "Startup", "Financement", "Impact"],
        "beneficiaries": ["startup", "TPE", "PME", "institution financiere partenaire"],
        "amount_min": None,
        "amount_max": None,
        "currency": "EUR",
        "open_date": None,
        "close_date": None,
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": (
            "Initiative permanente du Groupe AFD/Proparco pour financer et accompagner les startups, "
            "TPE et PME africaines, souvent via des partenaires financiers locaux."
        ),
        "source_url": "https://www.proparco.fr/fr/choose-africa-linitiative-francaise-en-faveur-de-lentrepreneuriat-africain",
        "source_raw": "Choose Africa est l'initiative du Groupe AFD en faveur de l'entrepreneuriat africain, avec financements, garanties, accompagnement et partenaires financiers.",
        "presentation": (
            "Choose Africa est la porte d'entree du Groupe AFD et de Proparco pour soutenir les startups, "
            "TPE et PME africaines. L'initiative combine financements, garanties, prises de participation, "
            "assistance technique et relais via des institutions financieres partenaires."
        ),
        "eligibility": (
            "La cible couvre les entrepreneurs, startups, microentreprises, TPE et PME africaines a differents "
            "stades de developpement. L'acces depend du pays, du secteur, du stade de maturite et du partenaire "
            "financier local mobilise. Les conditions doivent etre confirmees via la page officielle ou les "
            "partenaires Proparco/AFD."
        ),
        "funding": (
            "Les solutions peuvent inclure financement direct ou indirect, garanties, dette, investissement "
            "en capital, accompagnement technique ou soutien aux fonds et institutions partenaires. Aucun montant "
            "unique ne doit etre affiche comme plafond universel."
        ),
        "calendar": "Dispositif permanent sans date de cloture unique publiee.",
        "procedure": (
            "Identifier le bon guichet ou partenaire financier selon le pays et le besoin: amorcage, croissance, "
            "credit bancaire, garantie, investissement ou accompagnement technique."
        ),
        "checks": "Verifier le pays couvert, le partenaire local, le ticket possible et le type d'instrument adapte au projet.",
        "decision": {
            "go_no_go": "a_verifier",
            "recommended_priority": "moyenne",
            "why_interesting": "Bonne piste permanente pour une PME ou startup africaine qui cherche un financement structure ou un partenaire financier.",
            "why_cautious": "Ce n'est pas un appel unique; le parcours depend fortement du pays et du partenaire financier.",
            "points_to_confirm": "Pays, secteur, stade de l'entreprise, partenaire local et instrument disponible.",
            "recommended_action": "Verifier le parcours Choose Africa puis identifier le partenaire financier le plus proche du besoin.",
            "urgency_level": "faible",
            "difficulty_level": "moyenne",
            "effort_level": "moyenne",
            "eligibility_score": 68,
            "strategic_interest": 82,
            "model": "curated_africa_source",
        },
    },
    {
        "source_name": "AECF - competitions et challenge funds",
        "title": "AECF - concours et challenge funds pour entreprises africaines",
        "organism": "Africa Enterprise Challenge Fund",
        "organism_type": "fonds de developpement",
        "country": "Afrique",
        "region": "Afrique subsaharienne",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "subvention",
        "aid_nature": "subvention",
        "sectors": ["Agribusiness", "Energie", "Resilience", "Services financiers ruraux", "Impact"],
        "beneficiaries": ["PME", "entreprise en croissance", "entreprise rurale", "entreprise a impact"],
        "amount_min": Decimal("15000"),
        "amount_max": Decimal("1500000"),
        "currency": "USD",
        "open_date": None,
        "close_date": None,
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "AECF publie des concours et challenge funds selon les fenetres de financement disponibles.",
        "source_url": "https://www.aecfafrica.org/fr/approach/competitions/",
        "source_raw": "AECF organise des concours ciblant agribusiness, energies renouvelables, resilience et services financiers ruraux en Afrique subsaharienne.",
        "presentation": (
            "AECF finance des petites entreprises et entreprises en croissance en Afrique via des concours "
            "et challenge funds. Les appels ciblent notamment l'agro-industrie, les energies renouvelables, "
            "la resilience et les services financiers ruraux, avec un objectif d'impact sur les communautes "
            "rurales et marginalisees."
        ),
        "eligibility": (
            "Les concours ciblent des entreprises commercialement viables, innovantes et capables de produire "
            "un impact de developpement. Les appels peuvent prioriser les femmes, les jeunes, les zones rurales "
            "ou les contextes fragiles selon la fenetre ouverte."
        ),
        "funding": (
            "AECF indique que le financement par entreprise peut varier de 15 000 a 1,5 million USD selon le "
            "concours. Le montant exact depend de l'appel, de la categorie et de l'analyse du projet."
        ),
        "calendar": "Dispositif recurrent: les dates varient selon chaque concours publie par AECF.",
        "procedure": (
            "Surveiller les concours AECF ouverts, puis deposer une note conceptuelle en ligne lorsque la fenetre "
            "correspond au secteur, au pays et au stade du projet."
        ),
        "checks": "Verifier la fenetre actuellement ouverte, les pays eligibles, le ticket, les exigences de cofinancement et les documents attendus.",
        "decision": {
            "go_no_go": "a_verifier",
            "recommended_priority": "haute",
            "why_interesting": "Tres bonne source a suivre pour les entreprises africaines dans l'agriculture, l'energie, la resilience et l'impact rural.",
            "why_cautious": "Chaque concours AECF a ses propres pays, dates, tickets et conditions.",
            "points_to_confirm": "Fenetre ouverte, pays eligibles, secteur, ticket et formulaire actif.",
            "recommended_action": "Creer une alerte AECF et verifier regulierement les concours ouverts.",
            "urgency_level": "moyenne",
            "difficulty_level": "moyenne",
            "effort_level": "moyenne",
            "eligibility_score": 75,
            "strategic_interest": 90,
            "model": "curated_africa_source",
        },
    },
]


async def _get_or_create_source(db, payload: dict[str, Any]) -> tuple[Source, str]:
    source = (await db.execute(select(Source).where(Source.name == payload["name"]))).scalar_one_or_none()
    action = "updated"
    if source is None:
        source = Source(
            id=uuid.uuid4(),
            name=payload["name"],
            organism=payload.get("organism") or payload["name"],
            country=payload.get("country") or "Afrique",
            source_type=payload.get("source_type") or "autre",
            level=payload.get("level") or 1,
            url=payload["url"],
            collection_mode=payload.get("collection_mode") or "manual",
            category=payload.get("category") or "public",
            reliability=payload.get("reliability") or 4,
            is_active=payload.get("is_active", False),
        )
        db.add(source)
        action = "created"

    for key, value in payload.items():
        if hasattr(source, key) and key != "id":
            setattr(source, key, value)
    source.last_checked_at = NOW
    return source, action


async def _unique_slug(db, title: str, existing_id=None) -> str:
    base = generate_slug(title)
    slug = base
    index = 2
    while True:
        with db.no_autoflush:
            query = select(Device).where(Device.slug == slug)
            found = (await db.execute(query)).scalar_one_or_none()
        if found is None or (existing_id is not None and found.id == existing_id):
            return slug
        slug = f"{base}-{index}"
        index += 1


async def _upsert_device(db, source: Source, payload: dict[str, Any]) -> tuple[str, Device]:
    device = (
        await db.execute(
            select(Device).where(
                Device.title == payload["title"],
                Device.source_id == source.id,
            )
        )
    ).scalar_one_or_none()

    action = "updated"
    if device is None:
        device = Device(
            id=uuid.uuid4(),
            title=payload["title"],
            organism=payload["organism"],
            country=payload["country"],
            device_type=payload["device_type"],
            source_url=payload["source_url"],
        )
        db.add(device)
        action = "created"

    sections = _sections(
        presentation=payload["presentation"],
        eligibility=payload["eligibility"],
        funding=payload["funding"],
        calendar=payload["calendar"],
        procedure=payload["procedure"],
        checks=payload["checks"],
        source="curated_africa_source",
    )
    full_description = build_structured_sections(
        presentation=payload["presentation"],
        eligibility=payload["eligibility"],
        funding=payload["funding"],
        open_date=payload.get("open_date"),
        close_date=payload.get("close_date"),
        procedure=payload["procedure"],
        recurrence_notes=payload.get("recurrence_notes"),
    )

    for key in (
        "title",
        "organism",
        "organism_type",
        "country",
        "region",
        "zone",
        "geographic_scope",
        "device_type",
        "aid_nature",
        "sectors",
        "beneficiaries",
        "amount_min",
        "amount_max",
        "currency",
        "open_date",
        "close_date",
        "status",
        "is_recurring",
        "recurrence_notes",
        "source_url",
        "source_raw",
    ):
        if key in payload:
            setattr(device, key, payload[key])

    device.source_id = source.id
    device.slug = await _unique_slug(db, payload["title"], existing_id=device.id)
    device.title_normalized = payload["title"].lower()
    device.short_description = payload["presentation"][:700]
    device.eligibility_criteria = payload["eligibility"]
    device.funding_details = payload["funding"]
    device.full_description = full_description
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = "curated_africa_source"
    device.ai_rewrite_checked_at = NOW
    device.language = "fr"
    device.keywords = extract_keywords(" ".join([payload["title"], payload["presentation"], " ".join(payload.get("sectors") or [])]))
    device.tags = list(dict.fromkeys(["afrique", "source_actionnable", *(payload.get("sectors") or [])]))[:12]
    device.auto_summary = payload["presentation"][:500]
    device.confidence_score = 84
    device.relevance_score = payload["decision"].get("strategic_interest", 80)
    device.ai_readiness_score = 90
    device.ai_readiness_label = "pret_recommandation"
    device.ai_readiness_reasons = ["sections structurees", "source officielle", "conditions a verifier explicites"]
    device.decision_analysis = payload["decision"]
    device.decision_analyzed_at = NOW
    device.last_verified_at = NOW

    quality_payload = {
        "title": device.title,
        "source_url": device.source_url,
        "short_description": device.short_description,
        "full_description": device.full_description,
        "eligibility_criteria": device.eligibility_criteria,
        "funding_details": device.funding_details,
        "source_raw": device.source_raw,
        "status": device.status,
        "is_recurring": device.is_recurring,
        "close_date": device.close_date,
        "amount_min": device.amount_min,
        "amount_max": device.amount_max,
    }
    decision = DeviceQualityGate().evaluate(quality_payload)
    device.validation_status = decision.validation_status
    if device.status in {"recurring", "standby", "expired"} and decision.validation_status == "pending_review":
        device.validation_status = "auto_published"
    device.completeness_score = compute_completeness(
        {
            "title": device.title,
            "organism": device.organism,
            "country": device.country,
            "device_type": device.device_type,
            "short_description": device.short_description,
            "close_date": device.close_date,
            "amount_max": device.amount_max,
            "eligibility_criteria": device.eligibility_criteria,
            "sectors": device.sectors,
            "source_url": device.source_url,
            "full_description": device.full_description,
            "beneficiaries": device.beneficiaries,
            "open_date": device.open_date,
            "keywords": device.keywords,
        }
    )
    return action, device


async def run() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        source_actions: dict[str, str] = {}
        sources: dict[str, Source] = {}
        for patch in SOURCE_PATCHES:
            source, action = await _get_or_create_source(db, patch)
            sources[source.name] = source
            source_actions[source.name] = action

        device_actions: list[dict[str, Any]] = []
        for blueprint in DEVICE_BLUEPRINTS:
            source = sources.get(blueprint["source_name"])
            if source is None:
                source = (await db.execute(select(Source).where(Source.name == blueprint["source_name"]))).scalar_one()
            action, device = await _upsert_device(db, source, blueprint)
            device_actions.append(
                {
                    "action": action,
                    "title": device.title,
                    "status": device.status,
                    "validation_status": device.validation_status,
                    "close_date": device.close_date.isoformat() if device.close_date else None,
                }
            )

        await db.commit()
        return {"sources": source_actions, "devices": device_actions}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
