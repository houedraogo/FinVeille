"""
Met a jour les sources existantes, desactive les sources fragiles
et ajoute un socle de sources plus fiables cote public et prive.

Usage : docker exec kafundo-backend python -m app.data.update_sources
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, "/app")


def _wb_url(country_code: str) -> str:
    fields = "id,project_name,project_abstract,url,totalcommamt,boardapprovaldate,closingdate,projectstatus,countryshortname,status,sector1,sector2"
    return (
        f"https://search.worldbank.org/api/v3/projects"
        f"?format=json&countrycode_exact={country_code}&status_exact=Active&fl={fields}&rows=50&start=0"
    )


WB_CONFIG = {
    "items_path": "projects",
    "title_field": "project_name",
    "description_field": "project_abstract",
    "url_template": "https://projects.worldbank.org/en/projects-operations/project-detail/{id}",
    "close_date_fields": ["closingdate"],
    "status_fields": ["status", "projectstatus"],
    "raw_content_fields": ["project_abstract", "countryshortname", "sector1.Name", "sector2.Name"],
    "allow_english_text": True,
    "assume_standby_without_close_date": True,
    "pagination": {"type": "offset", "offset_param": "start", "size_param": "rows", "size_value": 50},
}


NEW_SOURCES = [
    {
        "name": "data.aides-entreprises.fr - aides aux entreprises",
        "organism": "API Aides Entreprises",
        "country": "France",
        "source_type": "portail_officiel",
        "category": "public",
        "level": 1,
        "url": "https://api.aides-entreprises.fr/v1.1/aides?status=1&clean_html=true",
        "collection_mode": "api",
        "check_frequency": "daily",
        "reliability": 5,
        "config": {
            "api_headers": [
                {"name": "X-Aidesentreprises-Id", "env": "AIDES_ENTREPRISES_API_ID"},
                {"name": "X-Aidesentreprises-Key", "env": "AIDES_ENTREPRISES_API_KEY"},
            ],
            "items_path": "data",
            "title_field": "aid_nom",
            "description_field": "aid_objet",
            "url_template": "https://api.aides-entreprises.fr/v1.1/aide/{id_aid}",
            "detail_url_template": "https://api.aides-entreprises.fr/v1.1/aide/{id_aid}",
            "detail_description_field": "aid_objet",
            "assume_recurring_without_close_date": True,
            "raw_content_fields": [
                "aid_objet",
                "aid_operations_el",
                "aid_conditions",
                "aid_montant",
                "aid_benef",
                "complements.source.0.texte",
                "complements.formulaire.0.texte",
                "complements.reglement.0.texte",
                "complements.dispositif.0.texte",
            ],
            "detail_raw_content_fields": [
                "aid_objet",
                "aid_operations_el",
                "aid_conditions",
                "aid_montant",
                "aid_benef",
                "complements.source.0.texte",
                "complements.formulaire.0.texte",
                "complements.reglement.0.texte",
                "complements.dispositif.0.texte",
            ],
            "preferred_url_fields": [
                "complements.source.0.lien",
                "complements.dispositif.0.lien",
                "complements.formulaire.0.lien",
            ],
            "close_date_fields": ["date_fin", "dateFin", "deadline", "deadlineDate"],
            "pagination": {"type": "offset", "offset_param": "offset", "size_param": "limit", "size_value": 100},
        },
        "notes": "API protegee par headers X-Aidesentreprises-Id et X-Aidesentreprises-Key.",
    },
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
        "is_active": False,
        "notes": "API protegee par JWT. Source a reactiver quand un jeton d'acces ou une integration authentifiee sera disponible.",
    },
    {
        "name": "les-aides.fr - solutions de financement entreprises",
        "organism": "CCI Hauts-de-France / Les-aides.fr",
        "country": "France",
        "source_type": "portail_officiel",
        "category": "public",
        "level": 1,
        "url": "https://api.les-aides.fr/",
        "collection_mode": "les_aides",
        "check_frequency": "daily",
        "reliability": 5,
        "config": {
            "api_key_header": "IDC",
            "api_key_value": "f94f575e2932379f273b7ede238d5deb72c4fdf4",
            "assume_standby_without_close_date": True,
        },
        "is_active": True,
        "notes": "API officielle CCI les-aides.fr. Attribution obligatoire : 'Contenu produit par Les-aides.fr'. Limite 720 req/jour.",
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
        "is_active": False,
        "notes": "Source desactivee: le flux generique data.gouv.fr remonte surtout des jeux de donnees historiques et archives.",
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
        "url": "https://www.afd.fr/fr/appels-a-projets/liste?status%5Bongoing%5D=ongoing&status%5Bsoon%5D=soon",
        "collection_mode": "html",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": {
            "list_selector": ".views-row",
            "item_title_selector": "a[href*='/fr/appels-a-projets/']",
            "item_link_selector": "a[href*='/fr/appels-a-projets/']",
            "detail_fetch": True,
            "detail_content_selector": ".column_content",
            "detail_max_chars": 9000,
            "pagination": {"max_pages": 1},
        },
        "notes": "Source officielle AFD ciblee sur la liste des appels a projets ouverts et a venir.",
    },
    {
        "name": "Global South Opportunities - Funding",
        "organism": "Global South Opportunities",
        "country": "International",
        "source_type": "agregateur",
        "category": "public",
        "level": 2,
        "url": "https://www.globalsouthopportunities.com/category/funding/feed/",
        "collection_mode": "rss",
        "check_frequency": "daily",
        "reliability": 3,
        "config": {
            "source_kind": "editorial_funding",
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
            "close_date_fields": ["deadline", "application_deadline"],
            "status_fields": ["status"],
        },
        "is_active": True,
        "notes": (
            "Flux RSS WordPress de la categorie Funding. Source relais/agregateur : "
            "les informations doivent etre confirmees sur le site officiel du dispositif."
        ),
    },
    {
        "name": "Banque Mondiale - projets Senegal",
        "organism": "World Bank Group",
        "country": "Senegal",
        "source_type": "institution_regionale",
        "category": "public",
        "level": 1,
        "url": _wb_url("SN"),
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": WB_CONFIG,
    },
    {
        "name": "Banque Mondiale - projets Cote d'Ivoire",
        "organism": "World Bank Group",
        "country": "Cote d'Ivoire",
        "source_type": "institution_regionale",
        "category": "public",
        "level": 1,
        "url": _wb_url("CI"),
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": WB_CONFIG,
    },
    {
        "name": "Banque Mondiale - projets Maroc",
        "organism": "World Bank Group",
        "country": "Maroc",
        "source_type": "institution_regionale",
        "category": "public",
        "level": 1,
        "url": _wb_url("MA"),
        "collection_mode": "api",
        "check_frequency": "weekly",
        "reliability": 5,
        "config": WB_CONFIG,
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
        "is_active": False,
        "notes": "Source desactivee: aucun succes de collecte et 4 erreurs consecutives.",
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
        "name": "Femmes Business Angels - reseau",
        "organism": "Femmes Business Angels",
        "country": "France",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 2,
        "url": "https://www.femmesbusinessangels.org",
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
        "level": 1,
        "url": "https://www.bpifrance.fr/nos-metiers/investissement",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
    {
        "name": "Partech Africa - VC tech Afrique",
        "organism": "Partech Africa",
        "country": "Afrique",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 1,
        "url": "https://partechpartners.com/africa",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
    {
        "name": "I&P - Investisseurs & Partenaires",
        "organism": "Investisseurs & Partenaires",
        "country": "Afrique",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 1,
        "url": "https://www.ietp.com",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
    {
        "name": "AfricInvest - private equity Afrique",
        "organism": "AfricInvest",
        "country": "Afrique",
        "source_type": "fonds_prive",
        "category": "private",
        "level": 1,
        "url": "https://www.africinvest.com",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 3,
        "is_active": False,
        "notes": "Source privee a qualifier manuellement avant automatisation.",
        "config": {},
    },
]


BROKEN_RULES = [
    (
        "BOAD ou BAD",
        "UPDATE sources SET is_active=false, notes='Source desactivee: URL ou acces devenu non fiable' "
        "WHERE (name ILIKE '%BOAD%' OR name ILIKE '%Africaine de Developpement%') AND consecutive_errors >= 3",
    ),
    (
        "Banque des Territoires",
        "UPDATE sources SET is_active=false, notes='Source desactivee: URL non fiable ou obsolete' "
        "WHERE name ILIKE '%Banque des Territoires%' AND consecutive_errors >= 3",
    ),
    (
        "Sources HTML fragiles",
        "UPDATE sources SET is_active=false, notes='Source historique fragile remplacee par une alternative plus fiable' "
        "WHERE (name ILIKE '%USAID West Africa%' "
        "OR name ILIKE '%DER/FJ%' "
        "OR name ILIKE '%ANPME Maroc%' "
        "OR name ILIKE '%European Funding Guide%') "
        "AND consecutive_errors >= 2",
    ),
]


async def main():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        disabled_count = 0
        for _, sql in BROKEN_RULES:
            result = await session.execute(text(sql))
            disabled_count += result.rowcount
        print(f"{disabled_count} source(s) fragiles desactivee(s)")

        await session.execute(text(
            "UPDATE sources SET url='https://www.bpifrance.fr/nos-solutions', "
            "consecutive_errors=0, notes='URL corrigee vers /nos-solutions' "
            "WHERE name ILIKE '%Bpifrance%' AND url LIKE '%toutes-nos-solutions%'"
        ))

        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    is_active = false,
                    consecutive_errors = 0,
                    notes = :notes
                WHERE name ILIKE '%Aides-territoires%'
                """
            ),
            {
                "notes": (
                    "Source desactivee: l'API Aides-territoires exige un JWT "
                    "et ne peut pas etre recollectee sans authentification."
                ),
            },
        )

        await session.execute(
            text(
                """
                UPDATE sources
                SET config = CAST(config AS jsonb) || CAST(:config_patch AS jsonb)
                WHERE name = 'les-aides.fr - solutions de financement entreprises'
                """
            ),
            {
                "config_patch": json.dumps({
                    "assume_standby_without_close_date": True,
                }),
            },
        )

        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    url = :url,
                    collection_mode = 'html',
                    consecutive_errors = 0,
                    config = CAST(:config AS jsonb),
                    notes = :notes
                WHERE name = 'Banque des Territoires - dispositifs et appels'
                """
            ),
            {
                "url": "https://www.banquedesterritoires.fr/dispositifs-nationaux",
                "config": json.dumps(
                    {
                        "list_selector": "main .paragraph--type--node-ref article.card-o",
                        "item_title_selector": ".card-o__title, h3, h2",
                        "item_link_selector": "a.card-o__trigger",
                        "item_description_selector": ".card-o__desc, p",
                        "detail_fetch": True,
                        "detail_content_selector": "main .field--name-body, main .layout-content, main article, main",
                        "detail_max_chars": 9000,
                        "assume_standby_without_close_date": True,
                        "pagination": {"max_pages": 1},
                    }
                ),
                "notes": (
                    "Source retargetee vers /dispositifs-nationaux pour ne collecter "
                    "que les programmes et dispositifs, en excluant le bruit de navigation, "
                    "les billets blog et les evenements generiques."
                ),
            },
        )

        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    url = :url,
                    collection_mode = 'html',
                    is_active = true,
                    consecutive_errors = 0,
                    config = CAST(:config AS jsonb),
                    notes = :notes
                WHERE name = 'AFD - concours et appels a projets'
                """
            ),
            {
                "url": "https://www.afd.fr/fr/appels-a-projets/liste?status%5Bongoing%5D=ongoing&status%5Bsoon%5D=soon",
                "config": json.dumps(
                    {
                        "list_selector": ".views-row",
                        "item_title_selector": "a[href*='/fr/appels-a-projets/']",
                        "item_link_selector": "a[href*='/fr/appels-a-projets/']",
                        "detail_fetch": True,
                        "detail_content_selector": ".column_content",
                        "detail_max_chars": 9000,
                        "pagination": {"max_pages": 1},
                    }
                ),
                "notes": "Source officielle AFD ciblee sur la liste des appels a projets ouverts et a venir.",
            },
        )

        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    is_active = false,
                    notes = :notes,
                    consecutive_errors = 0
                WHERE name IN (
                    'AFD - dons et subventions ONG',
                    'AFD - operations de financement'
                )
                """
            ),
            {
                "notes": "Source desactivee: flux historiques de projets/operations AFD, non cibles pour les appels a projets actuels.",
            },
        )

        wb_source_updates = {
            "Banque Mondiale - projets Senegal": _wb_url("SN"),
            "Banque Mondiale - projets Cote d'Ivoire": _wb_url("CI"),
            "Banque Mondiale - projets Maroc": _wb_url("MA"),
            "Banque Mondiale - projets Cameroun": _wb_url("CM"),
            "Banque Mondiale - projets Tunisie": _wb_url("TN"),
            "Banque Mondiale - projets Mali": _wb_url("ML"),
            "Banque Mondiale - projets Kenya": _wb_url("KE"),
            "Banque Mondiale - projets Ghana": _wb_url("GH"),
            "Banque Mondiale - projets Rwanda": _wb_url("RW"),
            "Banque Mondiale - projets Burkina Faso": _wb_url("BF"),
            "Banque Mondiale - projets Guinee": _wb_url("GN"),
            "Banque Mondiale - projets Benin": _wb_url("BJ"),
            "Banque Mondiale - projets Togo": _wb_url("TG"),
            "Banque Mondiale - projets Niger": _wb_url("NE"),
            "Banque Mondiale - projets Mauritanie": _wb_url("MR"),
            "Banque Mondiale - projets Ethiopie": _wb_url("ET"),
            "Banque Mondiale - projets Madagascar": _wb_url("MG"),
        }

        for source_name, source_url in wb_source_updates.items():
            await session.execute(
                text(
                    """
                    UPDATE sources
                    SET
                        url = :url,
                        collection_mode = 'api',
                        is_active = true,
                        consecutive_errors = 0,
                        config = CAST(:config AS jsonb),
                        notes = :notes
                    WHERE name = :name
                    """
                ),
                {
                    "name": source_name,
                    "url": source_url,
                    "config": json.dumps(WB_CONFIG),
                    "notes": (
                        "Source World Bank standardisee sur les projets actifs avec "
                        "closingdate, status et countryshortname pour fiabiliser les dates "
                        "de cloture et le statut."
                    ),
                },
            )

        # Reconfigurer les-aides.fr en mode API (était en mode html)
        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    url = 'https://api.les-aides.fr/',
                    collection_mode = 'les_aides',
                    is_active = true,
                    consecutive_errors = 0,
                    config = CAST(:config AS jsonb),
                    notes = :notes
                WHERE name = 'les-aides.fr - solutions de financement entreprises'
                  AND collection_mode = 'html'
                """
            ),
            {
                "config": json.dumps({
                    "api_key_header": "IDC",
                    "api_key_value": "f94f575e2932379f273b7ede238d5deb72c4fdf4",
                    "assume_standby_without_close_date": True,
                }),
                "notes": "API officielle CCI les-aides.fr. Attribution obligatoire : 'Contenu produit par Les-aides.fr'. Limite 720 req/jour.",
            },
        )

        await session.execute(
            text(
                """
                UPDATE sources
                SET
                    is_active = false,
                    consecutive_errors = 0,
                    notes = :notes
                WHERE name = 'Banque Mondiale - projets Afrique subsaharienne'
                """
            ),
            {
                "notes": (
                    "Source desactivee: agregat regional trop large et bruité, "
                    "avec remontees hors perimetre. Remplacee par les sources pays ciblees."
                ),
            },
        )

        await session.commit()

        existing_names = {
            row[0].lower().strip()
            for row in (await session.execute(text("SELECT name FROM sources"))).fetchall()
        }

        inserted = 0
        skipped = 0

        for src in NEW_SOURCES:
            key = src["name"].lower().strip()
            if key in existing_names:
                skipped += 1
                continue

            await session.execute(
                text(
                    """
                    INSERT INTO sources (
                        id, name, organism, country, source_type, level,
                        url, collection_mode, check_frequency, reliability,
                        category, is_active, consecutive_errors, config, notes
                    ) VALUES (
                        :id, :name, :organism, :country, :source_type, :level,
                        :url, :collection_mode, :check_frequency, :reliability,
                        :category, :is_active, 0, :config, :notes
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "name": src["name"],
                    "organism": src["organism"],
                    "country": src["country"],
                    "source_type": src["source_type"],
                    "level": src["level"],
                    "url": src["url"],
                    "collection_mode": src["collection_mode"],
                    "check_frequency": src.get("check_frequency", "weekly"),
                    "reliability": src.get("reliability", 3),
                    "category": src.get("category", "public"),
                    "is_active": src.get("is_active", True),
                    "config": json.dumps(src.get("config") or {}),
                    "notes": src.get("notes"),
                },
            )
            existing_names.add(key)
            inserted += 1
            print(f"Ajoutee : {src['name']}")

        await session.commit()

        totals = (
            await session.execute(
                text(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE category='public') AS public_count, "
                    "COUNT(*) FILTER (WHERE category='private') AS private_count, "
                    "COUNT(*) FILTER (WHERE is_active) AS active_count, "
                    "COUNT(*) AS total_count "
                    "FROM sources"
                )
            )
        ).fetchone()

        print(
            f"Resultat : {inserted} ajoutee(s), {skipped} deja presente(s) | "
            f"Public: {totals[0]} | Prive: {totals[1]} | Actives: {totals[2]} | Total: {totals[3]}"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
