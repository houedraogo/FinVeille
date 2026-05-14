from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SourceProfile:
    key: str
    source_kind: str = "listing"
    domains: tuple[str, ...] = ()
    organism_markers: tuple[str, ...] = ()
    title_fields: tuple[str, ...] = ()
    short_description_fields: tuple[str, ...] = ()
    full_description_fields: tuple[str, ...] = ()
    eligibility_fields: tuple[str, ...] = ()
    funding_fields: tuple[str, ...] = ()
    procedure_fields: tuple[str, ...] = ()
    close_date_fields: tuple[str, ...] = ()
    status_fields: tuple[str, ...] = ()
    country_fields: tuple[str, ...] = ()
    default_device_type: Optional[str] = None
    default_status_without_close_date: Optional[str] = None
    config_overrides: dict[str, Any] = field(default_factory=dict)

    def matches(self, source: dict) -> bool:
        source_url = (source.get("url") or "").lower()
        organism = (source.get("organism") or "").lower()
        name = (source.get("name") or "").lower()

        if any(marker in source_url for marker in self.domains):
            return True
        if any(marker.lower() in organism for marker in self.organism_markers):
            return True
        if any(marker.lower() in name for marker in self.organism_markers):
            return True
        return False


SOURCE_PROFILES: tuple[SourceProfile, ...] = (
    SourceProfile(
        key="les_aides",
        source_kind="listing",
        domains=("api.les-aides.fr", "les-aides.fr"),
        organism_markers=("les-aides.fr",),
        title_fields=("title", "intitule", "nom", "name"),
        short_description_fields=("summary", "resume", "short_description", "description", "objectif", "objet"),
        full_description_fields=("description", "details", "contenu", "body", "presentation", "operations", "depenses"),
        eligibility_fields=("conditions", "eligibility_criteria", "conditions_acces", "beneficiaires_conditions", "beneficiaires", "publics"),
        funding_fields=("funding_details", "montant", "nature_aide", "avantage", "aide", "financement", "taux"),
        procedure_fields=("demarches", "procedure", "modalites", "contact", "depot", "instruction"),
        close_date_fields=("close_date", "date_limite", "date_fin", "deadline", "date_cloture"),
        status_fields=("status", "etat", "state"),
        default_status_without_close_date="standby",
    ),
    SourceProfile(
        key="data_aides_entreprises",
        source_kind="listing",
        domains=("api.aides-entreprises.fr", "data.aides-entreprises.fr"),
        organism_markers=("aides entreprises",),
        title_fields=("aid_nom",),
        short_description_fields=("aid_objet",),
        full_description_fields=("aid_objet", "aid_operations_el"),
        eligibility_fields=("aid_conditions", "aid_benef"),
        funding_fields=("aid_montant",),
        procedure_fields=(
            "aid_demarches",
            "aid_contact",
            "aid_source",
            "aid_source2",
            "aid_ensavoirplus",
            "complements.source",
            "complements.formulaire",
            "complements.dispositif",
        ),
        close_date_fields=("date_fin", "date_cloture", "date_limite_candidature"),
        status_fields=("status",),
        default_status_without_close_date="standby",
        config_overrides={
            "close_date_fields": ["date_fin", "dateFin", "date_cloture", "dateCloture", "date_limite_candidature", "dateLimiteCandidature"],
            "status_fields": ["status"],
        },
    ),
    SourceProfile(
        key="world_bank",
        source_kind="institutional_project",
        domains=("worldbank.org", "search.worldbank.org", "projects.worldbank.org"),
        organism_markers=("world bank", "banque mondiale"),
        title_fields=("project_name", "projectname"),
        short_description_fields=("project_abstract",),
        full_description_fields=("project_abstract",),
        funding_fields=("totalcommamt",),
        close_date_fields=("closingdate", "closing_date"),
        status_fields=("projectstatus", "status"),
        country_fields=("countryshortname",),
        default_device_type="institutional_project",
        default_status_without_close_date="standby",
        config_overrides={
            "allow_english_text": True,
            "close_date_fields": ["closingdate", "closing_date"],
            "status_fields": ["projectstatus", "status"],
        },
    ),
    SourceProfile(
        key="banque_des_territoires",
        source_kind="single_program_page",
        domains=("banquedesterritoires.fr",),
        organism_markers=("banque des territoires",),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "conditions", "criteria", "beneficiaires"),
        funding_fields=("funding", "montant", "avantage", "financement"),
        procedure_fields=("procedure", "demarches", "candidature", "contact"),
        close_date_fields=("deadline", "date_limite", "close_date", "date_fin"),
    ),
    SourceProfile(
        key="ademe",
        source_kind="institutional_project",
        domains=("agirpourlatransition.ademe.fr", "ademe.fr"),
        organism_markers=("ademe",),
        title_fields=("title", "name", "nom", "intitule"),
        short_description_fields=("summary", "resume", "description", "objectif"),
        full_description_fields=("content", "body", "description", "presentation", "details", "objectif"),
        eligibility_fields=("eligibility", "conditions", "criteria", "beneficiaires", "cibles"),
        funding_fields=("funding", "montant", "aide", "financement", "depenses_eligibles"),
        procedure_fields=("procedure", "demarches", "candidature", "depot", "contact"),
        close_date_fields=("deadline", "date_limite", "close_date", "date_fin", "date_de_fin_du_projet"),
        status_fields=("status", "etat"),
        default_status_without_close_date="standby",
    ),
    SourceProfile(
        key="private_investor",
        source_kind="single_program_page",
        domains=(
            "africinvest.com",
            "bpifrance-investissement.fr",
            "partechpartners.com",
            "franceangels.org",
            "femmesbusinessangels.org",
            "ietp.com",
        ),
        organism_markers=(
            "africinvest",
            "bpifrance investissement",
            "bpi france investissement",
            "i&p",
            "investisseurs & partenaires",
            "partech africa",
            "partech",
            "france angels",
            "femmes business angels",
            "amoon",
        ),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "investment_thesis"),
        full_description_fields=("content", "body", "description", "presentation", "investment_thesis"),
        funding_fields=("ticket", "investment_range", "funding", "amount", "montant"),
        procedure_fields=("contact", "apply", "deal_submission"),
        default_device_type="investissement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
            "translate_investor_text": True,
        },
    ),
    SourceProfile(
        key="africa_business_heroes",
        source_kind="single_program_page",
        domains=("africabusinessheroes.org",),
        organism_markers=("africa business heroes", "abh", "fondation jack ma"),
        default_device_type="concours",
        close_date_fields=("deadline", "date_limite", "close_date"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("prize", "award", "funding", "amount", "rewards"),
        procedure_fields=("application", "how_to_apply", "timeline", "calendar"),
    ),
    SourceProfile(
        key="prix_pierre_castel",
        source_kind="pdf_manual",
        domains=("candidature-prix-pierre-castel.org", "prix-pierre-castel"),
        organism_markers=("prix pierre castel",),
        default_device_type="concours",
        close_date_fields=("deadline", "date_limite", "close_date"),
        short_description_fields=("summary", "resume", "presentation", "description"),
        full_description_fields=("content", "body", "presentation", "description", "reglement"),
        eligibility_fields=("eligibility", "conditions", "criteres", "candidats"),
        funding_fields=("dotation", "prix", "recompenses", "montant"),
        procedure_fields=("calendrier", "candidature", "depot", "selection"),
    ),
    SourceProfile(
        key="global_south_opportunities",
        source_kind="editorial_funding",
        domains=("globalsouthopportunities.com",),
        organism_markers=("global south opportunities",),
        title_fields=("title",),
        short_description_fields=("summary", "description"),
        full_description_fields=("content", "summary", "description"),
        eligibility_fields=("eligibility", "who_can_apply", "requirements"),
        funding_fields=("funding", "award", "prize", "amount"),
        procedure_fields=("how_to_apply", "application_process", "procedure"),
        close_date_fields=("deadline", "application_deadline"),
        default_device_type="subvention",
        default_status_without_close_date="standby",
        config_overrides={
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
        },
    ),
    SourceProfile(
        key="aecf",
        source_kind="editorial_funding",
        domains=("aecfafrica.org",),
        organism_markers=("africa enterprise challenge fund", "aecf"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation"),
        full_description_fields=("content", "body", "description", "presentation"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="subvention",
        default_status_without_close_date="standby",
        config_overrides={
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
        },
    ),
    SourceProfile(
        key="gsma_innovation_fund",
        source_kind="single_program_page",
        domains=("gsma.com/innovationfund", "gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/the-gsma-innovation-fund"),
        organism_markers=("gsma", "gsma innovation fund"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="subvention",
        default_status_without_close_date="standby",
        config_overrides={
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
        },
    ),
    SourceProfile(
        key="vc4a_programs",
        source_kind="listing",
        domains=("vc4a.com/programs",),
        organism_markers=("vc4a",),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements", "who_can_apply"),
        funding_fields=("funding", "grant", "amount", "award", "prize", "benefits"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline", "deadline"),
        close_date_fields=("deadline", "close_date", "date_limite", "application_deadline"),
        default_device_type="accompagnement",
        default_status_without_close_date="standby",
        config_overrides={
            "allow_english_text": True,
            "assume_standby_without_close_date": True,
        },
    ),
    SourceProfile(
        key="orange_corners_ocif",
        source_kind="single_program_page",
        domains=("orangecorners.com/more-than-incubation/orange-corners-innovation-fund-ocif",),
        organism_markers=("orange corners", "ocif"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket", "tracks"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="investissement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="baobab_network",
        source_kind="single_program_page",
        domains=("thebaobabnetwork.com/apply-now", "apply.thebaobabnetwork.com"),
        organism_markers=("baobab network",),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="investissement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="awdf_grants",
        source_kind="single_program_page",
        domains=("awdf.org/what-we-do/resourcing", "awdf.org/grants"),
        organism_markers=("awdf", "african women's development fund", "african womens development fund"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="subvention",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="janngo_capital",
        source_kind="single_program_page",
        domains=("janngo.com/investments", "janngo.com/contact-us"),
        organism_markers=("janngo capital", "janngo"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket", "investment"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline", "contact"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="investissement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="tlcom_capital",
        source_kind="single_program_page",
        domains=("tlcomcapital.com/contact-us", "tlcomcapital.com/about-old", "tlcomcapital.com"),
        organism_markers=("tlcom capital", "tlcom"),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket", "investment"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline", "contact"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="investissement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="villgro_africa",
        source_kind="single_program_page",
        domains=("villgroafrica.org/innovators/apply-now", "villgroafrica.org"),
        organism_markers=("villgro africa",),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "ticket", "investment"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline", "contact"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="accompagnement",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
    SourceProfile(
        key="tony_elumelu_foundation",
        source_kind="single_program_page",
        domains=("tonyelumelufoundation.org/tef-entrepreneurship-programme", "tonyelumelufoundation.org"),
        organism_markers=("tony elumelu foundation",),
        title_fields=("title", "name", "nom"),
        short_description_fields=("summary", "resume", "description", "presentation", "headline"),
        full_description_fields=("content", "body", "description", "presentation", "details"),
        eligibility_fields=("eligibility", "criteria", "conditions", "requirements"),
        funding_fields=("funding", "grant", "amount", "award", "seed capital"),
        procedure_fields=("application", "how_to_apply", "procedure", "calendar", "timeline"),
        close_date_fields=("deadline", "close_date", "date_limite"),
        default_device_type="subvention",
        default_status_without_close_date="recurring",
        config_overrides={
            "allow_english_text": True,
            "assume_recurring_without_close_date": True,
        },
    ),
)


def get_source_profile(source: dict) -> Optional[SourceProfile]:
    for profile in SOURCE_PROFILES:
        if profile.matches(source):
            return profile
    return None
