import json
import logging
import re
from datetime import date
from typing import Any, Dict, Optional

import dateparser
from unidecode import unidecode

from app.collector.base_connector import RawItem
from app.utils.text_utils import (
    clean_editorial_text,
    dedupe_text_fields,
    derive_device_status,
    extract_keywords,
    looks_english_text,
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


class Normalizer:
    def __init__(self, source: dict):
        self.source = source
        self.default_country = source.get("country", "")
        self.organism = source.get("organism", "")
        self.config = source.get("config") or {}

    def normalize(self, item: RawItem) -> Optional[Dict[str, Any]]:
        raw_body = clean_editorial_text(item.raw_content or "")
        if looks_english_text(raw_body) and not self.config.get("allow_english_text"):
            logger.info(f"[Normalizer] Item ignoré car description anglaise: {item.title[:120]}")
            return None

        normalized_title = self._normalize_title_for_source(item.title, raw_body)
        text = sanitize_text(f"{normalized_title} {raw_body}").lower()
        close_date = self._extract_metadata_date(item, "close") or self._extract_date(text, "close")
        open_date = self._extract_metadata_date(item, "open") or self._extract_date(text, "open")
        initial_status = self._extract_metadata_status(item) or self._detect_status(text)
        is_recurring = False
        recurrence_notes = None
        if (
            self.config.get("assume_recurring_without_close_date")
            and not close_date
            and initial_status == "open"
        ):
            initial_status = "recurring"
            is_recurring = True
            recurrence_notes = (
                "Classe automatiquement comme dispositif recurrent: "
                "la source n'expose pas de date de cloture fiable."
            )
        elif (
            self.config.get("assume_standby_without_close_date")
            and not close_date
            and initial_status == "open"
        ):
            initial_status = "standby"
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        short_description = self._build_short_description(item, raw_body, metadata, close_date)
        full_description = self._build_full_description(item, raw_body, metadata, close_date, open_date)
        extra_fields = self._extract_source_specific_fields(normalized_title, raw_body, close_date, open_date)
        short_description = extra_fields.get("short_description") or short_description
        short_description, full_description, funding_details, eligibility_criteria = dedupe_text_fields(
            short_description,
            extra_fields.get("full_description") or full_description,
            extra_fields.get("funding_details"),
            extra_fields.get("eligibility_criteria"),
        )

        payload = {
            "title": normalized_title,
            "organism": self.organism,
            "country": self._detect_country(text) or self.default_country,
            "source_url": item.url,
            "source_raw": self._build_source_raw(item),
            "device_type": self._detect_device_type(text),
            "sectors": self._detect_sectors(text) or ["transversal"],
            "beneficiaries": self._detect_beneficiaries(text),
            "short_description": short_description,
            "full_description": full_description,
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
        }
        if funding_details:
            payload["funding_details"] = funding_details
        for key, value in extra_fields.items():
            if key in {"full_description", "funding_details", "eligibility_criteria"}:
                continue
            payload[key] = value
        return payload

    def _normalize_title_for_source(self, title: str, raw_body: str) -> str:
        cleaned = sanitize_text(title or "")
        source_url = (self.source.get("url") or "").lower()
        body = sanitize_text(raw_body or "").lower()

        if "africabusinessheroes.org" in source_url:
            return "Africa's Business Heroes (ABH) 2026" if "2026" in body else "Africa's Business Heroes (ABH)"

        return cleaned

    def _extract_source_specific_fields(
        self,
        normalized_title: str,
        raw_body: str,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Dict[str, Any]:
        source_url = (self.source.get("url") or "").lower()
        if "africabusinessheroes.org" not in source_url:
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

    def _build_short_description(self, item: RawItem, raw_body: str, metadata: dict, close_date: Optional[date]) -> Optional[str]:
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

    def _build_full_description(
        self,
        item: RawItem,
        raw_body: str,
        metadata: dict,
        close_date: Optional[date],
        open_date: Optional[date],
    ) -> Optional[str]:
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
        sectors = [str(value).strip() for value in (sector_1, sector_2) if value]
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
        if any(keyword in text for keyword in ["récurrent", "permanent", "ouvert en continu"]):
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
