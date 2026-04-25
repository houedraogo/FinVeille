"""
Script de seed : peuple la base avec des sources initiales fiables et un compte admin.
Usage : python -m app.data.seed
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import AsyncSessionLocal, create_tables
from app.models.source import Source
from app.models.user import User
from app.utils.auth_utils import hash_password

INITIAL_SOURCES = [
    {
        "name": "Aides-territoires - aides aux entreprises",
        "organism": "ANCT / beta.gouv.fr",
        "country": "France",
        "source_type": "portail_officiel",
        "category": "public",
        "level": 1,
        "url": "https://aides-territoires.beta.gouv.fr/api/aids/?format=json&page_size=50&target_audience=private_sector",
        "collection_mode": "api",
        "check_frequency": "daily",
        "reliability": 5,
        "config": {
            "items_path": "results",
            "title_field": "name",
            "url_field": "url",
            "description_field": "description",
            "pagination": {"type": "page", "page_param": "page", "size_param": "page_size", "size_value": 50},
        },
    },
    {
        "name": "data.gouv.fr - aides et subventions",
        "organism": "Gouvernement francais",
        "country": "France",
        "source_type": "portail_officiel",
        "category": "public",
        "level": 2,
        "url": "https://www.data.gouv.fr/api/1/datasets/?tag=subvention&page_size=100&sort=-created",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 4,
        "config": {
            "items_path": "data",
            "title_field": "title",
            "url_field": "page",
            "description_field": "description",
            "pagination": {"type": "page", "page_param": "page", "size_param": "page_size", "size_value": 100},
        },
    },
    {
        "name": "Bpifrance - appels a projets et concours",
        "organism": "Bpifrance",
        "country": "France",
        "source_type": "agence_nationale",
        "category": "public",
        "level": 1,
        "url": "https://www.bpifrance.fr/nos-appels-a-projets-concours",
        "collection_mode": "html",
        "check_frequency": "weekly",
        "reliability": 4,
        "config": {
            "link_selector": "a[href*='/nos-appels-a-projets-concours/'], a.card__link",
            "title_selector": "h3, h2, .card__title",
            "description_selector": ".card__description, p",
        },
    },
    {
        "name": "AFD - concours et appels a projets",
        "organism": "Agence Francaise de Developpement",
        "country": "International",
        "source_type": "agence_nationale",
        "category": "public",
        "level": 1,
        "url": "https://opendata.afd.fr/api/explore/v2.1/catalog/datasets/les-concours-de-l-afd/records",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "items_path": "results",
            "title_field": "intitule",
            "url_field": "url",
            "description_field": "description",
            "pagination": {"type": "offset", "offset_param": "offset", "size_param": "limit", "size_value": 100},
        },
    },
    {
        "name": "Banque Mondiale - projets Senegal",
        "organism": "World Bank Group",
        "country": "Senegal",
        "source_type": "institution_regionale",
        "category": "public",
        "level": 1,
        "url": "https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=SN&fl=id,project_name,totalamt,sector1,boardapprovaldate,closingdate,url,project_abstract&status_exact=Active",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "items_path": "projects",
            "title_field": "project_name",
            "url_field": "url",
            "description_field": "project_abstract",
            "url_template": "https://projects.worldbank.org/en/projects-operations/project-detail/{id}",
            "pagination": {"type": "offset", "offset_param": "start", "size_param": "rows", "size_value": 50},
        },
    },
    {
        "name": "Banque Mondiale - projets Cote d'Ivoire",
        "organism": "World Bank Group",
        "country": "Cote d'Ivoire",
        "source_type": "institution_regionale",
        "category": "public",
        "level": 1,
        "url": "https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=CI&fl=id,project_name,totalamt,sector1,boardapprovaldate,closingdate,url,project_abstract&status_exact=Active",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "items_path": "projects",
            "title_field": "project_name",
            "url_field": "url",
            "description_field": "project_abstract",
            "url_template": "https://projects.worldbank.org/en/projects-operations/project-detail/{id}",
            "pagination": {"type": "offset", "offset_param": "start", "size_param": "rows", "size_value": 50},
        },
    },
    {
        "name": "IFC - projets Afrique",
        "organism": "IFC",
        "country": "Afrique",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 1,
        "url": "https://disclosures.ifc.org/api/v1/disclosure?regionId=SSA&status=Active&limit=50&offset=0",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "items_path": "data",
            "title_field": "projectName",
            "url_field": "projectUrl",
            "description_field": "projectDescription",
            "pagination": {"type": "offset", "offset_param": "offset", "size_param": "limit", "size_value": 50},
        },
    },
    {
        "name": "PROPARCO - projets secteur prive",
        "organism": "PROPARCO",
        "country": "Afrique",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 1,
        "url": "https://opendata.afd.fr/api/explore/v2.1/catalog/datasets/donnees-de-laide-au-developpement-de-proparco/records",
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "items_path": "results",
            "title_field": "intitule_du_projet",
            "url_field": "url_projet",
            "description_field": "description_du_projet",
            "pagination": {"type": "offset", "offset_param": "offset", "size_param": "limit", "size_value": 100},
        },
    },
    {
        "name": "France Angels - reseau national",
        "organism": "France Angels",
        "country": "France",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 2,
        "url": "https://www.franceangels.org",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
    {
        "name": "Bpifrance Investissement - capital investissement",
        "organism": "Bpifrance Investissement",
        "country": "France",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 2,
        "url": "https://www.bpifrance.fr/nos-metiers/investissement",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
]

ADMIN_USER = {
    "email": "contact@kafundo.com",
    "password": "Kafundo@2026!",
    "full_name": "Administrateur Kafundo",
    "role": "admin",
}


async def seed():
    print("Creation des tables...")
    await create_tables()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        existing_admin = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
        if not existing_admin.scalar_one_or_none():
            admin = User(
                email=ADMIN_USER["email"],
                password_hash=hash_password(ADMIN_USER["password"]),
                full_name=ADMIN_USER["full_name"],
                role=ADMIN_USER["role"],
            )
            db.add(admin)
            print(f"Admin cree : {ADMIN_USER['email']}")
        else:
            print(f"Admin deja existant : {ADMIN_USER['email']}")

        created = 0
        for src_data in INITIAL_SOURCES:
            existing = await db.execute(select(Source).where(Source.url == src_data["url"]))
            if not existing.scalar_one_or_none():
                source = Source(**src_data)
                db.add(source)
                created += 1

        await db.commit()
        print(f"{created} source(s) creee(s) sur {len(INITIAL_SOURCES)}")
        print("\nSeed termine. Connectez-vous avec :")
        print(f"   Email    : {ADMIN_USER['email']}")
        print(f"   Password : {ADMIN_USER['password']}")
        print("\nPensez a changer le mot de passe admin en production.")


if __name__ == "__main__":
    asyncio.run(seed())
