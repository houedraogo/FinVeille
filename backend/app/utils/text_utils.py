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


def _same_text(left: str | None, right: str | None) -> bool:
    normalized_left = unidecode(clean_editorial_text(left or "").lower())
    normalized_right = unidecode(clean_editorial_text(right or "").lower())
    return bool(normalized_left) and normalized_left == normalized_right


def build_structured_sections(
    *,
    presentation: str | None = None,
    eligibility: str | None = None,
    funding: str | None = None,
    open_date: date | None = None,
    close_date: date | None = None,
    procedure: str | None = None,
    recurrence_notes: str | None = None,
) -> str | None:
    """Construit un full_description metier propre et dedupe."""

    presentation_text = clean_editorial_text(presentation or "")
    eligibility_text = clean_editorial_text(eligibility or "")
    funding_text = clean_editorial_text(funding or "")
    procedure_text = clean_editorial_text(procedure or "")
    recurrence_text = clean_editorial_text(recurrence_notes or "")

    if _same_text(eligibility_text, presentation_text):
        eligibility_text = ""
    if _same_text(funding_text, presentation_text) or _same_text(funding_text, eligibility_text):
        funding_text = ""
    if _same_text(procedure_text, presentation_text) or _same_text(procedure_text, eligibility_text) or _same_text(procedure_text, funding_text):
        procedure_text = ""

    sections: list[tuple[str, str]] = []

    sections.append(
        (
            "Presentation",
            presentation_text or "La source ne fournit pas encore de presentation editoriale exploitable.",
        )
    )

    sections.append(
        (
            "Criteres d'eligibilite",
            eligibility_text or "Les criteres detailles doivent etre confirmes sur la source officielle.",
        )
    )

    sections.append(
        (
            "Montant / avantages",
            funding_text or "Le montant ou les avantages ne sont pas precises clairement par la source.",
        )
    )

    calendar_lines = []
    if open_date:
        calendar_lines.append(f"- Ouverture : {open_date.strftime('%d/%m/%Y')}")
    if close_date:
        calendar_lines.append(f"- Cloture : {close_date.strftime('%d/%m/%Y')}")
    if recurrence_text and not any(_same_text(recurrence_text, line) for line in calendar_lines):
        calendar_lines.append(f"- Rythme : {recurrence_text}")
    if not calendar_lines:
        calendar_lines.append("- Calendrier non communique clairement par la source.")
    sections.append(("Calendrier", "\n".join(calendar_lines)))

    sections.append(
        (
            "Demarche",
            procedure_text or "La consultation detaillee et la candidature se font depuis la source officielle.",
        )
    )

    full_description = "\n\n".join(f"## {title}\n{content}" for title, content in sections if content)
    return full_description.strip() or None


def _split_editorial_sentences(text: str) -> list[str]:
    cleaned = clean_editorial_text(text or "")
    if not cleaned:
        return []
    normalized = re.sub(r"([.;!?])(?=\S)", r"\1 ", cleaned)
    parts = re.split(r"(?<=[.;!?])\s+|\n+", normalized)
    sentences = []
    seen = set()
    for part in parts:
        value = clean_editorial_text(part)
        if not value:
            continue
        normalized_value = unidecode(value.lower())
        if normalized_value in seen:
            continue
        seen.add(normalized_value)
        sentences.append(value)
    return sentences


def _pick_sentences_by_keywords(text: str, keywords: tuple[str, ...], limit: int = 2) -> list[str]:
    matches = []
    seen = set()
    for sentence in _split_editorial_sentences(text):
        normalized = unidecode(sentence.lower())
        if not any(keyword in normalized for keyword in keywords):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        matches.append(sentence)
        if len(matches) >= limit:
            break
    return matches


def _format_beneficiaries(beneficiaries) -> str:
    if not beneficiaries:
        return ""
    if isinstance(beneficiaries, str):
        values = [clean_editorial_text(beneficiaries)]
    else:
        values = [clean_editorial_text(str(value)) for value in beneficiaries if clean_editorial_text(str(value))]
    normalized = []
    seen = set()
    for value in values:
        key = unidecode(value.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value.lower())
    if not normalized:
        return ""
    if len(normalized) == 1:
        return normalized[0]
    if len(normalized) == 2:
        return f"{normalized[0]} et {normalized[1]}"
    return f"{', '.join(normalized[:-1])} et {normalized[-1]}"


def _format_scope(country: str | None = None, geographic_scope: str | None = None) -> str:
    scope = unidecode(clean_editorial_text(geographic_scope or "").lower())
    country_label = clean_editorial_text(country or "")
    if scope == "regional":
        return "a l'echelle regionale"
    if scope == "national":
        if country_label:
            return f"sur l'ensemble du territoire {country_label}"
        return "a l'echelle nationale"
    if scope == "local":
        return "sur un perimetre local"
    if scope == "international":
        return "a l'international"
    if scope == "continental":
        return "a l'echelle continentale"
    if country_label:
        return f"en {country_label}"
    return ""


def build_contextual_eligibility(
    *,
    text: str | None = None,
    beneficiaries=None,
    country: str | None = None,
    geographic_scope: str | None = None,
) -> str:
    keywords = (
        "eligible",
        "eligibil",
        "beneficia",
        "adresse",
        "destine",
        "reserve",
        "pme",
        "tpe",
        "eti",
        "startup",
        "association",
        "collectiv",
        "entreprise",
        "artisan",
        "agric",
        "porteur",
    )
    sentences = _pick_sentences_by_keywords(text or "", keywords, limit=2)
    parts = list(sentences)

    beneficiaries_label = _format_beneficiaries(beneficiaries)
    scope_label = _format_scope(country=country, geographic_scope=geographic_scope)

    if beneficiaries_label:
        sentence = f"Le dispositif s'adresse notamment aux {beneficiaries_label}."
        if scope_label:
            sentence = f"Le dispositif s'adresse notamment aux {beneficiaries_label} {scope_label}."
        if not any(unidecode(sentence.lower()) == unidecode(part.lower()) for part in parts):
            parts.append(sentence)
    elif scope_label:
        parts.append(f"Le dispositif s'applique {scope_label}.")

    if not parts:
        parts.append("Les criteres detailles doivent etre confirmes sur la source officielle.")
    else:
        parts.append("Les conditions detaillees de recevabilite doivent etre confirmees sur la source officielle.")

    return " ".join(parts).strip()


def build_contextual_funding(
    *,
    text: str | None = None,
    device_type: str | None = None,
    amount_min=None,
    amount_max=None,
    currency: str | None = None,
) -> str:
    if amount_min is not None or amount_max is not None:
        def _format_amount(value) -> str:
            if value is None:
                return ""
            try:
                amount = float(value)
            except (TypeError, ValueError):
                return clean_editorial_text(str(value))
            if amount.is_integer():
                amount_str = f"{int(amount):,}".replace(",", " ")
            else:
                amount_str = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
            return f"{amount_str} {(currency or 'EUR').strip()}".strip()

        if amount_min and amount_max and amount_min != amount_max:
            return f"Montant indicatif compris entre {_format_amount(amount_min)} et {_format_amount(amount_max)}."
        amount = amount_max or amount_min
        if amount is not None:
            return f"Montant indicatif : {_format_amount(amount)}."

    keywords = (
        "montant",
        "subvention",
        "pret",
        "garantie",
        "avance",
        "prise en charge",
        "financement",
        "taux",
        "plafond",
        "exoner",
        "abattement",
        "dotation",
        "cofinancement",
        "%",
        "euro",
        "eur",
    )
    sentences = _pick_sentences_by_keywords(text or "", keywords, limit=2)
    if sentences:
        merged = " ".join(sentences).strip()
        normalized = unidecode(merged.lower())
        if not any(marker in normalized for marker in ("montant", "taux", "%", "euro", "eur", "prise en charge", "plafond")):
            merged += " Le montant exact doit etre confirme sur la fiche officielle."
        return merged

    default_messages = {
        "subvention": "La source reference ce dispositif comme une subvention, mais le montant exact doit etre confirme sur la fiche officielle.",
        "pret": "La source reference ce dispositif comme un pret, mais ses modalites financieres exactes doivent etre confirmees sur la fiche officielle.",
        "garantie": "La source reference ce dispositif comme une garantie ou un partage de risque, a confirmer sur la fiche officielle.",
        "aap": "Les avantages associes a cet appel doivent etre confirmes sur la fiche officielle.",
        "concours": "La source mentionne un concours ou une dotation, mais les avantages exacts doivent etre confirmes sur la fiche officielle.",
    }
    return default_messages.get(device_type or "", "Le montant ou les avantages ne sont pas precises clairement par la source.")


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


def has_recurrence_evidence(text: str | None) -> bool:
    sample = f" {unidecode(sanitize_text(text or '').lower())} "
    markers = (
        " ouvert en continu ",
        " ouverte en continu ",
        " toute l'annee ",
        " toute l annee ",
        " permanent ",
        " permanente ",
        " recurrent ",
        " recurrente ",
        " reconduit chaque annee ",
        " sans date limite ",
        " au fil de l'eau ",
        " au fil de l eau ",
        " a tout moment ",
        " dispositif permanent ",
        " dispositif recurrent ",
    )
    return any(marker in sample for marker in markers)


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
