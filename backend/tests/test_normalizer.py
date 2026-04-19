from datetime import date, timedelta

from app.collector.base_connector import RawItem
from app.collector.normalizer import Normalizer


def make_source(**config):
    return {
        "id": "source-1",
        "country": "France",
        "organism": "Source de test",
        "language": "fr",
        "url": "https://example.org/source",
        "config": config,
    }


def test_normalizer_reads_close_date_from_metadata_field():
    normalizer = Normalizer(make_source())
    item = RawItem(
        title="Appel a projets energie",
        url="https://example.org/aide",
        raw_content="Financement pour les PME.",
        metadata={"closingdate": "2026-09-30"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["close_date"] == date(2026, 9, 30)
    assert normalized["status"] == "open"


def test_normalizer_reads_close_date_from_project_end_metadata_field():
    normalizer = Normalizer(make_source())
    item = RawItem(
        title="Projet ADEME",
        url="https://example.org/projet",
        raw_content="Projet de recherche environnementale.",
        metadata={"date_de_fin_du_projet": "2017-12-27"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["close_date"] == date(2017, 12, 27)
    assert normalized["status"] == "expired"


def test_normalizer_marks_expired_when_metadata_close_date_is_past():
    past_date = (date.today() - timedelta(days=2)).isoformat()
    normalizer = Normalizer(make_source())
    item = RawItem(
        title="Programme clos",
        url="https://example.org/programme",
        raw_content="Programme de soutien aux entreprises.",
        metadata={"date_fin": past_date, "status": "open"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["close_date"] == date.fromisoformat(past_date)
    assert normalized["status"] == "expired"


def test_normalizer_marks_recurring_when_source_assumes_recurring_without_close_date():
    normalizer = Normalizer(make_source(assume_recurring_without_close_date=True))
    item = RawItem(
        title="Aide permanente a l'investissement",
        url="https://example.org/permanent",
        raw_content="Aide ouverte en continu pour les PME.",
        metadata={"status": "active"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "recurring"
    assert normalized["is_recurring"] is True
    assert "recurrent" in normalized["recurrence_notes"]


def test_normalizer_marks_standby_when_source_assumes_standby_without_close_date():
    normalizer = Normalizer(make_source(assume_standby_without_close_date=True))
    item = RawItem(
        title="Projet institutionnel sans date",
        url="https://example.org/projet",
        raw_content="Projet actif sans date de cloture communiquee.",
        metadata={"status": "active"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "standby"
    assert normalized["is_recurring"] is False


def test_normalizer_uses_metadata_status_when_source_marks_project_closed():
    normalizer = Normalizer(make_source(status_fields=["projectstatus"]))
    item = RawItem(
        title="Projet institutionnel",
        url="https://example.org/project",
        raw_content="Projet soutenu par une institution.",
        metadata={"projectstatus": "Closed"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "closed"


def test_normalizer_builds_structured_full_description_from_metadata_only():
    normalizer = Normalizer(make_source())
    item = RawItem(
        title="Kenya Solar Lighting Program",
        url="https://example.org/kenya-solar",
        raw_content="",
        metadata={
            "countryshortname": "Kenya",
            "sector1": {"Name": "Energy"},
            "sector2": {"Name": "Climate"},
            "totalcommamt": "15000000",
            "boardapprovaldate": "2017-07-26",
            "closingdate": "2026-09-30",
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["full_description"] is not None
    assert "## Presentation" in normalized["full_description"]
    assert "## Calendrier" in normalized["full_description"]
    assert "- Cloture : 30/09/2026" in normalized["full_description"]
    assert "## Demarche" in normalized["full_description"]


def test_normalizer_replaces_english_world_bank_abstract_with_french_metadata_summary():
    normalizer = Normalizer(
        {
            "id": "wb-source",
            "country": "Kenya",
            "organism": "World Bank Group",
            "language": "fr",
            "url": "https://search.worldbank.org/api/v3/projects?countrycode_exact=KE",
            "config": {"allow_english_text": True},
        }
    )
    item = RawItem(
        title="Kenya Solar Lighting Program",
        url="https://projects.worldbank.org/en/projects-operations/project-detail/P123456",
        raw_content=(
            "The project development objective is to expand access to modern energy services "
            "in underserved areas through solar lighting systems and related support."
        ),
        metadata={
            "countryshortname": "Kenya",
            "sector1": {"Name": "Energy"},
            "sector2": {"Name": "Climate"},
            "totalcommamt": "15000000",
            "boardapprovaldate": "2017-07-26",
            "closingdate": "2026-09-30",
            "project_abstract": (
                "The project development objective is to expand access to modern energy services "
                "in underserved areas through solar lighting systems and related support."
            ),
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["short_description"] is not None
    assert "The project development objective" not in normalized["short_description"]
    assert "Ce projet est porté" in normalized["short_description"]
    assert normalized["full_description"] is not None
    assert "The project development objective" not in normalized["full_description"]
    assert normalized["device_type"] == "autre"


def test_normalizer_overrides_title_for_africa_business_heroes_source():
    normalizer = Normalizer(
        {
            "id": "source-abh",
            "country": "Afrique",
            "organism": "Fondation Jack Ma",
            "language": "fr",
            "url": "https://africabusinessheroes.org/fr/the-prize/overview",
            "config": {},
        }
    )
    item = RawItem(
        title="LE CONCOURS DU PRIXAFRICA'S BUSINESS HEROES (ABH)",
        url="https://africabusinessheroes.org/fr/the-prize/overview",
        raw_content=(
            "Bienvenue dans la candidature ABH 2026 ! "
            "La date limite de depot des candidatures est fixee au 28 avril 2026. "
            "Les entreprises doivent justifier d'au moins trois ans d'existence."
        ),
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["title"] == "Africa's Business Heroes (ABH) 2026"
    assert normalized["device_type"] == "concours"
    assert normalized["close_date"] == date(2026, 4, 28)
    assert normalized["full_description"] is not None
    assert "## Calendrier" in normalized["full_description"]
    assert "trois ans" in normalized["full_description"]
    assert "1,5 million de dollars" in normalized["full_description"]


def test_normalizer_applies_data_aides_entreprises_profile_sections():
    normalizer = Normalizer(
        {
            "id": "source-aides-entreprises",
            "country": "France",
            "organism": "data.aides-entreprises.fr",
            "language": "fr",
            "url": "https://api.aides-entreprises.fr/v1.1/aides",
            "config": {},
        }
    )
    item = RawItem(
        title="Titre ignore",
        url="https://example.org/aide/123",
        raw_content="",
        metadata={
            "aid_nom": "Pret Flash Carburant",
            "aid_objet": "Soutenir rapidement la tresorerie des entreprises exposees au cout du carburant.",
            "aid_operations_el": "Depenses de tresorerie et besoins de financement court terme.",
            "aid_conditions": "Entreprise de plus d'un an, sans procedure collective, avec activite eligible.",
            "aid_montant": "Pret de 5 000 EUR a 50 000 EUR sur 36 mois.",
            "date_fin": "2026-04-30",
            "status": "1",
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["title"] == "Pret Flash Carburant"
    assert normalized["close_date"] == date(2026, 4, 30)
    assert normalized["status"] == "open"
    assert normalized["short_description"].startswith("Soutenir rapidement la tresorerie")
    assert "## Criteres d'eligibilite" in normalized["full_description"]
    assert "## Montant / avantages" in normalized["full_description"]
    assert "## Demarche" in normalized["full_description"]
    assert normalized["eligibility_criteria"].startswith("Entreprise de plus d'un an")
    assert normalized["funding_details"].startswith("Pret de 5 000 EUR")


def test_normalizer_applies_les_aides_profile_sections():
    normalizer = Normalizer(
        {
            "id": "source-les-aides",
            "country": "France",
            "organism": "Les-aides.fr",
            "language": "fr",
            "url": "https://api.les-aides.fr/aides",
            "config": {},
        }
    )
    item = RawItem(
        title="Titre brut",
        url="https://les-aides.fr/aides/abc",
        raw_content="",
        metadata={
            "title": "Aide a l'innovation",
            "description": "Soutien aux PME qui investissent dans un projet innovant.",
            "conditions": "PME implantee en France avec projet innovant eligible.",
            "montant": "Subvention jusqu'a 30 000 EUR.",
            "date_limite": "2026-06-15",
            "status": "open",
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["title"] == "Aide a l'innovation"
    assert normalized["close_date"] == date(2026, 6, 15)
    assert normalized["short_description"] == "Soutien aux PME qui investissent dans un projet innovant."
    assert "## Presentation" in normalized["full_description"]
    assert "## Criteres d'eligibilite" in normalized["full_description"]
    assert "## Montant / avantages" in normalized["full_description"]
    assert "## Demarche" in normalized["full_description"]


def test_normalizer_builds_contextual_les_aides_fields_when_metadata_is_sparse():
    normalizer = Normalizer(
        {
            "id": "source-les-aides",
            "country": "France",
            "organism": "Les-aides.fr",
            "language": "fr",
            "url": "https://api.les-aides.fr/aides",
            "config": {},
        }
    )
    item = RawItem(
        title="Titre brut",
        url="https://les-aides.fr/aides/abc",
        raw_content="Aide regionale pour favoriser le developpement a l'export des entreprises.",
        metadata={
            "title": "Accompagnement VIE",
            "description": "Aide regionale pour favoriser le developpement a l'export des entreprises.",
            "device_type": "subvention",
            "geographic_scope": "regional",
            "country": "France",
            "status": "open",
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["eligibility_criteria"] is not None
    assert "echelle regionale" in normalized["eligibility_criteria"].lower()
    assert "source officielle" in normalized["eligibility_criteria"].lower()
    assert normalized["funding_details"] is not None
    assert "subvention" in normalized["funding_details"].lower()


def test_normalizer_marks_recurring_when_text_shows_open_ended_program():
    normalizer = Normalizer(make_source())
    item = RawItem(
        title="Aide permanente",
        url="https://example.org/aide-permanente",
        raw_content="Dispositif ouvert en continu, sans date limite de depot, pour soutenir les PME.",
        metadata={"status": "open"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "recurring"
    assert normalized["is_recurring"] is True


def test_normalizer_marks_les_aides_standby_when_no_date_or_recurrence_proof():
    normalizer = Normalizer(
        {
            "id": "source-les-aides",
            "country": "France",
            "organism": "Les-aides.fr",
            "language": "fr",
            "url": "https://api.les-aides.fr/aides",
            "config": {"assume_standby_without_close_date": True},
        }
    )
    item = RawItem(
        title="Aide ponctuelle",
        url="https://les-aides.fr/aides/abc",
        raw_content="Aide regionale pour soutenir les entreprises dans leurs investissements.",
        metadata={"status": "open"},
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "standby"
    assert normalized["is_recurring"] is False


def test_normalizer_marks_data_aides_entreprises_recurring_without_close_date():
    normalizer = Normalizer(
        {
            "id": "source-aides-entreprises",
            "country": "France",
            "organism": "data.aides-entreprises.fr",
            "language": "fr",
            "url": "https://api.aides-entreprises.fr/v1.1/aides",
            "config": {},
        }
    )
    item = RawItem(
        title="Titre ignore",
        url="https://example.org/aide/123",
        raw_content="Dispositif de financement mobilisable pour les entreprises sans date limite explicite.",
        metadata={
            "aid_nom": "Pret a moyen terme",
            "aid_objet": "Financer les investissements des entreprises.",
            "status": "1",
            "date_fin": "0000-00-00 00:00:00",
        },
    )

    normalized = normalizer.normalize(item)

    assert normalized is not None
    assert normalized["status"] == "recurring"
    assert normalized["is_recurring"] is True
