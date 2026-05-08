import json
import logging
import re
from datetime import date
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import dateparser
from bs4 import BeautifulSoup
from unidecode import unidecode

from app.collector.base_connector import RawItem
from app.collector.source_profiles import get_source_profile
from app.services.content_section_builder import build_content_sections, render_sections_markdown
from app.services.taxonomy_classifier import classify_taxonomy
from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    dedupe_text_fields,
    derive_device_status,
    extract_keywords,
    has_recurrence_evidence,
    looks_english_text,
    localize_investment_text,
    sanitize_text,
)

logger = logging.getLogger(__name__)

COUNTRY_MAP = {
    "france": "France",
    "français": "France",
    "francais": "France",
    "sénégal": "Sénégal",
    "senegal": "Sénégal",
    "côte d'ivoire": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "cote d’ivoire": "Côte d'Ivoire",
    "côte d’ivoire": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "maroc": "Maroc",
    "morocco": "Maroc",
    "tunisie": "Tunisie",
    "tunisia": "Tunisie",
    "cameroun": "Cameroun",
    "cameroon": "Cameroun",
    "mali": "Mali",
    "burkina faso": "Burkina Faso",
    "burkina": "Burkina Faso",
    "niger": "Niger",
    "togo": "Togo",
    "bénin": "Bénin",
    "benin": "Bénin",
    "guinée": "Guinée",
    "guinee": "Guinée",
    "guinea": "Guinée",
    "madagascar": "Madagascar",
    "rdc": "RD Congo",
    "congo": "RD Congo",
    "rd congo": "RD Congo",
    "nigeria": "Nigeria",
    "nigéria": "Nigeria",
    "ghana": "Ghana",
    "kenya": "Kenya",
    "afrique du sud": "Afrique du Sud",
    "south africa": "Afrique du Sud",
    "éthiopie": "Éthiopie",
    "ethiopia": "Éthiopie",
}

DEVICE_TYPE_RULES = {
    "subvention": ["subvention", "aide directe", "dotation", "fonds perdus", "grant", "aide non remboursable"],
    "pret": ["prêt", "loan", "crédit public", "emprunt"],
    "avance_remboursable": ["avance remboursable", "avance récupérable"],
    "garantie": ["garantie", "cautionnement", "contre-garantie"],
    "credit_impot": ["crédit d'impôt", "cir ", "cii ", "jei", "tax credit"],
    "exoneration": ["exonération", "abattement fiscal", "réduction de charges"],
    "aap": ["appel à projets", "appel a projets", "aap", "call for projects", "appel à candidatures"],
    "ami": ["appel à manifestation", "appel a manifestation", " ami ", "expression d'intérêt"],
    "accompagnement": ["accompagnement", "incubation", "accélération", "mentorat", "coaching public"],
    "concours": ["concours", "prix ", "trophée", "award", "compétition"],
    "investissement": [
        "capital-risque",
        "venture capital",
        "fonds d'investissement",
        "business angel",
        "prise de participation",
        "equity",
        "capital-développement",
        "capital investissement",
        "seed fund",
        "series a",
        "series b",
        "amorçage",
        "love money",
        "investisseur",
    ],
}

DATA_AIDES_RECURRING_HOSTS = {
    "www.bpifrance.fr",
    "diag.bpifrance.fr",
    "diagecoconception.bpifrance.fr",
    "bpifrance-creation.fr",
    "www.inpi.fr",
    "www.siagi.com",
    "www.bretagneactive.org",
    "www.urssaf.fr",
    "scientipolecapital.fr",
    "www.bje-capital-risque.com",
    "www.bretagne-capital-solidaire.fr",
    "www.bretagne.bzh",
    "www.normandie.fr",
    "www.auvergnerhonealpes.fr",
    "www.paysdelaloire.fr",
    "www.vte-france.fr",
    "www.ademe.fr",
    "anct.gouv.fr",
    "bofip.impots.gouv.fr",
}

DATA_AIDES_RECURRING_BLOCKERS = (
    "appel a projets",
    "appel à projets",
    "appel a candidature",
    "appel à candidature",
    "concours",
    "phase b",
    "jusqu'au ",
    "jusqu au ",
    "avant le ",
    "au plus tard le ",
)

SECTOR_RULES = {
    "agriculture": ["agricult", "agro", "alimentaire", "rural", "élevage", "pêche", "agroalimentaire"],
    "energie": ["énergie", "energy", "solaire", "renouvelable", "électricité", "photovoltaïque", "biogaz"],
    "sante": ["santé", "médical", "health", "hôpital", "pharmaceutical", "médicament", "biotech"],
    "numerique": ["numérique", "digital", "tech", "logiciel", "ia ", "intelligence artificielle", "fintech", "e-commerce"],
    "education": ["éducation", "formation", "école", "université", "enseignement", "apprentissage"],
    "environnement": ["environnement", "climat", "biodiversité", "écologi", "transition écologique", "économie circulaire"],
    "industrie": ["industrie", "manufacture", "production", "usine", "mécanique", "métallurgie"],
    "tourisme": ["tourisme", "hospitality", "hôtellerie", "patrimoine"],
    "transport": ["transport", "logistique", "mobilité", "infrastructure routière"],
    "culture": ["culture", "créatif", "audiovisuel", "patrimoine", "art "],
    "immobilier": ["immobilier", "logement", "habitat", "btp", "construction"],
    "finance": ["finance", "assurance", "bancaire", "microfinance"],
    "eau": ["eau", "assainissement", "irrigation", "hydraulique"],
    "social": ["social", "insertion", "handicap", "solidarité", "emploi"],
}

BENEFICIARY_RULES = {
    "startup": ["startup", "jeune entreprise", "entreprise innovante"],
    "pme": ["pme", "tpe", "artisan", "commerçant", "petite entreprise"],
    "eti": ["eti", "entreprise de taille intermédiaire"],
    "association": ["association", "ong", "organisation non gouvernementale"],
    "collectivite": ["collectivité", "commune", "département", "région", "intercommunalité"],
    "porteur_projet": ["porteur de projet", "créateur", "entrepreneur"],
    "agriculteur": ["agriculteur", "exploitant agricole", "paysan"],
    "chercheur": ["chercheur", "laboratoire", "université", "établissement d'enseignement"],
}

CLOSE_DATE_FIELDS = [
    "close_date",
    "date_fin",
    "dateFin",
    "date_de_fin_du_projet",
    "dateDeFinDuProjet",
    "date_dachevement",
    "date_achevement",
    "date_fin_candidature",
    "dateFinCandidature",
    "date_cloture",
    "dateCloture",
    "date_limite",
    "dateLimite",
    "date_limite_candidature",
    "dateLimiteCandidature",
    "end_date",
    "endDate",
    "deadline",
    "deadlineDate",
    "closingdate",
    "closing_date",
    "application_deadline",
]

OPEN_DATE_FIELDS = [
    "open_date",
    "date_ouverture",
    "dateOuverture",
    "openingdate",
    "opening_date",
    "start_date",
    "publication_date",
    "published_at",
]

UNUSABLE_CONTENT_MARKERS = (
    "aucun contenu exploitable trouve",
    "aucun contenu editorial exploitable trouve",
    "impossible d'acceder a l'url",
    "token invalide ou expire",
    "javascript dynamique",
    "structure html trop pauvre",
    "access denied",
    "forbidden",
    "not found",
)


class Normalizer:
    def __init__(self, source: dict):
        self.source = source
        self.default_country = source.get("country", "")
        self.organism = source.get("organism", "")
        self.profile = get_source_profile(source)
        self.config = {**(source.get("config") or {})}
        if self.profile:
            for key, value in self.profile.config_overrides.items():
                if value and not self.config.get(key):
                    self.config[key] = value

    def _looks_like_data_aides_recurring_offer(
        self,
        *,
        item: RawItem,
        normalized_title: str,
        raw_body: str,
        metadata: dict,
        close_date: Optional[date],
    ) -> bool:
        if not self.profile or self.profile.key != "data_aides_entreprises" or close_date is not None:
            return False

        host = (urlparse(item.url or "").netloc or "").lower()
        if host not in DATA_AIDES_RECURRING_HOSTS:
            return False

        text = sanitize_text(
            " ".join(
                part
                for part in (
                    normalized_title,
                    raw_body,
                    self._metadata_value_to_text(metadata),
                )
                if part
            )
        ).lower()
        if any(marker in text for marker in DATA_AIDES_RECURRING_BLOCKERS):
            return False

        recurring_types = {"pret", "garantie", "accompagnement", "investissement", "autre", "exoneration"}
        if (self._detect_device_type(text) or "") in recurring_types:
            return True

        recurring_markers = (
            "catalogue-offres",
            "diagnostic",
            "diag ",
            "diag-",
            "garantie",
            "pret",
            "prêt",
            "credit-bail",
            "crédit-bail",
            "fonds direct",
            "pass pi",
            "redevances brevets",
            "volontariat territorial en entreprise",
        )
        return any(marker in text for marker in recurring_markers)

    def normalize(self, item: RawItem) -> Optional[Dict[str, Any]]:
        raw_body = clean_editorial_text(item.raw_content or "")
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        if self._is_unusable_content(raw_body, metadata):
            logger.info("[Normalizer] Item ignore car contenu source inexploitable: %s", item.title[:120])
            return None
        if self._should_skip_source_item(item, raw_body):
            logger.info("[Normalizer] Item ignore car hors perimetre source: %s", item.title[:120])
            return None
        if looks_english_text(raw_body) and not self.config.get("allow_english_text"):
            logger.info(f"[Normalizer] Item ignoré car description anglaise: {item.title[:120]}")
            return None

        normalized_title = self._normalize_title_for_source(item.title, raw_body, metadata)
        text = sanitize_text(f"{normalized_title} {raw_body}").lower()
        close_date = self._extract_metadata_date(item, "close") or self._extract_date(text, "close")
        open_date = self._extract_metadata_date(item, "open") or self._extract_date(text, "open")
        initial_status = self._extract_metadata_status(item) or self._detect_status(text)
        is_recurring = False
        recurrence_notes = None
        normalized_status_text = unidecode(text)
        has_reliable_recurrence_evidence = has_recurrence_evidence(text) and not any(
            marker in normalized_status_text
            for marker in (
                "sans date limite communiquee",
                "date limite non communiquee",
                "cloture non communiquee",
                "aucune date limite communiquee",
                "sans date limite explicite",
                "date limite explicite",
            )
        )
        if initial_status == "open" and not close_date and has_reliable_recurrence_evidence:
            initial_status = "recurring"
            is_recurring = True
            recurrence_notes = (
                "Classe automatiquement comme dispositif recurrent: "
                "le texte source indique un fonctionnement sans fenetre de cloture unique."
            )
        elif (
            self.profile
            and self.profile.default_status_without_close_date == "recurring"
            and not close_date
            and initial_status == "open"
        ):
            initial_status = "recurring"
            is_recurring = True
            recurrence_notes = (
                "Classe automatiquement comme dispositif recurrent: "
                "le profil source indique un fonctionnement sans fenetre de cloture unique."
            )
        elif (
            self.profile
            and self.profile.default_status_without_close_date == "standby"
            and not close_date
            and initial_status == "open"
        ):
            initial_status = "standby"
        elif self.config.get("assume_recurring_without_close_date") and not close_date and initial_status == "open":
            initial_status = "recurring"
            is_recurring = True
            recurrence_notes = (
                "Classe automatiquement comme dispositif recurrent: "
                "la source n'expose pas de date de cloture fiable."
            )
        elif (
            (self.config.get("assume_standby_without_close_date") or (self.profile and self.profile.key == "les_aides"))
            and not close_date
            and initial_status == "open"
        ):
            initial_status = "standby"
        if (
            initial_status in {"open", "standby"}
            and self._looks_like_data_aides_recurring_offer(
                item=item,
                normalized_title=normalized_title,
                raw_body=raw_body,
                metadata=metadata,
                close_date=close_date,
            )
        ):
            initial_status = "recurring"
            is_recurring = True
            recurrence_notes = (
                "Classe automatiquement comme dispositif permanent : "
                "la page source presente une offre continue sans date limite exploitable."
            )
        short_description = self._build_short_description(item, raw_body, metadata, close_date)
        full_description = self._build_full_description(item, raw_body, metadata, close_date, open_date)
        extra_fields = self._extract_source_specific_fields(normalized_title, raw_body, metadata, close_date, open_date)
        short_description = extra_fields.get("short_description") or short_description
        short_description, full_description, funding_details, eligibility_criteria = dedupe_text_fields(
            short_description,
            extra_fields.get("full_description") or full_description,
            extra_fields.get("funding_details"),
            extra_fields.get("eligibility_criteria"),
        )
        if self.profile and self.profile.key in {
            "les_aides",
            "data_aides_entreprises",
            "banque_des_territoires",
            "ademe",
            "prix_pierre_castel",
            "private_investor",
            "africa_business_heroes",
            "global_south_opportunities",
            "orange_corners_ocif",
            "baobab_network",
            "awdf_grants",
            "janngo_capital",
            "tlcom_capital",
            "villgro_africa",
        }:
            eligibility_criteria = extra_fields.get("eligibility_criteria") or eligibility_criteria
            funding_details = extra_fields.get("funding_details") or funding_details

        final_full_description = self._finalize_structured_full_description(
            item=item,
            metadata=metadata,
            normalized_title=normalized_title,
            full_description=full_description,
            short_description=short_description,
            eligibility_criteria=eligibility_criteria,
            funding_details=funding_details,
            open_date=open_date,
            close_date=close_date,
            recurrence_notes=recurrence_notes,
        )
        taxonomy = classify_taxonomy(
            {
                "title": normalized_title,
                "organism": self.organism,
                "device_type": self._detect_device_type(text),
                "short_description": short_description,
                "full_description": final_full_description,
                "eligibility_criteria": eligibility_criteria,
                "funding_details": funding_details,
                "source_raw": self._build_source_raw(item),
                "status": initial_status,
                "is_recurring": is_recurring,
                "recurrence_notes": recurrence_notes,
            },
            self.source,
        )
        device_type = taxonomy.device_type
        profile_device_type = self.config.get("default_device_type") or (
            self.profile.default_device_type if self.profile else None
        )
        if profile_device_type and (device_type == "autre" or self.config.get("force_device_type")):
            device_type = str(profile_device_type)

        source_raw = self._build_source_raw(item)
        payload = {
            "title": normalized_title,
            "organism": self.organism,
            "country": self._detect_country(text) or self.default_country,
            "source_url": item.url,
            "source_raw": source_raw,
            "device_type": device_type,
            "sectors": self._detect_sectors(text) or ["transversal"],
            "beneficiaries": self._detect_beneficiaries(text),
            "short_description": short_description,
            "full_description": final_full_description,
            "eligibility_criteria": eligibility_criteria,
            "close_date": close_date,
            "open_date": open_date,
            "amount_min": self._extract_amount(text, "min"),
            "amount_max": self._extract_amount(text, "max"),
            "currency": self._detect_currency(text),
            "keywords": extract_keywords(normalized_title),
            "status": derive_device_status(close_date, initial_status),
            "is_recurring": is_recurring,
            "recurrence_notes": recurrence_notes,
            "language": self.source.get("language", "fr"),
            "source_id": self.source.get("id"),
            "tags": [taxonomy.taxonomy_tag],
        }
        if funding_details:
            payload["funding_details"] = funding_details
        for key, value in extra_fields.items():
            if key in {"full_description", "funding_details", "eligibility_criteria"}:
                continue
            payload[key] = value
        sections = build_content_sections(payload, self.source)
        payload["content_sections_json"] = sections
        payload["full_description"] = render_sections_markdown(sections) or payload["full_description"]
        return payload

    def _should_skip_source_item(self, item: RawItem, raw_body: str) -> bool:
        if not self.profile:
            return False

        if self.profile.key == "aecf":
            text = unidecode(f"{item.title or ''} {raw_body or ''}".lower())
            if "open competition" not in text and "difec" not in text and "digital innovation fund for energy" not in text:
                return True
            if any(marker in text for marker in ("annual report", "regional workshop", "read our", "who regional workshop")):
                return True

        return False

    def _normalize_title_for_source(self, title: str, raw_body: str, metadata: dict) -> str:
        cleaned = sanitize_text(title or "")
        source_url = (self.source.get("url") or "").lower()
        body = sanitize_text(raw_body or "").lower()
        profile_title = self._get_profile_text(metadata, getattr(self.profile, "title_fields", ()))
        if profile_title:
            cleaned = sanitize_text(profile_title)

        if "africabusinessheroes.org" in source_url:
            return "Africa's Business Heroes (ABH) 2026" if "2026" in body else "Africa's Business Heroes (ABH)"
        if "thebaobabnetwork.com/apply-now" in source_url:
            return "Baobab Network - accelerateur pour startups africaines"
        if "awdf.org/what-we-do/resourcing" in source_url or "awdf.org/grants" in source_url:
            return "AWDF - grantmaking for African women's organisations"
        if "janngo.com/investments" in source_url:
            return "Janngo Capital - investissement dans les startups africaines"
        if "tlcomcapital.com/contact-us" in source_url or "tlcomcapital.com/about-old" in source_url:
            return "TLcom Capital - investissement dans les startups africaines"
        if "villgroafrica.org/innovators/apply-now" in source_url:
            return "Villgro Africa - incubation et financement sante en Afrique"

        return cleaned

    def _extract_source_specific_fields(
        self,
        normalized_title: str,
        raw_body: str,
        metadata: dict,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        source_url = (self.source.get("url") or "").lower()
        if self.profile and self.profile.key == "private_investor":
            investor_fields = self._build_private_investor_fields(
                normalized_title,
                raw_body,
                metadata,
                close_date,
                open_date,
            )
            if investor_fields:
                return investor_fields
        if self.profile and self.profile.key == "aecf":
            return self._build_aecf_fields(normalized_title, raw_body, close_date, open_date)
        if "globalsouthopportunities.com" in source_url or (self.profile and self.profile.key == "global_south_opportunities"):
            return self._build_global_south_opportunities_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "orange_corners_ocif":
            return self._build_orange_corners_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "baobab_network":
            return self._build_baobab_network_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "awdf_grants":
            return self._build_awdf_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "janngo_capital":
            return self._build_janngo_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "tlcom_capital":
            return self._build_tlcom_fields(normalized_title, raw_body, close_date, open_date)
        if self.profile and self.profile.key == "villgro_africa":
            return self._build_villgro_fields(normalized_title, raw_body, close_date, open_date)

        is_abh = "africabusinessheroes.org" in source_url or (
            self.profile and self.profile.key == "africa_business_heroes"
        )
        if not is_abh:
            profile_fields = self._build_profile_sections(metadata, close_date, open_date, raw_body=raw_body)
            if profile_fields:
                return profile_fields
            return {}

        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "Africa's Business Heroes (ABH) est un concours panafricain qui identifie, soutient et met en valeur "
            "des entrepreneurs africains Ã  fort impact. Le programme accompagne la prochaine gÃ©nÃ©ration "
            "d'entrepreneurs du continent Ã  travers un concours annuel, de la visibilitÃ©, du mentorat et un "
            "accÃ¨s renforcÃ© Ã  l'Ã©cosystÃ¨me."
        )

        eligibility = (
            "Le concours accueille des candidatures issues de tous les pays africains, de tous les secteurs "
            "et de toutes les tranches d'Ã¢ge. Les entreprises doivent Ãªtre officiellement enregistrÃ©es, "
            "avoir leur siÃ¨ge en Afrique et justifier d'au moins trois ans d'existence."
        )

        rewards = (
            "Chaque annÃ©e, dix finalistes sont sÃ©lectionnÃ©s pour la grande finale du concours ABH et "
            "peuvent remporter une part de 1,5 million de dollars de subventions. Le programme apporte aussi "
            "de la visibilitÃ©, du mentorat, de la formation et un accÃ¨s Ã  l'Ã©cosystÃ¨me entrepreneurial."
        )

        calendar = []
        if open_date:
            calendar.append(f"- Ouverture des candidatures : {open_date.strftime('%d/%m/%Y')}")
        if close_date:
            calendar.append(f"- Date limite de candidature : {close_date.strftime('%d/%m/%Y')}")
        if not calendar and "28 avril 2026" in body.lower():
            calendar.append("- Date limite de candidature : 28/04/2026")

        full_sections = [
            f"## PrÃ©sentation\n{presentation}",
            f"## CritÃ¨res d'Ã©ligibilitÃ©\n{eligibility}",
            f"## RÃ©compenses\n{rewards}",
        ]
        if calendar:
            full_sections.append("## Calendrier\n" + "\n".join(calendar))

        short_description = (
            "Concours panafricain de la Fondation Jack Ma destinÃ© aux entrepreneurs africains. "
            "La candidature 2026 est ouverte jusqu'au 28 avril 2026."
            if close_date
            else "Concours panafricain de la Fondation Jack Ma destinÃ© aux entrepreneurs africains."
        )

        return {
            "short_description": short_description,
            "full_description": "\n\n".join(full_sections),
            "eligibility_criteria": eligibility,
            "funding_details": rewards,
            "device_type": "concours",
            "aid_nature": "subvention",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["entrepreneurs", "startups", "PME"],
            "sectors": ["transversal", "entrepreneuriat", "innovation"],
            "keywords": extract_keywords(normalized_title + " entrepreneurs africains concours"),
        }

    def _build_orange_corners_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "Orange Corners Innovation Fund (OCIF) soutient les jeunes entrepreneurs issus des programmes "
            "d'incubation et d'acceleration Orange Corners. Le fonds repond aux besoins de financement "
            "des startups a impact en Afrique, au Moyen-Orient et en Asie du Sud-Est en combinant capital, "
            "assistance technique et accompagnement a l'investissement."
        )
        if "2019" in body or "2030" in body:
            presentation += (
                " Lance en 2019, le dispositif poursuit son extension internationale et doit se prolonger "
                "au moins jusqu'en 2030."
            )

        eligibility = (
            "Le fonds s'adresse prioritairement aux entrepreneurs participant aux programmes Orange Corners "
            "dans les pays couverts par OCIF, avec une ouverture explicite a la Tunisie pour le premier track. "
            "La selection du second track se fait en fin de cohorte via une competition de pitch devant un jury expert."
        )

        funding = (
            "Le dispositif comporte deux volets. Track 1 : bon de prototypage et allocation mensuelle, "
            "jusqu'a 5 000 EUR par entrepreneur. Track 2 : financement seed jusqu'a 50 000 EUR par entrepreneur, "
            "sous forme mixte subvention + pret, avec 12 a 18 mois d'accompagnement complementaire."
        )

        procedure = (
            "L'entree dans OCIF se fait via les programmes Orange Corners locaux. Les entrepreneurs concernes "
            "sont ensuite orientes vers le track adapte a leur stade puis, pour le second track, selectionnes "
            "par competition de pitch selon les modalites locales."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "Le fonds fonctionne par cohortes et mecanismes recurrents sans date limite unique publique "
                "au niveau global."
            ),
        )

        return {
            "short_description": (
                "Fonds Orange Corners pour startups a impact, avec tickets jusqu'a 50 000 EUR "
                "et accompagnement renforce via des cohortes recurrentes."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "investissement",
            "aid_nature": "capital",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "multi_pays",
            "beneficiaries": ["startups", "entrepreneurs"],
            "sectors": ["numerique", "innovation", "entrepreneuriat"],
            "specific_conditions": (
                "Les modalites de financement et la structure exacte subvention/pret peuvent varier selon le contexte local."
            ),
            "required_documents": (
                "Les documents de candidature et les conditions precises doivent etre verifies aupres du programme Orange Corners local."
            ),
            "keywords": extract_keywords(normalized_title + " orange corners entrepreneurs startup impact"),
        }

    def _build_baobab_network_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "Baobab Network accompagne et finance des startups africaines a fort potentiel via un accelerator "
            "tres operationnel. Le programme combine premier cheque, appui venture, reseau international "
            "et soutien a la croissance pour des entreprises technologiques en phase early-stage."
        )

        eligibility = (
            "Le programme cible des startups tech orientees business, a but lucratif, qui disposent idealement "
            "d'un MVP et de premiers signes de traction. Les candidatures a l'etape idee pure sont moins prioritaires "
            "et doivent au minimum demontrer une demande de marche deja validee."
        )

        funding = (
            "Baobab met en avant un ticket initial d'environ 100 000 USD pour accelerer la croissance de la startup, "
            "avec des options complementaires de co-investissement, venture debt et follow-on fund selon l'evolution de l'entreprise."
        )

        procedure = (
            "Les candidatures sont acceptees en continu. La page officielle indique une logique rolling basis, "
            "avec un prochain cohort kick-off mentionne en Q4 2025. Les fondateurs doivent postuler via la plateforme Baobab."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "Le programme fonctionne sur un rythme recurrent avec candidatures en continu plutot qu'une date limite publique unique."
            ),
        )

        return {
            "title": "Baobab Network - accelerator for African startups",
            "short_description": (
                "Accelerateur pan-africain pour startups tech, avec candidature en continu et ticket initial autour de 100 000 USD."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "investissement",
            "aid_nature": "capital",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["startups", "entrepreneurs"],
            "sectors": ["numerique", "innovation", "finance"],
            "specific_conditions": (
                "Le programme privilegie les structures for-profit et une preuve de traction ou de validation de marche."
            ),
            "required_documents": (
                "Le detail du dossier et des informations demandees doit etre confirme sur la plateforme de candidature Baobab."
            ),
            "keywords": extract_keywords(normalized_title + " baobab accelerator africa startups venture"),
        }

    def _build_awdf_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "L'African Women's Development Fund (AWDF) finance et accompagne des organisations africaines "
            "qui renforcent durablement les droits, le pouvoir d'action et la reconnaissance des femmes. "
            "Le grantmaking soutient des structures etabliies comme de petites organisations locales."
        )

        eligibility = (
            "Pour etre eligibles, les organisations doivent etre dirigees et gerees par des femmes, ou porter "
            "un projet centre sur les femmes avec une gouvernance feminine claire. Elles doivent s'inscrire dans "
            "une strategie locale, nationale ou regionale d'autonomisation des femmes, disposer de systemes "
            "organisationnels de base et justifier d'au moins trois ans d'existence."
        )

        funding = (
            "AWDF propose des subventions flexibles et specialisees pour soutenir les organisations de femmes, "
            "leurs projets structurants, ainsi que des opportunites d'apprentissage, de reseautage et de "
            "valorisation des contributions des femmes africaines."
        )

        procedure = (
            "La page officielle renvoie vers la demande de grant AWDF. Les porteuses doivent verifier la fenetre "
            "d'ouverture active, les formulaires en cours et les modalites de depot directement sur le site AWDF."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "Le grantmaking AWDF fonctionne selon des ouvertures recurrentes ou variables, sans date limite "
                "publique unique visible sur cette page de reference."
            ),
        )

        return {
            "title": "AWDF - subventions pour organisations de femmes en Afrique",
            "short_description": (
                "Programme de subventions AWDF pour organisations africaines dirigees par des femmes, "
                "avec grantmaking recurrent et criteres d'eligibilite explicites."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "subvention",
            "aid_nature": "subvention",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["associations", "ong", "organisations de femmes"],
            "sectors": ["social", "egalite", "impact"],
            "specific_conditions": (
                "AWDF ne finance pas les partis politiques, les financements individuels, les administrations "
                "publiques, les bourses d'etudes et les organisations de femmes qui ne sont pas effectivement dirigees par des femmes."
            ),
            "required_documents": (
                "Le detail du dossier, des formulaires et des pieces demandees doit etre confirme sur la page AWDF "
                "de demande de grant au moment de la candidature."
            ),
            "keywords": extract_keywords(normalized_title + " awdf women africa grants feminist organisations"),
        }

    def _build_janngo_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "Janngo Capital investit dans des startups africaines early stage, technologiques ou tech-enabled, "
            "avec une these panafricaine orientee croissance, impact et inclusion. Le fonds met en avant une "
            "forte exposition aux startups fondees, cofondees ou beneficiant aux femmes."
        )

        eligibility = (
            "Le dispositif cible des startups africaines en phase early stage actives sur des marches de croissance. "
            "Les entreprises recherchees doivent contribuer a l'acces a des biens et services essentiels, a "
            "l'acces au marche ou au capital pour les PME africaines, ou a la creation d'emplois durables a grande echelle."
        )

        funding = (
            "Janngo Capital investit entre 50 000 euros et 5 millions d'euros dans des startups tech ou "
            "tech-enabled. Le fonds combine capital financier et accompagnement operationnel via une equipe "
            "interne d'operating partners et d'experts."
        )

        procedure = (
            "La page officielle invite les fondateurs a prendre contact avec Janngo Capital. L'instruction se fait "
            "ensuite via echanges, evaluation du profil startup, pitch avec l'equipe puis comite d'investissement "
            "et discussion de term sheet si le dossier avance."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "Janngo Capital fonctionne comme un investisseur recurrent sans fenetre publique unique de cloture."
            ),
        )

        return {
            "title": "Janngo Capital - investissement dans les startups africaines",
            "short_description": (
                "Fonds panafricain early stage pour startups tech, avec tickets de 50 000 EUR a 5 M EUR "
                "et these forte sur l'impact et l'inclusion."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "investissement",
            "aid_nature": "capital",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["startups", "entrepreneurs", "pme"],
            "sectors": ["numerique", "sante", "finance", "agriculture", "mobilite"],
            "specific_conditions": (
                "Le fonds privilegie les startups technologiques ou tech-enabled en croissance, avec une attention "
                "forte a l'impact et a l'entrepreneuriat feminin."
            ),
            "required_documents": (
                "Le detail des informations demandees doit etre confirme directement avec Janngo Capital au moment "
                "de la prise de contact."
            ),
            "keywords": extract_keywords(normalized_title + " janngo capital africa venture women startups"),
        }

    def _build_tlcom_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "TLcom Capital investit dans des startups technologiques africaines a fort potentiel, avec une "
            "approche venture capital orientee croissance, execution et passage a l'echelle. Le fonds accompagne "
            "des fondateurs capables de construire des entreprises scalables sur des marches africains."
        )

        eligibility = (
            "Le dispositif cible des startups africaines technologiques ou tech-enabled, ambitieuses, scalables "
            "et en capacite de demonstrer un potentiel de croissance solide. La page officielle s'adresse "
            "principalement aux fondateurs qui souhaitent pitcher une entreprise a TLcom Capital."
        )

        funding = (
            "TLcom Capital intervient comme investisseur venture sur des startups africaines en croissance. "
            "La page publique ne communique pas ici de ticket standard unique, mais met en avant un partenariat "
            "capitalistique avec accompagnement strategique, expertise venture et soutien a l'execution."
        )

        procedure = (
            "Les fondateurs peuvent soumettre leur dossier via le point d'entree 'Pitch Us' de TLcom Capital. "
            "L'instruction se poursuit ensuite via revue du pitch, echanges avec l'equipe d'investissement et "
            "evaluation du fit avant poursuite eventuelle du processus."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "TLcom Capital fonctionne comme un investisseur recurrent sans fenetre publique unique de cloture."
            ),
        )

        return {
            "title": "TLcom Capital - investissement dans les startups africaines",
            "short_description": (
                "Fonds venture capital actif en Afrique pour startups technologiques a fort potentiel, avec "
                "soumission continue des dossiers via le point d'entree founders."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "investissement",
            "aid_nature": "capital",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["startups", "entrepreneurs", "pme"],
            "sectors": ["numerique", "finance", "logistique", "commerce", "sante"],
            "specific_conditions": (
                "Le fonds privilegie des startups africaines technologiques et scalables, capables de soutenir "
                "une trajectoire de croissance venture."
            ),
            "required_documents": (
                "Le detail du dossier, du pitch et des informations demandees doit etre confirme directement via "
                "le formulaire de prise de contact TLcom Capital."
            ),
            "keywords": extract_keywords(normalized_title + " tlcom capital africa venture startups pitch"),
        }

    def _build_villgro_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        presentation = (
            "Villgro Africa accompagne des innovations sante et life sciences en Afrique via un dispositif "
            "d'incubation, d'appui a l'investissement et de structuration business. Le programme vise des "
            "startups capables d'ameliorer durablement l'acces a des solutions de sante sur le continent."
        )

        eligibility = (
            "Les innovateurs candidats doivent disposer d'une equipe pluridisciplinaire, d'un problem-solution fit, "
            "d'un product-market fit, d'un produit minimum viable deja construit, d'une demande de marche validee, "
            "d'un modele de revenus clair, d'un fondateur a temps plein engage dans le programme et d'au moins "
            "un cofondateur technique."
        )

        funding = (
            "Villgro Africa combine incubation, accompagnement a l'investissement et acces a des financeurs a impact "
            "dans la sante. La page publique met en avant un appui en seed funding, en structuration d'entreprise "
            "et en preparation a l'investissement plutot qu'un montant unique garanti a chaque candidat."
        )

        procedure = (
            "Les candidatures sont acceptees sur une base continue. Chaque soumission est revue par un portfolio "
            "manager, puis peut faire l'objet de demandes d'informations complementaires dans le cadre de la due "
            "diligence. Si le dossier entre dans le mandat de Villgro Africa, l'equipe recontacte le porteur "
            "dans un delai pouvant aller jusqu'a un mois."
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure=procedure,
            close_date=close_date,
            open_date=open_date,
            recurrence_notes=(
                "Villgro Africa accepte les candidatures sur une base continue, sans date limite publique unique."
            ),
        )

        return {
            "title": "Villgro Africa - incubation et financement sante en Afrique",
            "short_description": (
                "Programme recurrent pour startups sante et life sciences en Afrique, avec incubation, "
                "preparation a l'investissement et revue des candidatures en continu."
            ),
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": "accompagnement",
            "aid_nature": "incubation",
            "country": "Afrique",
            "region": "Afrique",
            "zone": "Afrique",
            "geographic_scope": "continental",
            "beneficiaries": ["startups", "entrepreneurs", "chercheurs", "pme"],
            "sectors": ["sante", "biotechnologies", "medtech", "numerique"],
            "specific_conditions": (
                "Le programme cible des innovations sante avec traction produit et marche minimale, ainsi qu'une "
                "equipe fondatrice suffisamment structuree pour entrer en incubation active."
            ),
            "required_documents": (
                "Le detail des informations et pieces demandees doit etre confirme au moment de la candidature "
                "sur la page officielle Villgro Africa."
            ),
            "keywords": extract_keywords(normalized_title + " villgro africa healthcare medtech biotech incubation"),
        }

    def _build_aecf_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        text = unidecode(f"{normalized_title} {raw_body}".lower())

        if "difec" in text or "digital innovation fund for energy" in text:
            presentation = (
                "Le programme DIFEC de l'AECF soutient des entreprises africaines developpant des solutions "
                "numeriques pour l'energie propre, la resilience climatique, l'agriculture digitale et des "
                "modeles circulaires. Il combine financement catalytique et appui technique pour accelerer "
                "des innovations a fort potentiel sur plusieurs marches africains."
            )
            eligibility = (
                "Le programme cible des entreprises early stage ou growth stage developpant des solutions "
                "digitales liees a l'acces a l'energie, au clean cooking, a la productive use of energy, "
                "a l'e-mobility, a l'agriculture numerique ou a la resilience climatique. Les candidats "
                "doivent demontrer un produit ou une traction coherente avec leur fenetre de financement."
            )
            funding = (
                "AECF ouvre deux fenetres de financement dans DIFEC. La fenetre Growing vise des entreprises "
                "plus amont avec des grants de 150 000 a 300 000 USD. La fenetre Scaling vise des entreprises "
                "avec traction commerciale et peut aller de 250 000 a 400 000 USD, avec logique de matching."
            )
            procedure = (
                "Les candidatures se font en reponse a l'appel officiel AECF. La selection comprend une revue "
                "du dossier, l'analyse du fit programme, puis une instruction plus poussee pour les dossiers "
                "retenus, avec verification des capacites de cofinancement et du potentiel de passage a l'echelle."
            )
            full_description = build_structured_sections(
                presentation=presentation,
                eligibility=eligibility,
                funding=funding,
                procedure=procedure,
                close_date=close_date,
                open_date=open_date,
            )
            return {
                "title": "AECF - Digital Innovation Fund for Energy & Climate (DIFEC)",
                "short_description": (
                    "Appel regional AECF pour entreprises africaines developpant des solutions digitales "
                    "energie-climat, avec deux fenetres de financement de 150 000 a 400 000 USD."
                ),
                "full_description": full_description,
                "eligibility_criteria": eligibility,
                "funding_details": funding,
                "device_type": "subvention",
                "aid_nature": "grant",
                "country": "Afrique",
                "region": "Afrique",
                "zone": "Afrique",
                "geographic_scope": "continental",
                "beneficiaries": ["startups", "entreprises", "pme"],
                "sectors": ["energie", "climat", "numerique", "agriculture"],
                "source_url": "https://www.aecfafrica.org/approach/our-programmes/renewable-energy/react-2-0-regional-digital-innovation-fund-for-energy-climate-programme-difec/",
                "keywords": extract_keywords(normalized_title + " aecf difec energy climate africa grants"),
            }

        if "women entrepreneurship" in text or "benin and burkina faso" in text:
            presentation = (
                "L'AECF soutient l'entrepreneuriat feminin dans une economie plus verte au Benin et au Burkina Faso "
                "via un programme de plusieurs annees qui combine grants, appui a l'acces au financement et "
                "renforcement des entreprises ou organisations ciblees."
            )
            eligibility = (
                "Le programme cible notamment des PME dirigees par des femmes, des cooperatives, des associations "
                "et des intermediaires financiers capables de renforcer l'activite economique des femmes dans des "
                "secteurs a impact climat et inclusion."
            )
            funding = (
                "Le programme comporte plusieurs fenetres. Des financements remboursables ou non remboursables "
                "peuvent etre mobilises pour les PME et intermediaires financiers, ainsi que des grants dedies "
                "aux cooperatives et associations de femmes selon les volets ouverts."
            )
            procedure = (
                "Les candidatures se font via les appels AECF associes au programme. L'instruction comprend une "
                "reponse au call, la revue des criteres d'eligibilite, puis une evaluation plus detaillee pour "
                "les candidatures preselectionnees."
            )
            full_description = build_structured_sections(
                presentation=presentation,
                eligibility=eligibility,
                funding=funding,
                procedure=procedure,
                close_date=close_date,
                open_date=open_date,
            )
            return {
                "title": "AECF - entrepreneuriat feminin pour une economie plus verte au Benin et au Burkina Faso",
                "short_description": (
                    "Programme AECF de financement et d'appui a l'entrepreneuriat feminin au Benin et au "
                    "Burkina Faso, avec plusieurs fenetres de soutien selon le profil du porteur."
                ),
                "full_description": full_description,
                "eligibility_criteria": eligibility,
                "funding_details": funding,
                "device_type": "subvention",
                "aid_nature": "grant",
                "country": "Afrique",
                "region": "Afrique",
                "zone": "Afrique",
                "geographic_scope": "regional",
                "beneficiaries": ["femmes", "pme", "cooperatives", "associations"],
                "sectors": ["agriculture", "climat", "numerique", "artisanat"],
                "source_url": "https://www.aecfafrica.org/approach/our-programmes/crosscutting-themes/investing-in-women-in-benin-and-burkina-faso/",
                "keywords": extract_keywords(normalized_title + " aecf women benin burkina faso grant"),
            }

        return {}

    def _build_private_investor_fields(
        self,
        normalized_title: str,
        raw_body: str,
        metadata: dict,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            body = self._get_profile_text(
                metadata,
                tuple(
                    dict.fromkeys(
                        tuple(getattr(self.profile, "short_description_fields", ()))
                        + tuple(getattr(self.profile, "full_description_fields", ()))
                    )
                ),
            ) or ""
        if not body:
            return {}

        localized = localize_investment_text(f"{normalized_title}\n{body}")
        presentation = localized
        if localized.startswith("## "):
            presentation = localized.split("\n", 1)[1] if "\n" in localized else localized

        funding = self._get_profile_text(metadata, getattr(self.profile, "funding_fields", ()))
        if not funding:
            funding = (
                "Le ticket, les conditions d'investissement et les modalites de prise de contact "
                "doivent etre confirmes directement sur la source officielle."
            )

        procedure = (
            "La prise de contact et l'etude du dossier se font directement aupres de l'equipe "
            "d'investissement via le site officiel du fonds."
        )
        full_description = build_structured_sections(
            presentation=presentation,
            funding=funding,
            open_date=open_date,
            close_date=close_date,
            procedure=procedure,
            recurrence_notes=(
                "Ce fonds fonctionne comme un dispositif permanent ou recurrent, sans fenetre de cloture unique."
                if not close_date
                else None
            ),
        )

        return {
            "short_description": sanitize_text(presentation)[:500],
            "full_description": full_description,
            "funding_details": sanitize_text(funding),
            "device_type": "investissement",
            "aid_nature": "capital",
            "geographic_scope": "international",
            "keywords": extract_keywords(normalized_title),
        }

    def _build_global_south_opportunities_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        body = clean_editorial_text(raw_body)
        if not body:
            return {}

        sections = self._extract_global_south_sections(raw_body)
        presentation_source = sections.get("presentation") or body
        eligibility_source = sections.get("eligibility")
        funding_source = sections.get("funding")
        procedure_source = sections.get("procedure")

        opportunity_type = self._detect_device_type((normalized_title + " " + body).lower())
        country = self._detect_country((normalized_title + " " + body).lower()) or "International"
        amount_label = self._extract_amount_label(body)

        close_sentence = (
            f"La date limite reperee est le {close_date.strftime('%d/%m/%Y')}."
            if close_date
            else "La date limite doit etre confirmee sur la page officielle."
        )
        amount_sentence = (
            f"Le texte source mentionne un financement ou avantage pouvant atteindre {amount_label}."
            if amount_label
            else "Le montant ou l'avantage exact doit etre confirme sur la source officielle."
        )

        short_description = (
            f"Opportunite de financement relayee par Global South Opportunities. "
            f"Elle concerne principalement {country}. {close_sentence}"
        )

        presentation = self._summarize_english_section_for_gso(
            presentation_source,
            fallback=(
                f"Global South Opportunities relaie cette opportunite sous le titre "
                f"\"{normalized_title}\". La fiche doit etre verifiee sur la source officielle "
                "avant toute candidature."
            ),
        )
        eligibility = self._summarize_english_section_for_gso(
            eligibility_source,
            fallback=(
                "Les beneficiaires eligibles et les conditions d'acces doivent etre confirmes "
                "dans l'article detaille et sur le site officiel du programme."
            ),
        )
        funding = self._summarize_english_section_for_gso(
            funding_source,
            fallback=amount_sentence,
        )
        procedure = self._summarize_english_section_for_gso(
            procedure_source,
            fallback=(
                "La demarche de candidature est decrite dans l'article source. "
                "Le depot doit etre effectue via le lien officiel indique par Global South Opportunities."
            ),
        )

        full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            open_date=open_date,
            close_date=close_date,
            procedure=procedure,
        )

        return {
            "short_description": short_description,
            "full_description": full_description,
            "eligibility_criteria": eligibility,
            "funding_details": funding,
            "device_type": opportunity_type,
            "aid_nature": "subvention" if opportunity_type in {"subvention", "concours", "aap"} else "a_confirmer",
            "country": country,
            "geographic_scope": "international" if country == "International" else "national",
            "keywords": extract_keywords(normalized_title),
        }

    def _extract_global_south_sections(self, raw_body: str) -> dict[str, str]:
        soup = BeautifulSoup(raw_body or "", "lxml")
        buckets: dict[str, list[str]] = {
            "presentation": [],
            "eligibility": [],
            "funding": [],
            "procedure": [],
        }
        current = "presentation"
        skip_markers = (
            "for more opportunities",
            "follow us on",
            "disclaimer",
            "final thoughts",
            "final overview",
        )

        for node in soup.find_all(["h2", "h3", "h4", "p", "li"]):
            text = clean_editorial_text(node.get_text(" ", strip=True))
            if not text:
                continue
            normalized = unidecode(text.lower())
            if any(marker in normalized for marker in skip_markers):
                continue
            if node.name in {"h2", "h3", "h4"}:
                if any(marker in normalized for marker in ("eligible", "eligibility", "who should apply", "who can apply", "requirements")):
                    current = "eligibility"
                elif any(marker in normalized for marker in ("funding", "grant cover", "benefit", "award", "prize", "amount", "support")):
                    current = "funding"
                elif any(marker in normalized for marker in ("how to apply", "application process", "submission", "deadline", "timeline", "dates")):
                    current = "procedure"
                continue
            if len(text) < 20:
                continue
            buckets[current].append(text)

        return {
            key: " ".join(values[:8])[:1800]
            for key, values in buckets.items()
            if values
        }

    def _summarize_english_section_for_gso(self, text: Optional[str], fallback: str) -> str:
        cleaned = clean_editorial_text(text or "")
        if not cleaned:
            return fallback

        normalized = unidecode(cleaned.lower())
        parts = []
        if "open to" in normalized or "eligible" in normalized or "applicants" in normalized:
            parts.append("La source precise les profils de candidats eligibles et les conditions de participation.")
        if "grant" in normalized or "funding" in normalized or "support" in normalized or "award" in normalized:
            parts.append("Le dispositif apporte un financement, une recompense ou un appui operationnel selon les modalites du programme.")
        if "deadline" in normalized or "apply" in normalized or "submission" in normalized:
            parts.append("La candidature doit etre deposee selon le calendrier et les consignes indiquees par l'organisme officiel.")
        if "climate" in normalized:
            parts.append("La thematique climat ou transition environnementale est mentionnee dans la source.")
        if "agricultur" in normalized or "food" in normalized:
            parts.append("La source mentionne des projets lies a l'agriculture, aux systemes alimentaires ou au developpement rural.")
        if "research" in normalized or "scient" in normalized:
            parts.append("La source cible notamment des projets de recherche, d'innovation ou de production de connaissances.")
        if "entrepreneur" in normalized or "startup" in normalized:
            parts.append("La source vise des entrepreneurs, startups ou structures porteuses de solutions innovantes.")

        if not parts:
            parts.append(fallback)
        parts.append("Les informations detaillees doivent etre confirmees sur le site officiel avant candidature.")
        return " ".join(dict.fromkeys(parts))

    def _extract_amount_label(self, text: str) -> Optional[str]:
        cleaned = sanitize_text(text or "")
        match = re.search(
            r"(?:up to|jusqu(?:'|’)a|jusqu(?:'|’)à)\s*(?:cad\s*)?([$€£]?\s?\d[\d\s,.]*(?:\s?(?:usd|eur|cad|gbp|€|\$|£))?)",
            cleaned,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"([$€£]\s?\d[\d\s,.]*|\d[\d\s,.]*\s?(?:usd|eur|cad|gbp|€|\$|£))",
                cleaned,
                re.IGNORECASE,
            )
        return clean_editorial_text(match.group(1)) if match else None

    def _build_short_description(self, item: RawItem, raw_body: str, metadata: dict, close_date: Optional[date]) -> Optional[str]:
        profile_short = self._get_profile_text(metadata, getattr(self.profile, "short_description_fields", ()))
        if profile_short and not self._should_replace_english_body_with_metadata(profile_short, metadata):
            return sanitize_text(profile_short)[:500]

        cleaned = sanitize_text(raw_body or "")
        if cleaned and len(cleaned) >= 80 and not self._should_replace_english_body_with_metadata(cleaned, metadata):
            return cleaned[:500]

        metadata_summary = self._compose_metadata_summary(item, metadata, close_date)
        return metadata_summary[:500] if metadata_summary else (cleaned[:500] if cleaned else None)

    @staticmethod
    def _format_iso_date(raw_value) -> Optional[str]:
        if not raw_value:
            return None
        value = str(raw_value)[:10]
        try:
            parsed = date.fromisoformat(value)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            return value

    @staticmethod
    def _clean_title_for_summary(title: str) -> str:
        cleaned = sanitize_text(title or "")
        if cleaned.upper() == cleaned and len(cleaned) <= 24:
            return cleaned.title()
        return cleaned

    def _metadata_value_to_text(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in ("text", "texte", "label", "title", "name", "value", "cdata", "Name"):
                nested = value.get(key)
                if nested:
                    return self._metadata_value_to_text(nested)
            parts = [self._metadata_value_to_text(item) for item in value.values()]
            return " ".join(part for part in parts if part).strip()
        if isinstance(value, list):
            parts = [self._metadata_value_to_text(item) for item in value]
            return " ".join(part for part in parts if part).strip()
        return sanitize_text(str(value))

    def _is_unusable_content(self, raw_body: str, metadata: dict) -> bool:
        value = " ".join(
            part
            for part in (
                raw_body or "",
                " ".join(str(v) for v in metadata.values()) if metadata else "",
            )
            if part
        )
        normalized = unidecode(sanitize_text(value).lower())
        return any(marker in normalized for marker in UNUSABLE_CONTENT_MARKERS)

    def _get_profile_text(self, metadata: dict, field_names: tuple[str, ...]) -> Optional[str]:
        if not metadata or not field_names:
            return None

        parts = []
        seen = set()
        for field_name in field_names:
            value = self._get_nested_metadata_value(metadata, field_name)
            text = self._metadata_value_to_text(value)
            if not text:
                continue
            normalized = unidecode(text.lower())
            if normalized in seen:
                continue
            seen.add(normalized)
            parts.append(text)

        if not parts:
            return None
        return "\n\n".join(parts)

    def _extract_profile_sections_from_text(self, raw_body: str) -> Dict[str, str]:
        text = clean_editorial_text(raw_body or "")
        if len(text) < 80:
            return {}

        buckets: dict[str, list[str]] = {
            "presentation": [],
            "details": [],
            "eligibility": [],
            "funding": [],
            "procedure": [],
        }
        current = "details"
        heading_markers = {
            "eligibility": (
                "eligib", "beneficiaire", "beneficiaires", "conditions", "criteres",
                "qui peut", "public vise", "candidats", "requirements",
            ),
            "funding": (
                "montant", "financement", "dotation", "recompense", "prix", "subvention",
                "pret", "avantage", "aide", "budget", "award", "funding", "prize",
            ),
            "procedure": (
                "demarche", "candidature", "postuler", "depot", "calendrier", "deadline",
                "date limite", "selection", "how to apply", "application",
            ),
            "presentation": ("presentation", "objectif", "description", "programme", "a propos"),
        }

        lines = [line.strip(" -\t") for line in re.split(r"[\n\r]+", text) if line.strip()]
        if len(lines) <= 1:
            lines = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) > 35]

        for line in lines:
            clean = sanitize_text(line)
            if len(clean) < 20:
                continue
            normalized = unidecode(clean.lower())
            is_heading = len(clean) <= 95 and not clean.endswith(".")
            if is_heading:
                matched_heading = None
                for bucket, markers in heading_markers.items():
                    if any(marker in normalized for marker in markers):
                        matched_heading = bucket
                        break
                if matched_heading:
                    current = matched_heading
                    continue

            target = current
            if current in {"details", "presentation"}:
                for bucket in ("eligibility", "funding", "procedure"):
                    if any(marker in normalized for marker in heading_markers[bucket]):
                        target = bucket
                        break
            buckets[target].append(clean)

        if not buckets["presentation"] and buckets["details"]:
            buckets["presentation"] = buckets["details"][:3]
            buckets["details"] = buckets["details"][3:]

        return {
            key: "\n".join(dict.fromkeys(parts[:10])).strip()
            for key, parts in buckets.items()
            if parts
        }

    def _build_profile_sections(
        self,
        metadata: dict,
        close_date: Optional[date],
        open_date: Optional[date],
        raw_body: str = "",
    ) -> Dict[str, Any]:
        if not self.profile or self.profile.key not in {
            "les_aides",
            "data_aides_entreprises",
            "banque_des_territoires",
            "ademe",
            "prix_pierre_castel",
            "global_south_opportunities",
        }:
            return {}

        presentation = self._get_profile_text(metadata, self.profile.short_description_fields)
        details = self._get_profile_text(metadata, self.profile.full_description_fields)
        eligibility = self._get_profile_text(metadata, self.profile.eligibility_fields)
        funding = self._get_profile_text(metadata, self.profile.funding_fields)
        procedure = self._get_profile_text(metadata, self.profile.procedure_fields)
        text_sections = self._extract_profile_sections_from_text(raw_body)
        presentation = presentation or text_sections.get("presentation")
        details = details or text_sections.get("details")
        eligibility = eligibility or text_sections.get("eligibility")
        funding = funding or text_sections.get("funding")
        procedure = procedure or text_sections.get("procedure")

        if not any([presentation, details, eligibility, funding, procedure]):
            return {}

        details_clean = sanitize_text(details or "")
        presentation_clean = sanitize_text(presentation or "")
        if details_clean and unidecode(details_clean.lower()) == unidecode(presentation_clean.lower()):
            details_clean = ""

        if self.profile.key == "les_aides":
            base_text = details_clean or presentation_clean
            eligibility = eligibility or build_contextual_eligibility(
                text=base_text,
                beneficiaries=self._detect_beneficiaries(sanitize_text(base_text).lower()),
                country=self._canonicalize_country_name(
                    self._get_nested_metadata_value(metadata, "country") or self.default_country
                ),
                geographic_scope=sanitize_text(self._get_nested_metadata_value(metadata, "geographic_scope") or ""),
            )
            funding = funding or build_contextual_funding(
                text=base_text,
                device_type=sanitize_text(self._get_nested_metadata_value(metadata, "device_type") or ""),
            )

        payload: Dict[str, Any] = {
            "short_description": sanitize_text(presentation or details or "")[:500] or None,
            "full_description": build_structured_sections(
                presentation=details_clean or presentation_clean,
                eligibility=eligibility,
                funding=funding,
                open_date=open_date,
                close_date=close_date,
                procedure=procedure or self._build_procedure_text(sanitize_text(presentation or details or "")),
            ),
            "eligibility_criteria": sanitize_text(eligibility) if eligibility else None,
            "funding_details": sanitize_text(funding) if funding else None,
            "procedure": sanitize_text(procedure) if procedure else None,
        }

        country = self._get_profile_text(metadata, getattr(self.profile, "country_fields", ()))
        if country:
            payload["country"] = self._canonicalize_country_name(country)
        return {key: value for key, value in payload.items() if value}

    def _build_full_description(
        self,
        item: RawItem,
        raw_body: str,
        metadata: dict,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Optional[str]:
        profile_full = self._build_profile_sections(metadata, close_date, open_date, raw_body=raw_body).get("full_description")
        if profile_full:
            return profile_full[:4000]

        cleaned = sanitize_text(raw_body or "")
        if cleaned and len(cleaned) >= 220 and not self._should_replace_english_body_with_metadata(cleaned, metadata):
            return cleaned[:4000]

        sections = []
        metadata_summary = self._compose_metadata_summary(item, metadata, close_date)
        if metadata_summary:
            sections.append(f"## Présentation\n{metadata_summary}")

        sector_lines = []
        for field_name in ("sector1.Name", "sector2.Name", "sector3.Name"):
            sector_name = self._get_nested_metadata_value(metadata, field_name)
            if sector_name:
                sector_lines.append(str(sector_name).strip())
        if sector_lines:
            sections.append("## Secteurs\n" + "\n".join(f"- {line}" for line in sector_lines))

        financing_lines = []
        total_commitment = self._get_nested_metadata_value(metadata, "totalcommamt")
        if total_commitment:
            financing_lines.append(f"- Engagement total : {total_commitment}")
        if close_date:
            financing_lines.append(f"- Date de clôture : {close_date.strftime('%d/%m/%Y')}")
        if open_date:
            financing_lines.append(f"- Date d'ouverture : {open_date.strftime('%d/%m/%Y')}")
        board_approval = self._get_nested_metadata_value(metadata, "boardapprovaldate")
        if board_approval:
            formatted_approval = self._format_iso_date(board_approval)
            if formatted_approval:
                financing_lines.append(f"- Date d'approbation : {formatted_approval}")
        if financing_lines:
            sections.append("## Informations clés\n" + "\n".join(financing_lines))

        if not self._get_nested_metadata_value(metadata, "project_abstract"):
            sections.append(
                "## Conditions d'attribution\n"
                "Les critères détaillés ne sont pas fournis dans le flux structuré disponible. "
                "La page officielle du projet doit être consultée pour vérifier les bénéficiaires, "
                "les conditions d'accès et les modalités opérationnelles."
            )

        result = sanitize_text("\n\n".join(section for section in sections if section))
        return result[:4000] if result else None

    def _build_procedure_text(self, context_title: str) -> str:
        source_url = (self.source.get("url") or "").lower()
        organism = sanitize_text(self.organism or "").strip()

        if "les-aides.fr" in source_url or "aides-entreprises" in source_url:
            return "La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle."
        if "worldbank" in source_url:
            return (
                "La consultation detaillee se fait sur la page officielle du projet. "
                "Les modalites d'acces et d'instruction doivent etre confirmees aupres de l'institution porteuse."
            )
        if organism:
            return f"La consultation detaillee se fait aupres de {organism} via la source officielle."
        if context_title:
            return "La consultation detaillee et la demarche associee doivent etre confirmees sur la source officielle."
        return "La consultation detaillee se fait depuis la source officielle."

    def _finalize_structured_full_description(
        self,
        *,
        item: RawItem,
        metadata: dict,
        normalized_title: str,
        full_description: Optional[str],
        short_description: Optional[str],
        eligibility_criteria: Optional[str],
        funding_details: Optional[str],
        open_date: Optional[date],
        close_date: Optional[date],
        recurrence_notes: Optional[str],
    ) -> Optional[str]:
        current = full_description or ""
        if current.startswith("## ") and "## Calendrier" in current:
            return current

        metadata_summary = self._compose_metadata_summary(item, metadata, close_date)
        presentation = metadata_summary or full_description or short_description
        funding = funding_details
        if not funding:
            funding_bits = []
            total_commitment = self._get_nested_metadata_value(metadata, "totalcommamt")
            if total_commitment:
                funding_bits.append(f"Engagement total annonce : {total_commitment}.")
            board_approval = self._get_nested_metadata_value(metadata, "boardapprovaldate")
            if board_approval:
                formatted_approval = self._format_iso_date(board_approval)
                if formatted_approval:
                    funding_bits.append(f"Date d'approbation indiquee : {formatted_approval}.")
            funding = " ".join(funding_bits) if funding_bits else None

        return build_structured_sections(
            presentation=presentation,
            eligibility=eligibility_criteria,
            funding=funding,
            open_date=open_date,
            close_date=close_date,
            procedure=self._build_procedure_text(normalized_title),
            recurrence_notes=recurrence_notes,
        ) or full_description

    def _compose_metadata_summary(self, item: RawItem, metadata: dict, close_date: Optional[date]) -> Optional[str]:
        project_abstract = self._get_nested_metadata_value(metadata, "project_abstract")
        if project_abstract and not looks_english_text(str(project_abstract)):
            return sanitize_text(str(project_abstract))

        country = self._canonicalize_country_name(
            self._get_nested_metadata_value(metadata, "countryshortname") or self.default_country
        )
        sector_1 = self._get_nested_metadata_value(metadata, "sector1.Name")
        sector_2 = self._get_nested_metadata_value(metadata, "sector2.Name")
        total_commitment = self._get_nested_metadata_value(metadata, "totalcommamt")
        board_approval = self._format_iso_date(self._get_nested_metadata_value(metadata, "boardapprovaldate"))
        nice_title = self._clean_title_for_summary(item.title)

        parts = []
        if not self._is_world_bank_source():
            parts.append(nice_title)
        if country:
            parts.append(f"Ce projet est porté au {country}.")
        sectors = [self._localize_sector_label(str(value).strip()) for value in (sector_1, sector_2) if value]
        if sectors:
            parts.append("Il concerne principalement les secteurs suivants : " + ", ".join(sectors) + ".")
        if total_commitment:
            parts.append(f"L'engagement total annoncé atteint {total_commitment}.")
        if board_approval:
            parts.append(f"La date d'approbation indiquée est le {board_approval}.")
        if close_date:
            parts.append(f"La clôture prévisionnelle est fixée au {close_date.strftime('%d/%m/%Y')}.")

        summary = " ".join(part for part in parts if part).strip()
        return summary or None

    def _should_replace_english_body_with_metadata(self, cleaned_text: str, metadata: dict) -> bool:
        if not cleaned_text or not metadata:
            return False
        if self._is_world_bank_source() and looks_english_text(cleaned_text):
            return True
        return False

    def _localize_sector_label(self, value: str) -> str:
        normalized = unidecode((value or "").lower()).strip()
        if not normalized:
            return value
        canonical = normalized.replace("&", "and")
        exact = {
            "agricultural extension, research, and other support activities": "appui agricole, recherche et services connexes",
            "public administration - agriculture, fishing & forestry": "administration publique agricole, pêche et forêt",
            "public administration - energy and extractives": "administration publique de l'énergie et des industries extractives",
            "public administration - industry, trade and services": "administration publique de l'industrie, du commerce et des services",
            "public administration - health": "administration publique de la santé",
            "public administration - transportation": "administration publique des transports",
            "public administration - water, sanitation and waste management": "administration publique de l'eau, de l'assainissement et des déchets",
            "health facilities and construction": "infrastructures et équipements de santé",
            "social protection": "protection sociale",
            "renewable energy solar": "énergie solaire renouvelable",
            "energy transmission and distribution": "transport et distribution d'énergie",
            "energie transmission and distribution": "transport et distribution d'énergie",
            "oil and gas": "pétrole et gaz",
            "rural and inter-urban roads": "routes rurales et interurbaines",
            "ict services": "services numériques",
            "workforce development and vocational education": "développement des compétences et formation professionnelle",
            "financial sector": "secteur financier",
            "fishing and forestry": "pêche et forêt",
            "agricultural markets, commercialization and agri-business": "marchés agricoles, commercialisation et agro-industrie",
            "other water supply, sanitation and waste management": "eau, assainissement et gestion des déchets",
            "other non-bank financial institutions": "institutions financières non bancaires",
            "other agriculture": "autres activités agricoles",
            "other energy and extractives": "autres activités énergie et industries extractives",
            "other industry, trade and services": "industrie, commerce et services",
            "central government": "administration centrale",
            "sub-national government": "administrations territoriales",
            "water supply": "approvisionnement en eau",
            "sanitation": "assainissement",
            "health": "santé",
            "education": "éducation",
            "energy": "énergie",
            "transportation": "transports",
        }
        if canonical in exact:
            return exact[canonical]
        replacements = (
            ("public administration", "administration publique"),
            ("other administration publique", "autres administrations publiques"),
            ("administration publique - water", "administration publique de l'eau"),
            ("administration publique - industry", "administration publique de l'industrie"),
            ("administration publique - education", "administration publique de l'éducation"),
            ("administration publique - éducation", "administration publique de l'éducation"),
            ("energie transmission and distribution", "transport et distribution d'énergie"),
            ("energy transmission and distribution", "transport et distribution d'énergie"),
            ("renewable energy", "énergies renouvelables"),
            ("oil and gas", "pétrole et gaz"),
            ("energy and extractives", "énergie et industries extractives"),
            ("other industry, trade and services", "industrie, commerce et services"),
            ("industry, trade and services", "industrie, commerce et services"),
            ("financial sector", "secteur financier"),
            ("workforce development and vocational education", "développement des compétences et formation professionnelle"),
            ("other public administration", "autres administrations publiques"),
            ("public administration - education", "administration publique de l'éducation"),
            ("fishing and forestry", "pêche et forêt"),
            ("other agriculture", "autres activités agricoles"),
            ("agricultural markets, commercialization and agri-business", "marchés agricoles, commercialisation et agro-industrie"),
            ("other water supply, sanitation and waste management", "eau, assainissement et gestion des déchets"),
            ("water supply, sanitation and waste management", "eau, assainissement et gestion des déchets"),
            ("other non-bank financial institutions", "institutions financières non bancaires"),
            ("sub-national government", "administrations territoriales"),
            ("central government", "administration centrale"),
            ("central agencies", "agences centrales"),
            ("health facilities", "infrastructures de santé"),
            ("water, sanitation and waste management", "eau, assainissement et gestion des déchets"),
            ("rural and inter-urban roads", "routes rurales et interurbaines"),
            ("agricultural extension", "conseil agricole"),
            ("irrigation and drainage", "irrigation et drainage"),
            ("capital markets", "marchés de capitaux"),
            ("micro- and sme finance", "microfinance et financement des PME"),
            ("ict infrastructure", "infrastructures numériques"),
            ("information and communications technologies", "technologies de l'information et de la communication"),
            ("information and communications technology", "technologies de l'information et de la communication"),
            ("ports/waterways", "ports et voies navigables"),
            ("urban transport", "transport urbain"),
            ("primary education", "enseignement primaire"),
            ("secondary education", "enseignement secondaire"),
            ("tertiary education", "enseignement supérieur"),
            ("research", "recherche"),
            ("support activities", "activités d'appui"),
            ("social protection", "protection sociale"),
            ("ict services", "services numériques"),
            ("transportation", "transports"),
            ("forestry", "forêt"),
            ("crops", "cultures agricoles"),
            ("agriculture", "agriculture"),
            ("health", "santé"),
            ("education", "éducation"),
            ("energy", "énergie"),
        )
        localized = canonical
        for source, target in replacements:
            localized = re.sub(source, target, localized, flags=re.IGNORECASE)
        if localized != canonical:
            return sanitize_text(localized)
        return sanitize_text(value)

    def _is_world_bank_source(self) -> bool:
        source_url = (self.source.get("url") or "").lower()
        organism = (self.source.get("organism") or "").lower()
        return "worldbank" in source_url or "world bank" in organism

    def _canonicalize_country_name(self, raw_value) -> Optional[str]:
        if not raw_value:
            return None
        value = sanitize_text(str(raw_value)).strip()
        normalized = unidecode(value.replace("’", "'").lower())
        return COUNTRY_MAP.get(normalized, value)

    def _build_source_raw(self, item: RawItem) -> Optional[str]:
        metadata_blob = ""
        if item.metadata:
            try:
                metadata_blob = json.dumps(item.metadata, ensure_ascii=False, default=str)
            except TypeError:
                metadata_blob = str(item.metadata)

        raw_blob = (item.raw_content or "").strip()
        parts = []
        if raw_blob:
            parts.append(raw_blob[:6000])
        if metadata_blob:
            parts.append(metadata_blob[:12000])

        combined = "\n\n".join(part for part in parts if part).strip()
        return combined[:18000] if combined else None

    def _detect_country(self, text: str) -> Optional[str]:
        normalized_text = unidecode(text.replace("’", "'").lower())
        for marker in ("pays et region", "pays et région", "pays "):
            if marker in normalized_text:
                start = normalized_text.index(marker) + len(marker)
                focus = normalized_text[start:start + 120]
                for alias, canonical in COUNTRY_MAP.items():
                    normalized_alias = unidecode(alias.replace("’", "'").lower())
                    if normalized_alias in focus:
                        return canonical
        for alias, canonical in COUNTRY_MAP.items():
            normalized_alias = unidecode(alias.replace("’", "'").lower())
            if normalized_alias in normalized_text:
                return canonical
        return None

    def _detect_device_type(self, text: str) -> str:
        if self._is_world_bank_source():
            if any(keyword in text for keyword in ["grant", "subvention"]):
                return "subvention"
            return "autre"
        for dtype, keywords in DEVICE_TYPE_RULES.items():
            if any(keyword in text for keyword in keywords):
                return dtype
        return "autre"

    def _detect_sectors(self, text: str) -> list:
        return [sector for sector, keywords in SECTOR_RULES.items() if any(keyword in text for keyword in keywords)]

    def _detect_beneficiaries(self, text: str) -> list:
        return [beneficiary for beneficiary, keywords in BENEFICIARY_RULES.items() if any(keyword in text for keyword in keywords)]

    def _detect_currency(self, text: str) -> str:
        if any(currency in text for currency in ["xof", "fcfa", "franc cfa"]):
            return "XOF"
        if any(currency in text for currency in ["mad", "dirham"]):
            return "MAD"
        if any(currency in text for currency in ["tnd", "dinar"]):
            return "TND"
        if "xaf" in text:
            return "XAF"
        return "EUR"

    def _detect_status(self, text: str) -> str:
        if any(keyword in text for keyword in ["clôturé", "terminé", "expiré", "closed", "archivé"]):
            return "closed"
        if has_recurrence_evidence(text) or any(
            keyword in text
            for keyword in ["récurrent", "permanent", "ouvert en continu", "ouverte en continu"]
        ):
            return "recurring"
        if "en cours" in text:
            return "open"
        return "open"

    def _extract_metadata_status(self, item: RawItem) -> Optional[str]:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        if not metadata:
            return None

        configured_fields = self.config.get("status_fields") or []
        configured_field = self.config.get("status_field")
        if configured_field:
            configured_fields = [configured_field, *configured_fields]

        field_names = configured_fields + ["status", "projectstatus", "state", "etat"]
        seen = set()
        for field_name in field_names:
            if not field_name or field_name in seen:
                continue
            seen.add(field_name)
            raw_value = self._get_nested_metadata_value(metadata, field_name)
            normalized = self._normalize_metadata_status(raw_value)
            if normalized:
                return normalized
        return None

    def _normalize_metadata_status(self, raw_value) -> Optional[str]:
        if raw_value is None:
            return None
        value = str(raw_value).strip().lower()
        if not value:
            return None
        if value in {"closed", "cloture", "clôturé", "closedout", "inactive", "archived"}:
            return "closed"
        if value in {"expired", "expire", "expiré"}:
            return "expired"
        if value in {"recurring", "ongoing", "continuous"}:
            return "recurring"
        if value in {"open", "active", "1", "published"}:
            return "open"
        return None

    def _extract_metadata_date(self, item: RawItem, mode: str) -> Optional[date]:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        if not metadata:
            return None

        configured_fields = self.config.get(f"{mode}_date_fields") or []
        configured_field = self.config.get(f"{mode}_date_field")
        if configured_field:
            configured_fields = [configured_field, *configured_fields]

        field_names = configured_fields + (CLOSE_DATE_FIELDS if mode == "close" else OPEN_DATE_FIELDS)
        seen = set()
        for field_name in field_names:
            if not field_name or field_name in seen:
                continue
            seen.add(field_name)
            raw_value = self._get_nested_metadata_value(metadata, field_name)
            parsed = self._parse_metadata_date(raw_value)
            if parsed:
                return parsed
        return None

    def _get_nested_metadata_value(self, metadata: dict, field_path: str):
        value = metadata
        for key in str(field_path).split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _parse_metadata_date(self, raw_value) -> Optional[date]:
        if raw_value is None:
            return None
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, list):
            for item in raw_value:
                parsed = self._parse_metadata_date(item)
                if parsed:
                    return parsed
            return None
        if isinstance(raw_value, dict):
            for item in raw_value.values():
                parsed = self._parse_metadata_date(item)
                if parsed:
                    return parsed
            return None

        value = str(raw_value).strip()
        if not value or value in {"0000-00-00", "0000-00-00 00:00:00"}:
            return None

        parsed = dateparser.parse(
            value,
            languages=["fr", "en"],
            settings={"PREFER_DAY_OF_MONTH": "last", "RETURN_AS_TIMEZONE_AWARE": False},
        )
        return parsed.date() if parsed else None

    def _extract_date(self, text: str, mode: str) -> Optional[Any]:
        if mode == "close":
            patterns = [
                r"clôture[:\s]+(.{5,40}?)(?:\n|\.)",
                r"date de fermeture\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4})",
                r"date de fermeture[:\s]+(.{5,40}?)(?:\n|\.)",
                r"date limite[:\s]+(.{5,30})",
                r"deadline[:\s]+(.{5,30})",
                r"(?:submission|application|final)?\s*deadline\s+(?:is|set for|falls on|closes on)\s+(.{5,35})",
                r"apply\s+(?:by|before)\s+(.{5,30})",
                r"applications?\s+(?:close|closes|end|ends)\s+(?:on\s+)?(.{5,30})",
                r"jusqu'au\s+(.{5,25})",
                r"au\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
                r"au\s+(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4})",
                r"avant le\s+(.{5,25})",
                r"au plus tard le\s+(.{5,25})",
            ]
        else:
            patterns = [
                r"ouverture[:\s]+(.{5,30})",
                r"lancement[:\s]+(.{5,30})",
                r"à partir du\s+(.{5,25})",
                r"dès le\s+(.{5,25})",
                r"du\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            candidate = re.sub(
                r"^(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+",
                "",
                match.group(1).strip(),
                flags=re.IGNORECASE,
            )
            year_match = re.search(r"(.{0,45}?\d{4})", candidate)
            if year_match:
                candidate = year_match.group(1)
            parsed = dateparser.parse(
                candidate,
                languages=["fr", "en"],
                settings={"PREFER_DAY_OF_MONTH": "last", "RETURN_AS_TIMEZONE_AWARE": False},
            )
            if parsed:
                return parsed.date()
        return None

    def _extract_amount(self, text: str, mode: str) -> Optional[float]:
        if mode == "max":
            patterns = [
                r"jusqu'[àa]\s+([\d\s,.]+)\s*(?:€|eur|k€|m€|millions?|milliards?|xof|mad|tnd)",
                r"maximum[:\s]+([\d\s,.]+)\s*(?:€|eur|k€|m€)",
                r"([\d\s,.]+)\s*(?:€|eur)\s*(?:maximum|max\.?)",
                r"plafond[:\s]+([\d\s,.]+)\s*(?:€|eur|k€)",
            ]
        else:
            patterns = [
                r"[àa] partir de\s+([\d\s,.]+)\s*(?:€|eur|k€)",
                r"minimum[:\s]+([\d\s,.]+)\s*(?:€|eur|k€)",
                r"([\d\s,.]+)\s*(?:€|eur)\s*minimum",
                r"plancher[:\s]+([\d\s,.]+)\s*(?:€|eur|k€)",
            ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = self._parse_amount(match.group(1))
            if value and value > 0:
                return value
        return None

    @staticmethod
    def _parse_amount(value: str) -> Optional[float]:
        try:
            clean = re.sub(r"\s", "", value).replace(",", ".")
            multiplier = 1
            if clean.lower().endswith(("k", "k€")):
                multiplier = 1_000
                clean = re.sub(r"k.*", "", clean, flags=re.IGNORECASE)
            elif clean.lower().endswith(("m", "m€", "million", "millions")):
                multiplier = 1_000_000
                clean = re.sub(r"m.*", "", clean, flags=re.IGNORECASE)
            elif clean.lower().endswith(("milliard", "milliards")):
                multiplier = 1_000_000_000
                clean = re.sub(r"milliard.*", "", clean, flags=re.IGNORECASE)
            return float(clean) * multiplier
        except (ValueError, AttributeError):
            return None
