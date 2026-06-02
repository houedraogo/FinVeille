from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness, normalize_title


UPDATES: dict[str, dict[str, str]] = {
    "55fabe8e-f336-42d1-9be5-c467dbfafcdd": {
        "short": "Investing for Employment finance des projets d'investissement capables de créer des emplois durables en Côte d'Ivoire. Cette fiche est surtout utile pour les entreprises ou partenaires qui préparent un projet déjà structuré.",
        "eligibility": "Publics à vérifier : entreprises, PME, organisations professionnelles ou partenaires de mise en oeuvre actifs en Côte d'Ivoire. Le projet doit généralement démontrer un potentiel de création d'emplois, une capacité de cofinancement et une faisabilité opérationnelle.",
        "funding": "L'aide peut prendre la forme d'une subvention ou d'un cofinancement. Les montants, dépenses éligibles, taux de prise en charge et obligations de reporting doivent être confirmés dans l'appel officiel.",
    },
    "982d2783-ede4-4f50-85e4-5858c50ab67a": {
        "short": "Digital Energy Challenge 2026 cible les PME et organisations qui développent des solutions numériques pour l'accès à l'énergie en Afrique. L'opportunité est pertinente pour les projets combinant innovation, énergie et impact climatique.",
        "eligibility": "Publics à vérifier : PME, startups, opérateurs énergétiques ou structures innovantes actives en Afrique. Les projets doivent être liés à l'énergie digitale, avec un besoin d'appui financier, technique ou de visibilité.",
        "funding": "Le programme peut combiner dotation, accompagnement technique, mise en relation et visibilité auprès d'acteurs du secteur énergie. Les montants et conditions exactes doivent être confirmés sur la page officielle.",
    },
    "533d8f64-6426-49e7-973d-450743d95cf6": {
        "short": "L'A2D Facility de l'UNIDO soutient des projets de démonstration dans des pays éligibles à l'aide publique au développement. Cette opportunité peut intéresser des structures industrielles ou innovantes capables de tester une solution à impact.",
        "eligibility": "Publics à vérifier : entreprises, consortiums, institutions ou partenaires techniques portant un projet de démonstration. Les critères précis dépendent du pays, du secteur et du niveau de maturité de la solution.",
        "funding": "L'appui peut couvrir une partie des coûts de démonstration, d'assistance technique ou de mise en oeuvre. Les montants, dépenses admissibles et obligations de cofinancement doivent être vérifiés dans l'appel officiel.",
    },
    "aec02e0e-41c1-495b-9142-d51af42027ca": {
        "short": "SOE Bénin 2026 est un rendez-vous utile pour les entrepreneurs qui cherchent des contacts investisseurs, des partenariats ou de la visibilité business. La valeur principale est la mise en relation, plus que la subvention directe.",
        "eligibility": "Publics à vérifier : entrepreneurs, PME, startups et porteurs de projets basés ou actifs au Bénin. Vérifier les conditions d'inscription, le profil attendu et les éventuelles catégories de participants.",
        "funding": "L'avantage principal est l'accès à des rencontres, conseils, partenaires et opportunités d'affaires. Aucun montant direct n'est garanti dans la fiche actuelle ; il faut confirmer les avantages exacts sur la source officielle.",
    },
    "2c2efc94-2b22-404d-9bb0-e782261419a0": {
        "short": "Le PIICC Bénin accompagne les acteurs des industries culturelles et créatives. Cette opportunité peut aider à structurer un projet culturel, renforcer le modèle économique et accéder à un réseau d'accompagnement.",
        "eligibility": "Publics à vérifier : entrepreneurs culturels, artistes, structures créatives, porteurs de projets ICC et jeunes entreprises basées ou actives au Bénin. Les critères peuvent varier selon les appels ou cohortes.",
        "funding": "L'appui est principalement un accompagnement : incubation, conseils, formation, réseau et préparation au financement. Les éventuelles dotations ou prises en charge doivent être confirmées sur la source officielle.",
    },
    "618ac411-1264-4215-917d-dbfb01d2a87c": {
        "short": "Le FDCT Burkina Faso soutient des projets dans la culture, le tourisme, les arts, l'audiovisuel et le patrimoine. Cette fiche est utile pour les acteurs créatifs qui cherchent un guichet public ou semi-public de financement.",
        "eligibility": "Publics à vérifier : artistes, entreprises culturelles, associations, opérateurs touristiques et porteurs de projets créatifs au Burkina Faso. Les conditions varient selon les appels, catégories et pièces demandées.",
        "funding": "Le soutien peut prendre la forme d'une subvention, d'un appui à projet ou d'un accompagnement selon les fenêtres ouvertes. Le montant, les plafonds et les dépenses éligibles doivent être confirmés auprès du FDCT.",
    },
    "aeaee807-c75b-45c9-a8f5-641e0ccf3f92": {
        "short": "Le FNDA Bénin finance ou facilite l'accès au financement pour les investissements agricoles et les services non financiers. Cette opportunité est pertinente pour les acteurs de l'agriculture et de l'agroalimentaire.",
        "eligibility": "Publics à vérifier : exploitants, coopératives, PME agricoles, transformateurs, prestataires de services agricoles et organisations professionnelles au Bénin. Les critères dépendent du guichet et du type de projet.",
        "funding": "L'appui peut couvrir des investissements agricoles, du conseil, des services non financiers ou un cofinancement. Les montants, taux et conditions doivent être vérifiés sur les appels ou guichets FNDA actifs.",
    },
    "8b6ab2dc-7eed-46ba-ab38-59174dfef050": {
        "short": "Le programme EdTech de la Mastercard Foundation au Bénin vise des solutions éducatives numériques à potentiel d'impact. Il peut intéresser les startups et équipes qui améliorent l'accès, la qualité ou l'employabilité par l'éducation.",
        "eligibility": "Publics à vérifier : startups edtech, entrepreneurs numériques, organisations éducatives et porteurs de solutions innovantes au Bénin. Le stade du projet, l'impact attendu et les critères de sélection doivent être confirmés.",
        "funding": "L'avantage peut inclure accompagnement, mentorat, visibilité, accès à un réseau et éventuellement financement selon les cohortes. Les montants et modalités doivent être confirmés sur la source officielle.",
    },
    "3dd029bc-2e9a-4db1-b6c1-8ffe4b732806": {
        "short": "Le FAARF appuie les femmes au Burkina Faso qui développent des activités génératrices de revenus. Cette opportunité est pertinente pour financer de petits projets entrepreneuriaux dans le commerce, l'artisanat ou l'agriculture.",
        "eligibility": "Publics à vérifier : femmes entrepreneures, groupements féminins et porteuses d'activités génératrices de revenus au Burkina Faso. Les conditions d'accès, garanties éventuelles et pièces à fournir doivent être confirmées localement.",
        "funding": "L'appui prend généralement la forme d'un crédit ou d'un financement de proximité. Les montants, taux, échéances et modalités de remboursement doivent être confirmés auprès du FAARF.",
    },
    "384ef8b4-6784-4319-a2cf-c9ed49b4ac88": {
        "short": "Nice African Talents Awards valorise de jeunes entrepreneurs en Côte d'Ivoire et en Afrique. L'opportunité peut apporter visibilité, réseau et soutien à des projets entrepreneuriaux ou innovants.",
        "eligibility": "Publics à vérifier : jeunes entrepreneurs, startups, porteurs de projets innovants et initiatives à impact. Les catégories, limites d'âge, pays éligibles et critères de sélection doivent être confirmés sur la source officielle.",
        "funding": "L'avantage peut inclure un prix, de la visibilité, du mentorat ou des opportunités de partenariat. Les dotations financières éventuelles et leur montant doivent être confirmés dans le règlement officiel.",
    },
    "4b3bb522-7607-47e0-8de9-98d6bbccc766": {
        "short": "L'AFP-PME Burkina Faso accompagne et finance les petites et moyennes entreprises. Cette fiche est utile pour les PME qui cherchent un appui institutionnel pour structurer, financer ou développer leur activité.",
        "eligibility": "Publics à vérifier : TPE, PME, promoteurs et entrepreneurs basés au Burkina Faso. Les critères peuvent dépendre du secteur, de la maturité de l'entreprise, du besoin de financement et des garanties disponibles.",
        "funding": "L'appui peut prendre la forme de prêt, accompagnement, conseil ou facilitation de financement. Les montants, conditions de remboursement et pièces demandées doivent être confirmés auprès de l'AFP-PME.",
    },
    "e6ac051e-12ae-40f6-be04-e5aa6a632cc2": {
        "short": "Le programme CECI MTWW soutient l'expansion commerciale des entreprises féminines en Afrique de l'Ouest. Il peut aider des entrepreneures à se renforcer, accéder à de nouveaux marchés et structurer leur croissance.",
        "eligibility": "Publics à vérifier : entreprises dirigées par des femmes, PME, coopératives ou structures engagées dans le commerce, l'export ou l'agroalimentaire. Les pays et critères précis doivent être vérifiés sur la source officielle.",
        "funding": "L'appui peut inclure formation, accompagnement, mise en relation, accès marché et éventuellement soutien financier selon les activités. Les avantages exacts doivent être confirmés auprès du programme.",
    },
    "45583515-d097-44da-bcb9-05be2dd6de19": {
        "short": "SEFAFI accompagne les entreprises au Burkina Faso dans la préparation et la facilitation de leur financement. Cette opportunité est utile pour les PME qui veulent améliorer leur dossier et dialoguer avec des financeurs.",
        "eligibility": "Publics à vérifier : PME, entrepreneurs et porteurs de projets au Burkina Faso ayant un besoin de financement ou de structuration. Les conditions d'accès et la documentation attendue doivent être confirmées auprès de la Maison de l'Entreprise.",
        "funding": "L'avantage principal est l'accompagnement vers le financement : diagnostic, préparation du dossier, orientation et mise en relation. Le programme ne garantit pas automatiquement l'obtention d'un financement.",
    },
    "b99825ef-9236-41a5-8910-aa8230709e5d": {
        "short": "Moov Innovation Côte d'Ivoire est un concours destiné aux startups et solutions digitales à impact. Il peut offrir visibilité, accompagnement et opportunités de partenariat dans l'écosystème numérique.",
        "eligibility": "Publics à vérifier : startups, entrepreneurs numériques, porteurs de solutions innovantes et projets à impact social en Côte d'Ivoire. Vérifier les catégories, dates et conditions de candidature sur la source officielle.",
        "funding": "L'avantage peut inclure prix, accompagnement, visibilité ou accès à un réseau. Les dotations financières et conditions exactes doivent être confirmées dans le règlement du concours.",
    },
    "b71c38a9-f2ac-496e-96ea-7b40e1971c22": {
        "short": "Le partenariat FIRCA - NSIA Banque CI facilite le financement de PME actives dans l'agro-transformation et les chaînes de valeur agricoles. Il est pertinent pour les entreprises qui ont un besoin de crédit ou de structuration financière.",
        "eligibility": "Publics à vérifier : PME agricoles, transformateurs, coopératives ou entreprises liées aux chaînes de valeur en Côte d'Ivoire. Les conditions bancaires, garanties et secteurs ciblés doivent être confirmés avec la source officielle.",
        "funding": "L'appui peut prendre la forme d'un prêt, d'une facilitation bancaire ou d'un accompagnement financier. Les montants, taux, garanties et modalités de remboursement doivent être confirmés auprès des organismes concernés.",
    },
    "a609de66-7791-404c-b18e-f747c955acdf": {
        "short": "Yello Startup Côte d'Ivoire accompagne des entrepreneurs et startups numériques. Cette opportunité peut aider à renforcer une solution digitale, accéder à du mentorat et gagner en visibilité.",
        "eligibility": "Publics à vérifier : startups, entrepreneurs digitaux, porteurs de solutions innovantes et jeunes entreprises technologiques en Côte d'Ivoire. Les critères de sélection et dates de candidature doivent être confirmés.",
        "funding": "L'appui peut inclure accompagnement, mentorat, visibilité, accès réseau et éventuellement prix ou avantages techniques. Les dotations financières éventuelles doivent être confirmées sur la source officielle.",
    },
    "a921df27-da9c-4fbb-9078-ec4a5fd3b89c": {
        "short": "Le Fonds Challenge LuxAid Bénin cofinance des entreprises innovantes dans des secteurs comme l'agritech, l'edtech, la fintech, la healthtech, le tourisme ou le numérique. Il est pertinent pour les projets à impact prêts à se structurer.",
        "eligibility": "Publics à vérifier : entreprises innovantes, startups et PME basées ou actives au Bénin. Les critères portent généralement sur l'innovation, l'impact, la capacité de mise en oeuvre et la viabilité du modèle.",
        "funding": "L'appui peut prendre la forme d'un cofinancement ou d'une subvention challenge. Les montants, taux de cofinancement, dépenses éligibles et conditions de décaissement doivent être confirmés sur l'appel officiel.",
    },
    "b507806d-6052-4b27-ab7e-40a1413b1380": {
        "short": "AFAWA est une initiative de la Banque africaine de développement qui facilite l'accès au financement pour les femmes entrepreneures en Afrique. Elle agit surtout via des partenaires financiers et programmes associés.",
        "eligibility": "Publics à vérifier : femmes entrepreneures, PME dirigées par des femmes, institutions financières partenaires et organisations d'appui. Les conditions concrètes dépendent du pays et du partenaire local.",
        "funding": "L'appui peut prendre la forme de garanties, lignes de crédit, accompagnement ou facilitation de financement. Les montants et modalités doivent être vérifiés auprès des partenaires AFAWA actifs dans le pays ciblé.",
    },
    "d05f428a-25e1-404d-80c2-cd4f30b6665f": {
        "short": "Young Africa Works de la Mastercard Foundation soutient l'emploi des jeunes en Afrique à travers des programmes de formation, entrepreneuriat et partenariats. Cette fiche doit être suivie comme signal de programme, avec appels à confirmer localement.",
        "eligibility": "Publics à vérifier : jeunes, entrepreneurs, organisations de formation, PME et partenaires de mise en oeuvre selon les programmes pays. Les critères varient selon les appels, cohortes et partenaires locaux.",
        "funding": "L'appui peut inclure subventions, accompagnement, formation, partenariats ou financement via des programmes locaux. Les montants et canaux d'accès doivent être confirmés sur la source officielle ou auprès des partenaires pays.",
    },
}


def _section_payload(device: Device, short: str, eligibility: str, funding: str) -> list[dict[str, Any]]:
    if device.close_date:
        calendar = f"Date limite indiquée : {device.close_date:%d/%m/%Y}. Vérifier la date sur la source officielle avant de candidater."
    elif device.status == "recurring" or device.is_recurring:
        calendar = "Opportunité récurrente ou à guichet variable : vérifier si une session ou un appel est ouvert avant de préparer un dossier."
    else:
        calendar = "Date limite non confirmée : vérifier la source officielle avant toute décision."
    procedure = "Consulter la source officielle, vérifier les critères, puis préparer les pièces demandées avant de candidater ou de contacter l'organisme."
    checks = "Confirmer la date, le montant exact, les bénéficiaires admissibles, les dépenses éligibles et la procédure de dépôt sur la source officielle."
    return [
        {"key": "presentation", "title": "Présentation", "content": short, "confidence": 90, "source": "nettoyage qualité utilisateur"},
        {"key": "eligibility", "title": "Pour qui ?", "content": eligibility, "confidence": 82, "source": "nettoyage qualité utilisateur"},
        {"key": "funding", "title": "Montant / avantages", "content": funding, "confidence": 80, "source": "nettoyage qualité utilisateur"},
        {"key": "calendar", "title": "Calendrier", "content": calendar, "confidence": 80, "source": "nettoyage qualité utilisateur"},
        {"key": "procedure", "title": "Démarche", "content": procedure, "confidence": 78, "source": "nettoyage qualité utilisateur"},
        {"key": "checks", "title": "Points à vérifier", "content": checks, "confidence": 76, "source": "nettoyage qualité utilisateur"},
    ]


def _payload(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    updated: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.id.in_(list(UPDATES.keys()))))
        ).scalars().all()

        for device in devices:
            data = UPDATES.get(str(device.id))
            if not data:
                continue
            short = clean_editorial_text(data["short"])
            eligibility = clean_editorial_text(data["eligibility"])
            funding = clean_editorial_text(data["funding"])
            sections = _section_payload(device, short, eligibility, funding)
            procedure = next(section["content"] for section in sections if section["key"] == "procedure")

            before = (device.short_description or "")[:140]
            device.short_description = short
            device.eligibility_criteria = eligibility
            device.funding_details = funding
            device.specific_conditions = eligibility
            device.content_sections_json = sections
            device.ai_rewritten_sections_json = sections
            device.ai_rewrite_status = "done"
            device.ai_rewrite_model = "manual-visible-copy-quality-v1"
            device.ai_rewrite_checked_at = now
            device.language = "fr"
            device.full_description = build_structured_sections(
                presentation=short,
                eligibility=eligibility,
                funding=funding,
                close_date=device.close_date,
                open_date=device.open_date,
                procedure=procedure,
                recurrence_notes=device.recurrence_notes,
            )
            device.completeness_score = compute_completeness(_payload(device))
            device.user_quality_score = max(device.user_quality_score or 0, 90)
            device.user_quality_decision = "publish"
            device.updated_at = now
            if device.title:
                device.title_normalized = normalize_title(device.title)

            updated.append({"id": str(device.id), "title": device.title, "before": before, "after": short[:160]})

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "updated": len(updated), "items": updated}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reformule les fiches visibles encore trop generiques ou coupees.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
