from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "Seme City - RISE 2 Benin",
        "organism": "Seme City / ADPME Benin",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://semecity.bj/programmes/rise/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "benin_pme_growth"},
        "notes": "Programme RISE 2 pour PME et jeunes entreprises béninoises, avec appui financier et accompagnement.",
    },
    {
        "name": "WIDU Cote d'Ivoire - subventions diaspora",
        "organism": "WIDU.africa / GIZ",
        "country": "Côte d'Ivoire",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://widu.africa/fr/cote-divoire",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "cote_ivoire_micro_pme_diaspora"},
        "notes": "Programme de cofinancement diaspora pour micro et petites entreprises en Côte d'Ivoire.",
    },
    {
        "name": "Ouaga Tout Court - incubateur cinema Burkina Faso",
        "organism": "Ouaga Tout Court",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://www.ouagatoutcourt.net/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "burkina_creative_industries"},
        "notes": "Incubateur de formation pour jeunes cineastes africains residents au Burkina Faso.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "Seme City - RISE 2 Benin",
        "title": "RISE 2 Bénin - financement et accélération des PME",
        "organism": "Seme City / ADPME Benin",
        "organism_type": "programme public",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_et_accompagnement",
        "sectors": ["entrepreneuriat", "pme", "startup", "agroalimentaire", "numerique", "numérique", "economie verte", "économie verte", "artisanat"],
        "beneficiaries": ["pme", "startup", "entreprise", "jeune entreprise", "entrepreneur"],
        "amount_max": Decimal("28000000"),
        "currency": "XOF",
        "open_date": date(2026, 5, 7),
        "close_date": date(2026, 6, 7),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://semecity.bj/programmes/rise/",
        "source_raw": (
            "Seme City indique que RISE 2 accompagne les jeunes entreprises et PME à fort potentiel au Bénin. "
            "Le programme facilite l'accès au financement, à l'accompagnement technique, à la formation, au coaching et à la mise en réseau. "
            "La page officielle indique une candidature avant le 7 juin 2026 et un appui financier pouvant aller jusqu'à 28 millions de FCFA."
        ),
        "presentation": (
            "RISE 2 est un programme d'accélération pour les PME et jeunes entreprises béninoises qui veulent structurer leur croissance, renforcer leur compétitivité et accéder à un appui financier."
        ),
        "eligibility": (
            "Le programme cible deux profils : les jeunes entreprises en phase d'amorçage avec un chiffre d'affaires entre 0 et 30 millions de FCFA, et les PME innovantes avec un chiffre d'affaires entre 15 et 50 millions de FCFA."
        ),
        "funding": (
            "L'appui financier peut aller jusqu'à 28 millions de FCFA. Il est complété par de la formation, du coaching, une assistance technique personnalisée et une mise en réseau."
        ),
        "calendar": (
            "Les candidatures sont ouvertes jusqu'au 7 juin 2026. La date et les conditions doivent être confirmées sur la page officielle avant dépôt."
        ),
        "procedure": (
            "Consulter la page RISE 2 de Seme City, vérifier les critères, puis utiliser le bouton de candidature renvoyant vers la plateforme officielle de dépôt."
        ),
        "checks": (
            "Vérifier la catégorie de candidature, le chiffre d'affaires éligible, les documents demandés et le lien de dépôt officiel avant de soumettre."
        ),
        "decision": (
            "Très bonne opportunité pour une PME ou startup béninoise déjà structurée qui cherche un appui financier et un accompagnement de croissance."
        ),
    },
    {
        "source_name": "WIDU Cote d'Ivoire - subventions diaspora",
        "title": "WIDU Côte d'Ivoire - subventions diaspora pour micro et petites entreprises",
        "organism": "WIDU.africa / GIZ",
        "organism_type": "programme international",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "cofinancement_diaspora",
        "sectors": ["entrepreneuriat", "microentreprise", "pme", "femmes", "jeunesse", "economie verte", "économie verte"],
        "beneficiaries": ["microentreprise", "pme", "entrepreneur", "femme entrepreneure", "jeune entrepreneur"],
        "amount_min": Decimal("3000"),
        "amount_max": Decimal("5000"),
        "currency": "EUR",
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://widu.africa/fr/cote-divoire",
        "source_raw": (
            "WIDU Côte d'Ivoire est un programme cofinancé par l'Union européenne et mis en œuvre par la GIZ. "
            "La source indique que les entrepreneurs ivoiriens parrainés par un proche ou ami vivant dans l'UE, en Suisse ou en Norvège peuvent obtenir une subvention jusqu'à 3 000 EUR pour une première demande, puis jusqu'à 5 000 EUR pour les tours suivants, avec coaching personnalisé."
        ),
        "presentation": (
            "WIDU aide les micro et petites entreprises en Côte d'Ivoire à mobiliser un cofinancement avec l'appui de la diaspora, tout en bénéficiant d'un accompagnement."
        ),
        "eligibility": (
            "L'entrepreneur doit être basé en Côte d'Ivoire et être parrainé par un proche ou ami vivant dans l'un des pays éligibles de la diaspora : Union européenne, Suisse ou Norvège. Les entreprises dirigées par des femmes et des jeunes sont particulièrement pertinentes."
        ),
        "funding": (
            "La subvention peut atteindre 3 000 EUR pour une première demande, puis jusqu'à 5 000 EUR pour les deuxième et troisième tours. Le programme inclut aussi trois sessions de coaching personnalisé."
        ),
        "calendar": (
            "Programme récurrent sans date unique de clôture communiquée sur la page pays. Les modalités et ouvertures doivent être vérifiées au moment de la demande."
        ),
        "procedure": (
            "Créer un compte sur WIDU, préparer le projet avec le parrain diaspora, compléter le plan d'investissement et suivre le processus de validation en ligne."
        ),
        "checks": (
            "Confirmer les pays de résidence acceptés pour le parrain, les justificatifs de contribution, les secteurs admis et la disponibilité du programme pour la Côte d'Ivoire."
        ),
        "decision": (
            "Bonne opportunité pour une micro ou petite entreprise ivoirienne qui dispose d'un relais diaspora prêt à cofinancer son développement."
        ),
    },
    {
        "source_name": "Ouaga Tout Court - incubateur cinema Burkina Faso",
        "title": "Ouaga Tout Court - incubation pour jeunes cineastes au Burkina Faso",
        "organism": "Ouaga Tout Court",
        "organism_type": "incubateur",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_creative",
        "sectors": ["culture", "cinema", "audiovisuel", "jeunesse", "formation", "industries creatives"],
        "beneficiaries": ["porteur projet", "entrepreneur culturel", "jeune createur", "association"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.ouagatoutcourt.net/",
        "source_raw": (
            "Ouaga Tout Court se presente comme un incubateur de formation a la realisation de courts metrages. "
            "La source officielle indique qu'il s'agit d'un dispositif de renforcement des capacites de jeunes cineastes africains residents au Burkina Faso pour la realisation de leur premier ou deuxieme film court metrage de fiction ou documentaire."
        ),
        "presentation": (
            "Ouaga Tout Court accompagne des jeunes cineastes residents au Burkina Faso dans le developpement et la realisation de courts metrages de fiction ou documentaire."
        ),
        "eligibility": (
            "Le dispositif concerne des jeunes cineastes africains residents au Burkina Faso, notamment ceux qui souhaitent realiser un premier ou deuxieme court metrage."
        ),
        "funding": (
            "L'appui visible est principalement de l'incubation, de la formation, du renforcement artistique et de la mise en relation avec des partenaires du cinema. Le site ne communique pas de montant financier direct."
        ),
        "calendar": (
            "Programme a suivre comme opportunite recurrente ou par cohorte. La page officielle ne communique pas de date limite unique dans le contenu public consulte."
        ),
        "procedure": (
            "Consulter la page officielle, verifier les actualites ou appels ouverts, puis contacter l'equipe via les coordonnees indiquees pour connaitre la prochaine cohorte."
        ),
        "checks": (
            "Confirmer l'ouverture des candidatures 2026, les conditions de residence, les pieces artistiques demandees et la nature exacte de l'appui avant de recommander une candidature."
        ),
        "decision": (
            "Piste utile pour les entrepreneurs culturels et jeunes cineastes au Burkina Faso, surtout si leur besoin principal est l'accompagnement plutot qu'une subvention directe."
        ),
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        counts = {"created": 0, "updated": 0}
        for device_data in DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        await db.commit()
        print({"sources": len(sources), **counts})


if __name__ == "__main__":
    asyncio.run(main())
