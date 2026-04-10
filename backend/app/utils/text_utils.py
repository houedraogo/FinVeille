import ast
import json
import re
import hashlib
from unidecode import unidecode
from slugify import slugify
from html import unescape
from datetime import date


def normalize_title(title: str) -> str:
    """Minuscules + suppression accents pour comparaisons."""
    return unidecode(title.lower().strip())


def generate_slug(title: str) -> str:
    return slugify(title, max_length=280, separator="-")


def sanitize_text(text: str) -> str:
    """Supprime le HTML et normalise les espaces."""
    if not text:
        return ""
    previous = None
    text = str(text)
    for _ in range(3):
        if text == previous:
            break
        previous = text
        text = extract_cdata_text(text)
    text = unescape(text)
    # Suppression balises HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Décodage entités HTML courantes
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Normalisation espaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_editorial_text(text: str) -> str:
    """Nettoie un texte éditorial aplati sans casser son contenu."""
    if not text:
        return ""

    value = sanitize_text(text)
    value = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?=\d)", " ", value)
    value = re.sub(r"(?<=\d)(?=[A-Za-zÀ-ÿ])", " ", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,.;:!?])(?=[^\s])", r"\1 ", value)
    value = re.sub(r"\(\s+", "(", value)
    value = re.sub(r"\s+\)", ")", value)
    value = re.sub(r"\s{2,}", " ", value).strip()
    return value


def dedupe_text_fields(
    short_description: str | None,
    full_description: str | None,
    funding_details: str | None = None,
    eligibility_criteria: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Supprime les blocs trop proches pour Ã©viter les doublons visibles."""

    def _normalized(value: str | None) -> str:
        return unidecode(clean_editorial_text(value or "").lower())

    short = clean_editorial_text(short_description or "") or None
    full = full_description.strip() if full_description else None
    funding = clean_editorial_text(funding_details or "") or None
    eligibility = clean_editorial_text(eligibility_criteria or "") or None

    normalized_short = _normalized(short)
    normalized_full = _normalized(full)
    normalized_funding = _normalized(funding)
    normalized_eligibility = _normalized(eligibility)

    if short and normalized_full and normalized_short and normalized_short in normalized_full:
        short = short

    if funding and normalized_full and normalized_funding and normalized_funding in normalized_full:
        funding = None

    if (
        eligibility
        and normalized_full
        and normalized_eligibility
        and normalized_eligibility in normalized_full
    ):
        eligibility = None

    if short and funding and normalized_short == normalized_funding:
        funding = None

    if short and eligibility and normalized_short == normalized_eligibility:
        eligibility = None

    return short, full, funding, eligibility


def _extract_cdata_payload(value):
    if isinstance(value, dict):
        for key in ("cdata!", "cdata", "CDATA!", "CDATA"):
            if key in value and value[key]:
                return str(value[key])
        for nested in value.values():
            extracted = _extract_cdata_payload(nested)
            if extracted:
                return extracted
        return None
    if isinstance(value, list):
        for nested in value:
            extracted = _extract_cdata_payload(nested)
            if extracted:
                return extracted
        return None
    if isinstance(value, str):
        return value
    return None


def extract_cdata_text(text: str) -> str:
    """Extrait le texte utile depuis des pseudo-objets de type {'cdata!': '...'}."""
    if not text:
        return ""
    value = str(text).strip()

    if value.startswith("{") or value.startswith("["):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(value)
            except (ValueError, SyntaxError, json.JSONDecodeError, TypeError):
                continue
            extracted = _extract_cdata_payload(parsed)
            if extracted:
                value = extracted.strip()
                break

    wrapped_match = re.search(
        r"^\{?\s*['\"]cdata!?['\"]\s*:\s*(['\"])(.*?)\1\s*\}?$",
        value,
        re.IGNORECASE | re.DOTALL,
    )
    if wrapped_match:
        value = wrapped_match.group(2)
    else:
        cdata_match = re.search(
            r"['\"]cdata!?['\"]\s*[:=]\s*(['\"])(.*?)\1",
            value,
            re.IGNORECASE | re.DOTALL,
        )
        if cdata_match:
            value = cdata_match.group(2)
        elif re.match(r"^\{?\s*['\"]cdata!?['\"]\s*[:=]\s*", value, re.IGNORECASE):
            value = re.sub(
                r"^\{?\s*['\"]cdata!?['\"]\s*[:=]\s*['\"]?",
                "",
                value,
                flags=re.IGNORECASE,
            ).strip()
            value = re.sub(r"['\"}\s]+$", "", value)

    return value.replace("\\n", " ").replace("\\t", " ").replace("\\'", "'").replace('\\"', '"')


def looks_english_text(text: str) -> bool:
    """Heuristique légère pour détecter une description majoritairement anglaise."""
    if not text:
        return False
    sample = f" {unidecode(sanitize_text(text).lower())} "
    markers = [
        " the ", " and ", " for ", " with ", " from ", " project ", " support ",
        " funding ", " development ", " program ", " initiative ", " health ",
        " education ", " climate ", " energy ", " objective ",
    ]
    return sum(1 for marker in markers if marker in sample) >= 2


def localize_investment_text(text: str) -> str:
    """Produit une synthèse française propre pour un texte d'investissement majoritairement anglais."""
    if not text:
        return ""

    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()

    normalized = unidecode(value.lower())

    sector_map = {
        "healthcare": "santé",
        "health": "santé",
        "biotech": "biotechnologies",
        "medtech": "medtech",
        "climate": "climat",
        "energy": "énergie",
        "fintech": "fintech",
        "deep tech": "deep tech",
        "deeptech": "deep tech",
        "software": "logiciel",
        "saas": "SaaS",
        "agriculture": "agriculture",
        "education": "éducation",
        "mobility": "mobilité",
    }
    sectors = [label for marker, label in sector_map.items() if marker in normalized]

    stages = []
    if "pre-seed" in normalized:
        stages.append("pré-amorçage")
    if "seed" in normalized:
        stages.append("amorçage")
    if "series a" in normalized:
        stages.append("série A")
    if "series b" in normalized:
        stages.append("série B")
    if "growth" in normalized or "late-stage" in normalized or "late stage" in normalized:
        stages.append("croissance")

    geographies = []
    for marker, label in (
        ("africa", "Afrique"),
        ("europe", "Europe"),
        ("france", "France"),
        ("international", "international"),
        ("global", "international"),
        ("israel", "Israël"),
        ("united states", "États-Unis"),
    ):
        if marker in normalized and label not in geographies:
            geographies.append(label)

    ticket_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*([mk])?\s*(?:\$|usd|eur|€)\s*(?:to|-|and)\s*(\d+(?:[.,]\d+)?)\s*([mk])?\s*(?:\$|usd|eur|€)",
        normalized,
        re.IGNORECASE,
    )
    if not ticket_match:
        ticket_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*([mk])\s*(?:to|-|and)\s*(\d+(?:[.,]\d+)?)\s*([mk])",
            normalized,
            re.IGNORECASE,
        )
    ticket_sentence = None
    if ticket_match:
        low, low_unit, high, high_unit = ticket_match.groups()
        ticket_sentence = (
            f"Le ticket d'investissement mentionné se situe entre {low}{(low_unit or '').upper()} "
            f"et {high}{(high_unit or '').upper()}."
        )

    support_bits = []
    if "portfolio" in normalized:
        support_bits.append("un accompagnement des participations du portefeuille")
    if "advisor" in normalized or "advisors" in normalized:
        support_bits.append("un appui d'experts et de conseillers")
    if "co-invest" in normalized:
        support_bits.append("des capacités de co-investissement")
    if "research" in normalized:
        support_bits.append("des liens avec des acteurs de la recherche")

    intro = "Ce fonds d'investissement accompagne des entreprises innovantes."
    if sectors:
        intro = f"Ce fonds d'investissement cible principalement les secteurs suivants : {', '.join(dict.fromkeys(sectors))}."

    scope_sentence = None
    if stages or geographies:
        parts = []
        if stages:
            parts.append(f"les stades {', '.join(dict.fromkeys(stages))}")
        if geographies:
            parts.append(f"sur les zones {', '.join(dict.fromkeys(geographies))}")
        scope_sentence = "La stratégie d'investissement couvre " + " et ".join(parts) + "."

    support_sentence = None
    if support_bits:
        support_sentence = "Le dispositif met aussi en avant " + ", ".join(dict.fromkeys(support_bits)) + "."

    summary_parts = [intro]
    if scope_sentence:
        summary_parts.append(scope_sentence)
    if ticket_sentence:
        summary_parts.append(ticket_sentence)
    if support_sentence:
        summary_parts.append(support_sentence)

    result = ("## Présentation\n" + " ".join(summary_parts)).strip()
    return result or "## Présentation\nCe fonds d'investissement propose un accompagnement en capital avec une portée internationale."


def derive_device_status(close_date_value, current_status: str | None = None) -> str:
    """Force expired si la date est passée."""
    if close_date_value and close_date_value < date.today():
        return "expired"
    if current_status:
        return current_status
    return "open"


def extract_close_date(text: str) -> date | None:
    """Extrait une date de clôture probable depuis un texte libre."""
    if not text:
        return None

    sample = sanitize_text(text).lower()
    metadata_patterns = [
        r'"(?:closingdate|closing_date|date_fin|datefin|date_de_fin_du_projet|date_dachevement|date_achevement|end_date|enddate|deadline|deadlinedate|application_deadline)"\s*:\s*"(\d{4})-(\d{2})-(\d{2})',
        r"(?:closingdate|closing_date|date_fin|datefin|date_de_fin_du_projet|date_dachevement|date_achevement|end_date|enddate|deadline|deadlinedate|application_deadline)\s*[:=]\s*(\d{4})-(\d{2})-(\d{2})",
        r"(?:closingdate|closing_date|date_fin|datefin|date_de_fin_du_projet|date_dachevement|date_achevement|end_date|enddate|deadline|deadlinedate|application_deadline).{0,20}?(\d{4})-(\d{2})-(\d{2})",
    ]
    for pattern in metadata_patterns:
        for match in re.finditer(pattern, sample, re.IGNORECASE):
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                continue

    direct_iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", sample)
    if direct_iso_match:
        try:
            return date(int(direct_iso_match.group(1)), int(direct_iso_match.group(2)), int(direct_iso_match.group(3)))
        except ValueError:
            pass

    numeric_patterns = [
        r"(?:clôture|cloture|date\s*limite|date\s*de\s*clôture|date\s*de\s*cloture|deadline|closing\s+date|jusqu['’]au|avant\s+le|au\s+plus\s+tard\s+le)\s*[:\-]?\s*(?:le\s+|au\s+)?(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",
        r"(?:candidature(?:s)?|dépôt|depot)\s*[:\-]?\s*(?:le\s+|au\s+)?(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",
    ]
    for pattern in numeric_patterns:
        for match in re.finditer(pattern, sample, re.IGNORECASE):
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if year < 100:
                    year += 2000
                return date(year, month, day)
            except ValueError:
                continue

    range_pattern = (
        r"(?:appel|candidature(?:s)?|inscription(?:s)?|depot|dépôt|concours).{0,60}?"
        r"du\s+\d{1,2}(?:er)?\s+"
        r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)"
        r"\s+au\s+(\d{1,2})(?:er)?\s+"
        r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)"
        r"\s+(\d{4})"
    )
    literal_pattern = (
        r"(?:clôture|cloture|date\s*limite|deadline|closing\s+date|jusqu['’]au|avant\s+le|au\s+plus\s+tard\s+le)?"
        r"\s*(\d{1,2})(?:er)?\s+"
        r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)"
        r"\s+(\d{4})"
    )
    month_map = {
        "janvier": 1,
        "février": 2,
        "fevrier": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "août": 8,
        "aout": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "décembre": 12,
        "decembre": 12,
    }
    for match in re.finditer(literal_pattern, sample, re.IGNORECASE):
        try:
            month = month_map.get(match.group(2).lower())
            if month:
                return date(int(match.group(3)), month, int(match.group(1)))
        except ValueError:
            continue

    for match in re.finditer(range_pattern, sample, re.IGNORECASE):
        try:
            month = month_map.get(match.group(4).lower())
            if month:
                return date(int(match.group(5)), month, int(match.group(2)))
        except ValueError:
            continue
    return None


def compute_completeness(device: dict) -> int:
    """Calcule un score de complétude 0-100 basé sur les champs renseignés."""
    REQUIRED = ["title", "organism", "country", "device_type", "short_description"]
    IMPORTANT = ["close_date", "amount_max", "eligibility_criteria", "sectors", "source_url"]
    OPTIONAL = ["full_description", "beneficiaries", "funding_rate", "open_date"]

    score = 0
    score += sum(14 for f in REQUIRED if device.get(f))   # max 70
    score += sum(4 for f in IMPORTANT if device.get(f))    # max 20
    score += sum(2 for f in OPTIONAL if device.get(f))     # max 8
    score += 2 if device.get("keywords") else 0            # max 2
    return min(score, 100)


def extract_keywords(title: str, max_keywords: int = 10) -> list:
    """Extrait les mots significatifs d'un titre."""
    STOP_WORDS = {
        "le", "la", "les", "de", "du", "des", "un", "une", "et", "en",
        "à", "au", "aux", "pour", "par", "sur", "sous", "avec", "dans",
        "ce", "se", "si", "ou", "mais", "donc", "or", "ni", "car",
        "the", "of", "and", "for", "in", "to", "a", "an",
    }
    words = re.findall(r"\b[a-zA-ZÀ-ÿ]{4,}\b", title.lower())
    return list({w for w in words if w not in STOP_WORDS})[:max_keywords]
