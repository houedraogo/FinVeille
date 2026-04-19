from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SourceProfile:
    key: str
    domains: tuple[str, ...] = ()
    organism_markers: tuple[str, ...] = ()
    title_fields: tuple[str, ...] = ()
    short_description_fields: tuple[str, ...] = ()
    full_description_fields: tuple[str, ...] = ()
    eligibility_fields: tuple[str, ...] = ()
    funding_fields: tuple[str, ...] = ()
    close_date_fields: tuple[str, ...] = ()
    status_fields: tuple[str, ...] = ()
    country_fields: tuple[str, ...] = ()
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
        domains=("api.les-aides.fr", "les-aides.fr"),
        organism_markers=("les-aides.fr",),
        title_fields=("title", "intitule", "nom", "name"),
        short_description_fields=("summary", "resume", "short_description", "description", "objectif"),
        full_description_fields=("description", "details", "contenu", "body", "presentation"),
        eligibility_fields=("conditions", "eligibility_criteria", "conditions_acces", "beneficiaires_conditions"),
        funding_fields=("funding_details", "montant", "nature_aide", "avantage", "aide"),
        close_date_fields=("close_date", "date_limite", "date_fin", "deadline"),
        status_fields=("status", "etat", "state"),
    ),
    SourceProfile(
        key="data_aides_entreprises",
        domains=("api.aides-entreprises.fr", "data.aides-entreprises.fr"),
        organism_markers=("aides entreprises",),
        title_fields=("aid_nom",),
        short_description_fields=("aid_objet",),
        full_description_fields=("aid_objet", "aid_operations_el"),
        eligibility_fields=("aid_conditions", "aid_benef"),
        funding_fields=("aid_montant",),
        close_date_fields=("date_fin",),
        status_fields=("status",),
        config_overrides={
            "close_date_fields": ["date_fin"],
            "status_fields": ["status"],
        },
    ),
    SourceProfile(
        key="world_bank",
        domains=("worldbank.org", "search.worldbank.org", "projects.worldbank.org"),
        organism_markers=("world bank", "banque mondiale"),
        title_fields=("project_name", "projectname"),
        short_description_fields=("project_abstract",),
        full_description_fields=("project_abstract",),
        funding_fields=("totalcommamt",),
        close_date_fields=("closingdate", "closing_date"),
        status_fields=("projectstatus", "status"),
        country_fields=("countryshortname",),
        config_overrides={
            "close_date_fields": ["closingdate", "closing_date"],
            "status_fields": ["projectstatus", "status"],
        },
    ),
)


def get_source_profile(source: dict) -> Optional[SourceProfile]:
    for profile in SOURCE_PROFILES:
        if profile.matches(source):
            return profile
    return None
