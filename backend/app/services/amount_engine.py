"""
AmountEngine — extraction d'amount avec distinction explicite
entre montant bénéficiaire et budget de programme.

Règle fondamentale : ne jamais mettre program_budget dans amount_max.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from unidecode import unidecode

from app.utils.encoding_repair import repair_mojibake


class AmountType(str, Enum):
    BENEFICIARY_AMOUNT = "beneficiary_amount"
    PROGRAM_BUDGET = "program_budget"
    RATE_ONLY = "rate_only"
    RANGE = "range"
    UNKNOWN = "unknown"


class AmountRole(str, Enum):
    """Semantic role of a monetary value found in a text. Only the first and the INVESTMENT_TICKET feed amount_min/max."""
    BENEFICIARY_AMOUNT = "beneficiary_amount"
    ELIGIBLE_EXPENSE_CAP = "eligible_expense_cap"
    ELIGIBLE_EXPENSE_FLOOR = "eligible_expense_floor"
    PROJECT_COST = "project_cost"
    PROGRAM_BUDGET = "program_budget"
    INVESTMENT_TICKET = "investment_ticket"
    ELIGIBILITY_THRESHOLD = "eligibility_threshold"
    UNKNOWN_AMOUNT = "unknown_amount"


@dataclass
class AmountResult:
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    # Currency written in the source next to the amounts. None when the source states none:
    # a currency deduced from the country is never a fact about the aid (see currency_inferred).
    currency: Optional[str] = None
    currency_inferred: Optional[str] = None
    funding_rate: Optional[float] = None
    program_budget: Optional[float] = None
    program_budget_currency: Optional[str] = None
    eligible_expense_cap: Optional[float] = None
    eligible_expense_cap_currency: Optional[str] = None
    eligible_expense_floor: Optional[float] = None
    project_cost: Optional[float] = None
    amount_type: AmountType = AmountType.UNKNOWN
    amount_source_text: Optional[str] = None
    amount_confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    amount_roles: list[tuple] = field(default_factory=list)    # (value, AmountRole, source currency)
    percent_roles: list[tuple] = field(default_factory=list)   # (value, PercentRole, secondary)

    @property
    def currency_source(self) -> Optional[str]:
        return self.currency


# ---- Currency detection ----

_CURRENCY_PATTERNS = (
    (r"\bxof\b|\bfcfa\b|\bfranc cfa\b", "XOF"),
    (r"\bxaf\b|\bfranc cfa d'afrique centrale\b", "XAF"),
    (r"\bmad\b|\bdirham\b", "MAD"),
    (r"\btnd\b|\bdinar\b", "TND"),
    (r"\busd\b|\bu\.s\.\s*dollar|\bdollar am[eé]ricain", "USD"),
    (r"\bgbp\b|\blivre sterling\b", "GBP"),
    (r"\bchf\b|\bfranc suisse\b", "CHF"),
    (r"\bjpy\b|\byen\b", "JPY"),
    (r"€|\beur\b|\beuros\b", "EUR"),
    (r"\$(?!\s*us)", "USD"),  # bare $ (not "$US")
    (r"\$\s*us\b|\bforints\b", "USD"),
)


def detect_currency(text: str) -> str:
    normalized = unidecode((text or "").lower())
    for pattern, currency in _CURRENCY_PATTERNS:
        if re.search(pattern, normalized):
            return currency
    return "EUR"


def detect_currency_for_country(country: str, text: str) -> str:
    """Use text first; fall back to country-based defaults."""
    text_currency = detect_currency(text)
    if text_currency != "EUR":
        return text_currency

    country_lower = (country or "").lower()
    _country_defaults = {
        "côte d'ivoire": "XOF", "cote d'ivoire": "XOF",
        "sénégal": "XOF", "senegal": "XOF",
        "mali": "XOF", "burkina faso": "XOF",
        "togo": "XOF", "bénin": "XOF", "benin": "XOF",
        "guinée": "XOF", "guinee": "XOF",
        "niger": "XOF",
        "cameroun": "XAF", "cameroon": "XAF",
        "congo": "XAF", "rd congo": "XAF", "gabon": "XAF",
        "maroc": "MAD", "morocco": "MAD",
        "tunisie": "TND", "tunisia": "TND",
        "kenya": "KES",
        "nigeria": "NGN", "nigéria": "NGN",
        "ghana": "GHS",
        "éthiopie": "ETB", "ethiopia": "ETB",
        "afrique du sud": "ZAR", "south africa": "ZAR",
        "états-unis": "USD", "usa": "USD", "etats-unis": "USD",
        "royaume-uni": "GBP", "united kingdom": "GBP",
        "suisse": "CHF", "switzerland": "CHF",
    }
    for country_key, currency in _country_defaults.items():
        if country_key in country_lower:
            return currency

    # International/multi-pays → USD by default
    if any(kw in country_lower for kw in ("international", "afrique", "africa", "global", "monde")):
        return "USD"

    return "EUR"



# ---- Money token parsing ----

_CUR_WORDS = (
    r"(?:euros?|eur|usd|dollars?(?!\s+(?:canadiens?|australiens?|canadian|australian))|xof|xaf|"
    r"f\s?cfa|fcfa|cfa|mad|dirhams?|tnd|dinars?|gbp|chf|jpy|cad|kes|ngn|ghs|zar|etb)"
)

_MONEY_NUM = r"(?:\d{1,3}(?:[  .,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?)"

_MONEY_TOKEN_RE = re.compile(
    rf"(?<![a-z\d])"
    rf"(?:(?P<pc>{_CUR_WORDS})(?=\s*\d)\s*)?"
    rf"(?P<num>{_MONEY_NUM})"
    rf"(?P<mult>\s*(?:milliards?|mrds?|billions?|millions?|mio)\b|(?:k|m)\b(?!\d)|\s*[km](?=\s*{_CUR_WORDS}\b))?"
    rf"(?:\s*(?:(?:de|d')\s*)?(?P<sc>{_CUR_WORDS})\b)?"
)

_MULT_VALUES = (
    ("milliard", 1_000_000_000),
    ("mrd", 1_000_000_000),
    ("billion", 1_000_000_000),
    ("million", 1_000_000),
    ("mio", 1_000_000),
)

# A bare number followed by one of these is a quantity, not money.
_UNIT_TAIL_RE = re.compile(
    r"^\s*(?:ans?\b|annees?\b|mois\b|jours?\b|semaines?\b|years?\b|months?\b|days?\b|weeks?\b|"
    r"heures?\b|hours?\b|places?\b|personnes?\b|salaries?\b|employes?\b|km\b|m2\b|habitants?\b|"
    r"projets?\b|pme\b|startups?\b|participants?\b|candidats?\b|beneficiaires?\b|equipes?\b|"
    r"pays\b|villes?\b|entreprises?\b|laureats?\b|households?\b|menages?\b|foyers?\b|familles?\b|"
    r"families\b|enfants\b|children\b|femmes\b|women\b|jeunes\b|youth\b|students?\b|etudiants?\b|eleves?\b|"
    r"agriculteurs\b|farmers\b|producteurs\b|emplois\b|jobs\b)"
)


def _canon_currency(word: str, country_default: str) -> str:
    w = re.sub(r"\s", "", word.lower())
    if w.startswith("eur"):
        return "EUR"
    if w.startswith("dollar") or w == "usd":
        return "USD"
    if w in ("fcfa", "cfa", "xof"):
        return "XAF" if (country_default == "XAF" and w != "xof") else "XOF"
    if w == "xaf":
        return "XAF"
    if w.startswith("dirham") or w == "mad":
        return "MAD"
    if w.startswith("dinar") or w == "tnd":
        return "TND"
    return w.upper()


def _to_float(num: str) -> Optional[float]:
    s = re.sub(r"[\s ]", "", num or "")
    if not s:
        return None
    seps = [c for c in s if c in ".,"]
    try:
        if not seps:
            return float(s)
        if "." in s and "," in s:
            decimal = "." if s.rfind(".") > s.rfind(",") else ","
            thousands = "," if decimal == "." else "."
            return float(s.replace(thousands, "").replace(decimal, "."))
        parts = s.split(seps[0])
        if len(seps) == 1 and len(parts[1]) != 3:
            return float(parts[0] + "." + parts[1])
        return float("".join(parts))
    except ValueError:
        return None


def _parse_number(raw: str) -> Optional[float]:
    """Parse '1 500 000', '1.5M', '350', '2,5 millions', '30000 EUR' → float."""
    if not raw:
        return None
    m = _MONEY_TOKEN_RE.search(unidecode(raw.lower()))
    if not m:
        return None
    return _token_value(m)


def _token_value(m: "re.Match[str]") -> Optional[float]:
    value = _to_float(m.group("num"))
    if value is None:
        return None
    mult = (m.group("mult") or "").strip()
    if mult:
        factor = 1_000 if mult == "k" else 1_000_000 if mult == "m" else next(
            (f for prefix, f in _MULT_VALUES if mult.startswith(prefix)), 1
        )
        value *= factor
    return value


@dataclass
class _Money:
    value: float
    currency: Optional[str]
    start: int
    end: int
    has_mult: bool
    num_value: float


def _prepare(text: str) -> str:
    t = repair_mojibake(text or "")
    t = re.sub(r"\$\s*us\b|\bus\s*\$", " usd ", t, flags=re.IGNORECASE)
    t = t.replace("€", " eur ").replace("$", " usd ").replace("£", " gbp ")
    return unidecode(t.lower())


def _find_money(s: str, country_default: str) -> list[_Money]:
    tokens: list[_Money] = []
    for m in _MONEY_TOKEN_RE.finditer(s):
        value = _token_value(m)
        num_value = _to_float(m.group("num"))
        if value is None or num_value is None or value <= 0:
            continue
        cur_word = m.group("pc") or m.group("sc")
        tail = s[m.end(): m.end() + 24]
        if re.match(r"\s*%", tail):
            continue
        if not cur_word:
            if _UNIT_TAIL_RE.match(tail) or (not m.group("mult") and s[m.end(): m.end() + 1].isalpha()):
                continue
            digits = re.sub(r"\D", "", m.group("num"))
            if not m.group("mult") and len(digits) == 4 and 1990 <= int(digits) <= 2100 and digits == m.group("num").strip():
                continue
        tokens.append(
            _Money(
                value=value,
                currency=_canon_currency(cur_word, country_default) if cur_word else None,
                start=m.start(),
                end=m.end(),
                has_mult=bool(m.group("mult")),
                num_value=num_value,
            )
        )
    return tokens


def parse_money(text: str, country: str = "") -> list[tuple[float, Optional[str]]]:
    """Every money token in `text` as (value, explicit currency or None). No context judgement."""
    s = _prepare(text)
    country_default = detect_currency_for_country(country, "")
    return [(t.value, t.currency) for t in _find_money(s, country_default)]


# ---- Lexical context ----

_PER_BENEFICIARY = (
    r"projets?|project|beneficiaires?|beneficiary|entreprises?|company|laureats?|laureate|winner|startups?|"
    r"candidats?|candidate|porteurs?|structures?|pme|sme|grantee|applicant|recipient|organisations?|"
    r"organizations?|participants?|equipes?|team|chercheurs?|researcher|cooperatives?|associations?|"
    r"collectivites?|dossiers?|lots?|eleves?|etudiants?|students?"
)

_PER_BENEFICIARY_AFTER_RE = re.compile(rf"^\s*(?:(?:par|per|/)\s*(?:{_PER_BENEFICIARY})\b|chacun\b|each\b)")
_PB_AFTER_RE = re.compile(r"^\s*(?:(?:de|d')\s*)?(?:mobilis|debloqu|allou|alloue|leve|decaisse|engage|investi|raised|mobilized|committed|disbursed)")
_NOT_PER_BENEFICIARY = r"(?!\s+(?:per|for\s+each|to\s+each|by\s+each|up\s+to))"
_TOTAL_FUND_AFTER_RE = re.compile(
    r"^\s*(?:(?:fund|funds|budget|envelope|programme|program|initiative|facility)\b" + _NOT_PER_BENEFICIARY
    + r"|(?:in\s+)?(?:total|overall)\b"
    + r"|(?:in\s+)?funding\b" + _NOT_PER_BENEFICIARY + r")"
)
_MAX_AFTER_RE = re.compile(r"^\s*(?:au\s+)?(?:maximum\b|max\b|maxi\b|au\s+plus\b)")
_MIN_AFTER_RE = re.compile(r"^\s*(?:au\s+)?(?:minimum\b|min\b|mini\b|au\s+moins\b)")

_PB_CUE = re.compile(
    r"(?:enveloppe(?:\s+(?:globale|totale|financiere|budgetaire|de\s+financement))?"
    r"|budgets?\s+(?:global|total|totale|du\s+programme|de\s+l'appel|de\s+l'initiative|programme|alloue|dedie|disponible|annuel)"
    r"|dotation\s+(?:globale|totale)"
    r"|financement\s+(?:global|total)"
    r"|montant\s+(?:total|global)"
    r"|(?:programme|appel(?:\s+a\s+projets?)?|fonds|dispositif|initiative|plan)\s+(?:global\s+)?(?:dote|finance|abonde)e?"
    r"|overall\s+budget"
    r"|total\s+(?:programme\s+)?(?:budget|funding|envelope|fund|amount)"
    r"|(?:funding|fund)\s+pool"
    r"|programme\s+budget"
    r"|(?:total\s+)?funding\s+available|available\s+funding)\b"
)
_MAX_CUE = re.compile(
    r"(?:jusqu'?a|up\s+to|maximum(?:\s+of)?|maximale?|max\b\.?|plafond|plafonne(?:e|s|es)?(?:\s+a)?|"
    r"dans\s+la\s+limite(?:\s+d(?:e|'))?|au\s+plus|not\s+exceeding|capped\s+at|limited\s+to|"
    r"peut\s+recevoir|peuvent\s+recevoir|recevoir|can\s+receive|receive|obtenir|"
    rf"par\s+(?:{_PER_BENEFICIARY}))(?![a-z])"
)
_MIN_CUE = re.compile(r"(?:a\s+partir\s+de|minimum(?:\s+of)?|minimale?|min\b\.?|au\s+moins|plancher|at\s+least)(?![a-z])")
_GEN_CUE = re.compile(
    r"(?:aides?|subventions?|prets?|loans?|bourses?|prix|grants?|awards?|prizes?|financements?|dotations?|budgets?|"
    r"montants?|transferts?|transfers?|allocations?|allowances?|stipends?|"
    r"investissements?|tickets?|cheques?)(?![a-z])"
)

# Crédit d'impôt : le taux s'applique à une assiette de dépenses ; un plafond qui suit borne cette assiette, pas l'aide.
_TAX_CREDIT_RE = re.compile(r"credits?\s+d'impots?|tax\s+credits?")
_LIMIT_CLAUSE_RE = re.compile(r"dans\s+la\s+limite")
# « Le crédit d'impôt est plafonné à X » : le plafond porte sur l'aide elle-même, pas sur l'assiette.
_AID_SUBJECT_CEILING_RE = re.compile(r"(?:credit\s+d'impots?|aide|subvention|credit)\s+(?:est\s+|sont\s+)?plafonne")
_PER_YEAR_AFTER_RE = re.compile(r"^\s*(?:par|per|/)\s*(?:an|annee|year|mois|month)\b")

_CUE_MAX_GAP = 30
_CLAUSE_SPLIT_RE = re.compile(r"[;!?\n]|\.\s")

_RANGE_GAP_RE = re.compile(r"^\s*(?:a|to|et|and|-|–|—)\s*$")
_RANGE_CUE_RE = re.compile(
    r"(?:de|from|entre|between|montant|montants|pret|subvention|aide|bourse|ticket|financement|"
    r"dotation|investissement\w*|allant|variant|range)\s*(?::|de|d'|of)?\s*$"
)


# Money that is not an aid amount: a cap on the expenses the aid is computed on, or the project's own cost.
_EXPENSE_WORDS = r"(?:depenses?|couts?|frais|assiette|charges?|investissements?|base)"
_CAP_BEFORE = re.compile(
    rf"(?:(?:plafond|plafonnee?s?|limitee?s?|maximale?|maximum)\s+(?:de\s+|des\s+|d')?(?:l')?{_EXPENSE_WORDS}"
    r"(?:\s+(?:eligibles?|retenues?|admissibles?))?(?:\s+(?:est|sont))?(?:\s+(?:fixee?s?|limitee?s?|plafonnee?s?))?\s*(?:a|de|:)?"
    r"|assiette(?:\s+eligible)?(?:\s+(?:maximale?|plafonnee?|limitee?))?\s*(?:de|a|:)?"
    rf"|{_EXPENSE_WORDS}(?:\s+eligibles?)?\s+(?:plafonnee?s?|limitee?s?)\s+a"
    r"|(?:eligible\s+)?(?:costs?|expenses)\s+(?:capped|limited)\s+(?:at|to)"
    r"|(?:cost|expense)\s+cap(?:\s+of)?)(?![a-z])"
)
_CAP_AFTER_RE = re.compile(
    rf"^\s*(?:(?:hors\s+taxes?|ht|ttc)\s+)?(?:(?:de|d')\s*{_EXPENSE_WORDS}\b|(?:of|in)\s+(?:eligible\s+)?(?:costs?|expenses)\b)"
)
_IGNORE_BEFORE = re.compile(
    r"(?:(?:cout|budget)\s+(?:total\s+)?(?:du|de\s+l[ae]?)\s+(?:projet|operation)"
    r"|cout\s+total"
    r"|(?:total\s+)?project\s+(?:cost|budget)|cost\s+of\s+the\s+project)\s*(?:de|d'|of|a|:)?(?![a-z])"
)


def _cue_tail(s: str, tok: "_Money") -> str:
    clause = _clause_before(s, tok.start)
    last_digit = max((i for i, c in enumerate(clause) if c.isdigit()), default=-1)
    return clause[last_digit + 1:]


def _cue_ends_near(rx: "re.Pattern[str]", tail: str) -> bool:
    last = None
    for m in rx.finditer(tail):
        last = m
    return last is not None and len(tail) - last.end() <= _CUE_MAX_GAP


def _clause_before(s: str, start: int) -> str:
    window = s[max(0, start - 90): start]
    parts = _CLAUSE_SPLIT_RE.split(window)
    return parts[-1] if parts else window


def _classify_cue(s: str, tok: _Money) -> Optional[str]:
    """Nearest lexical cue before the token: 'pb' | 'max' | 'min' | 'gen' | None."""
    clause = _clause_before(s, tok.start)
    last_digit = max((i for i, c in enumerate(clause) if c.isdigit()), default=-1)
    tail = clause[last_digit + 1:]
    best: Optional[tuple[int, int, str]] = None
    for priority, (kind, rx) in enumerate((("pb", _PB_CUE), ("max", _MAX_CUE), ("min", _MIN_CUE), ("gen", _GEN_CUE))):
        last = None
        for m in rx.finditer(tail):
            last = m
        if last is None or len(tail) - last.end() > _CUE_MAX_GAP:
            continue
        key = (last.end(), -priority, kind)
        if best is None or key[:2] > best[:2]:
            best = key
    return best[2] if best else None


# A floor on the size of the expense basis / project ("assiette de dépenses … d'au moins 1 M€") is not an aid amount.
_FLOOR_CUE_RE = re.compile(
    r"au\s+moins|minimum|minimale?s?|min\b\.?|superieur(?:e|es|s)?\s+a|plus\s+de|depassant|excedant|au[- ]dessus\s+de|"
    r"a\s+partir\s+de|at\s+least|more\s+than|greater\s+than|exceed\w*|over\b"
)
_EXPENSE_NOUN_RE = re.compile(
    r"assiette|depenses?|couts?|budget\s+(?:total\s+)?du\s+projet|montant\s+total\s+du\s+projet|taille\s+du\s+projet|"
    r"(?:total\s+)?(?:project|eligible)\s+(?:cost|budget|expenses)"
)
_AID_WORD_RE = re.compile(
    r"aide|subvention|pret\b|financement|dotation|bourse|prix\b|grant|award|prize|loan|funding|benefici\w+|recev\w+|"
    r"obtenir|percevoir|accord\w+|octroy\w+|verse\w*|remboursable"
)
_THRESHOLD_AMOUNT_RE = re.compile(
    r"(?:chiffre\s+d'affaires|turnover|annual\s+revenue|total\s+du\s+bilan|capital\s+social|total\s+assets)[^.]{0,40}"
    r"(?:inferieur\w*|moins\s+de|plus\s+de|superieur\w*|under|below|above|exceed\w*|max\w*|<|>)[^.\d]{0,15}$"
)


def _is_expense_floor(s: str, tok: _Money) -> bool:
    sent = _before(s, tok.start, 170)
    cue = None
    for m in _FLOOR_CUE_RE.finditer(sent):
        cue = m
    noun = _EXPENSE_NOUN_RE.search(sent)
    if cue is None or noun is None or len(sent) - cue.end() > 45:
        return False
    # Anything the sentence says about aid / beneficiaries after the expense wording makes it an aid amount instead.
    return _AID_WORD_RE.search(sent[min(cue.start(), noun.start()):]) is None


def _is_threshold_amount(s: str, tok: _Money) -> bool:
    return _THRESHOLD_AMOUNT_RE.search(_before(s, tok.start, 110)) is not None


def _classify_token(s: str, tok: _Money, currency: str) -> Optional[str]:
    """'pb' | 'max' | 'min' | 'cap' | 'floor' | 'project_cost' | 'threshold' | None. Lexical context first; the size threshold only arbitrates weak cues."""
    if tok.currency is None and not tok.has_mult and tok.value < 100:
        return None
    after = s[tok.end: tok.end + 40]
    tail = _cue_tail(s, tok)
    if _is_threshold_amount(s, tok):
        return "threshold"
    if _is_expense_floor(s, tok):
        return "floor"
    if _CAP_AFTER_RE.match(after) or _cue_ends_near(_CAP_BEFORE, tail):
        return "cap"
    if _cue_ends_near(_IGNORE_BEFORE, tail):
        return "project_cost"
    before_kind = _classify_cue(s, tok)
    if before_kind != "min" and _PER_BENEFICIARY_AFTER_RE.match(after):
        return "max"
    if before_kind not in ("pb", "max", "min") and _PB_AFTER_RE.match(after):
        return "pb"
    if before_kind not in ("pb", "max", "min") and tok.has_mult and _TOTAL_FUND_AFTER_RE.match(after):
        return "pb"   # "€2 Million Funding", "a $5 million fund": the size of the fund, not what a beneficiary receives
    if before_kind != "pb":
        if _MAX_AFTER_RE.match(after):
            return "max"
        if _MIN_AFTER_RE.match(after):
            return "min"
    if before_kind in ("pb", "max", "min"):
        return before_kind
    if before_kind == "gen":
        if tok.currency is None and not tok.has_mult:
            return None
        return "pb" if _is_likely_program_budget(tok.value, currency) else "max"
    return None


# ---- Percentages: semantic role of every "N %" ----


class PercentRole(str, Enum):
    FUNDING_RATE = "funding_rate"
    ELIGIBILITY_THRESHOLD = "eligibility_threshold"
    PARTNER_SHARE_CAP = "partner_share_cap"
    EXPENSE_SHARE = "expense_share"
    OTHER_PERCENTAGE = "other_percentage"


_PCT_RE = re.compile(r"(?:(?P<lo>\d{1,3}(?:[.,]\d+)?)\s*(?:et|and|-|a|to)\s+)?(?P<v>\d{1,3}(?:[.,]\d+)?)\s*%")
_SENTENCE_SPLIT_RE = re.compile(r"\.\s|[!?\n]")

# The share applies to a company attribute (eligibility criterion), not to the aid.
_THRESHOLD_AFTER_RE = re.compile(
    r"^\s*(?:du\s+|de\s+la\s+|de\s+l'|des\s+|de\s+)?(?:chiffre\s+d'affaires|ca\b|charges?\b|capital|effectifs?|masse\s+salariale\s+totale|"
    r"total\s+du\s+bilan|actifs?|turnover|revenues?|droits\s+de\s+vote|parts\s+sociales|budget\s+(?:total\s+)?de\s+l'entreprise)"
)
_THRESHOLD_BEFORE_RE = re.compile(r"(?:seuil|threshold|detenu\w*|detient|detiennent|holds?|owned?)[^.]{0,40}$")
# A partner / country / member may not exceed a share of the project budget: a participation limit, not a subsidy rate.
_PARTNER_BEFORE_RE = re.compile(
    r"(?:ne\s+doi(?:t|vent)\s+pas\s+(?:representer|depasser)|no\s+more\s+than|not\s+(?:to\s+)?exceed|must\s+not\s+exceed|cannot\s+exceed|"
    r"pas\s+plus\s+de|part\s+maximale|at\s+most)[^.]{0,20}$"
)
_PARTNER_SUBJECT_RE = re.compile(r"partenaires?|partners?|pays\b|countr(?:y|ies)|consortium|membres?|entites?|organismes?|represent")
_BUDGET_AFTER_RE = re.compile(r"^\s*(?:du|of\s+the|de\s+l[ae]?|des?)\s*(?:total\s+)?(?:budget|couts?|costs?|project\s+budget)")
# Flat-rate expense computation rules ("fixées forfaitairement à 75 % des dotations…").
_EXPENSE_SHARE_BEFORE_RE = re.compile(r"(?:forfait\w*|fixee?s?\s+a|calcule\w*\s+(?:sur|a))[^.]{0,80}$")
_EXPENSE_SHARE_AFTER_RE = re.compile(
    r"^\s*(?:des|de\s+la|du)\s+(?:dotations?|depenses?\s+de\s+(?:personnel|fonctionnement)|masse|remunerations?|frais\s+(?:generaux|de\s+personnel)|amortissements?)"
)
_EXPENSE_LINE_ITEM_RE = re.compile(r"pour\s*$")
_FUNDING_BEFORE_RE = re.compile(
    r"(?:taux\s+(?:d'intervention|de\s+subvention|de\s+financement|de\s+prise\s+en\s+charge|d'aide|maximum|maximal|de\s+credit\s+d'impot)\s*(?:de|:|=|a)?"
    r"|(?:financ\w+|subventionn\w+|couvr\w+|couvert\w*|rembours\w+|prise\s+en\s+charge|prend\s+en\s+charge|garanti\w*|cover\w*|grant\w*|fund\w*)\s*(?:de|d'|a|:|-)?\s*(?:hauteur\s+de\s+)?"
    r"|a\s+hauteur\s+de|jusqu'?a|up\s+to"
    r"|(?:subvention|aide|credit\s+d'impot|pret)\s+(?:de|a|d')"
    r"|credit\s+d'impot\s+representant\s*[:\-\s]*)\s*$"
)
_FUNDING_AFTER_RE = re.compile(
    r"^\s*(?:du\s+montant\s+des\s+|des\s+|du\s+|de\s+l[ae]?\s+)?(?:depenses?|couts?|frais|investissements?|assiette|montant\s+eligible|costs?|expenses|eligible|remboursable|non\s+remboursable|de\s+couverture|de\s+financement|de\s+prise\s+en\s+charge|sur\s+(?:une\s+|l')?(?:assiette|base|depenses))"
)
_SECONDARY_BEFORE_RE = re.compile(r"major\w*|porte\w*\s+a|bonus|supplementaire|prefinanc\w*|avance\b|au[- ]dela|hors\s+plafond|complement\w*")
_SECONDARY_AFTER_RE = re.compile(r"sans\s+plafond|au[- ]dela|au[- ]dessus|prestation|expert|consultant|diagnostic|prestataire")
_SECONDARY_AFTER_WINDOW = 120


@dataclass
class _Percent:
    value: float
    role: PercentRole
    secondary: bool
    start: int


def _before(s: str, start: int, width: int = 110) -> str:
    window = s[max(0, start - width): start]
    parts = _SENTENCE_SPLIT_RE.split(window)
    return parts[-1] if parts else window


def _classify_percentages(s: str) -> list[_Percent]:
    found: list[_Percent] = []
    for m in _PCT_RE.finditer(s):
        try:
            value = float(m.group("v").replace(",", "."))
        except ValueError:
            continue
        if not 0 < value <= 100:
            continue
        before = _before(s, m.start())
        after = s[m.end(): m.end() + 90]
        has_range = m.group("lo") is not None
        role = PercentRole.OTHER_PERCENTAGE
        if _THRESHOLD_AFTER_RE.match(after) and not _FUNDING_BEFORE_RE.search(before) or _THRESHOLD_BEFORE_RE.search(before):
            role = PercentRole.ELIGIBILITY_THRESHOLD
        elif _PARTNER_BEFORE_RE.search(before) and _BUDGET_AFTER_RE.match(after) and (_PARTNER_SUBJECT_RE.search(before) or _PARTNER_SUBJECT_RE.search(after[:120]) or "represent" in before):
            role = PercentRole.PARTNER_SHARE_CAP
        elif (_EXPENSE_SHARE_BEFORE_RE.search(before) and _EXPENSE_SHARE_AFTER_RE.match(after)) or (
            _EXPENSE_LINE_ITEM_RE.search(before) and re.match(r"^\s*du\s+montant\s*\)", after)
        ):
            role = PercentRole.EXPENSE_SHARE
        elif not has_range and (_FUNDING_BEFORE_RE.search(before) or _FUNDING_AFTER_RE.match(after)):
            role = PercentRole.FUNDING_RATE
        secondary = bool(_SECONDARY_BEFORE_RE.search(before[-90:]) or _SECONDARY_AFTER_RE.search(after[:_SECONDARY_AFTER_WINDOW]))
        found.append(_Percent(value, role, secondary, m.start()))
    return found


def _pick_funding_rate(percents: list[_Percent]) -> Optional[float]:
    """The main rate: first FUNDING_RATE that is not a bonus / above-ceiling / sub-scheme rate. Never invents one."""
    for p in percents:
        if p.role == PercentRole.FUNDING_RATE and not p.secondary:
            return p.value
    return None


# A service paid for by the funder ("financée à 100 %") is not a funding rate when the source says there is no direct funding.
_NO_DIRECT_FUNDING_RE = re.compile(
    r"pas\s+de\s+financement(?:\s+direct)?|sans\s+financement|aucun\s+financement|(?:appui|accompagnement|aide|soutien)\s+(?:est\s+)?(?:surtout\s+|principalement\s+)?non[-\s]financ|"
    r"no\s+(?:direct\s+)?(?:funding|financing|financial)"
)

# Fallback threshold: arbitrates only weak cues ("subvention de X"), never overrides explicit context.
_PROGRAM_BUDGET_THRESHOLD_EUR = 10_000_000
_PROGRAM_BUDGET_THRESHOLD_XOF = 5_000_000_000


def _is_likely_program_budget(value: float, currency: str) -> bool:
    if currency in ("XOF", "XAF"):
        return value >= _PROGRAM_BUDGET_THRESHOLD_XOF
    return value >= _PROGRAM_BUDGET_THRESHOLD_EUR


_ROLE_OF_KIND = {
    "pb": AmountRole.PROGRAM_BUDGET,
    "max": AmountRole.BENEFICIARY_AMOUNT,
    "min": AmountRole.BENEFICIARY_AMOUNT,
    "cap": AmountRole.ELIGIBLE_EXPENSE_CAP,
    "floor": AmountRole.ELIGIBLE_EXPENSE_FLOOR,
    "project_cost": AmountRole.PROJECT_COST,
    "threshold": AmountRole.ELIGIBILITY_THRESHOLD,
}
_INVESTMENT_RE = re.compile(r"invest\w*|ticket|equity|capital|fonds\b|fund\b|venture|seed|amorcage")


class AmountEngine:
    """
    Extrait les montants d'une fiche en déterminant le rôle sémantique de chaque valeur.

    Montants (AmountRole) : seuls BENEFICIARY_AMOUNT et INVESTMENT_TICKET alimentent amount_min / amount_max.
    Pourcentages (PercentRole) : seul FUNDING_RATE alimente funding_rate (exprimé en % : 70 = 70 %).
    La devise n'est renseignée que si la source l'écrit ; la devise déduite du pays reste dans currency_inferred.
    """

    def extract(self, text: str, country: str = "", *, institutional_project: bool = False) -> AmountResult:
        result = AmountResult()
        s = _prepare(text)
        country_default = detect_currency_for_country(country, "")
        inferred = detect_currency_for_country(country, s)
        result.currency_inferred = inferred

        percents = _classify_percentages(s)
        result.percent_roles = [(p.value, p.role.value, p.secondary) for p in percents]
        result.funding_rate = None if _NO_DIRECT_FUNDING_RE.search(s) else _pick_funding_rate(percents)
        if result.funding_rate is not None:
            result.signals.append(f"rate:{result.funding_rate}")

        tokens = _find_money(s, country_default)
        used: set[int] = set()
        beneficiary_currency: Optional[str] = None
        source_currency: Optional[str] = None
        source_span: Optional[tuple[int, int]] = None

        def note(tok: _Money, role: AmountRole) -> None:
            result.amount_roles.append((tok.value, role.value, tok.currency))

        # Ranges first: "de X à Y", "entre X et Y", "X to Y"
        for i in range(len(tokens) - 1):
            if i in used or i + 1 in used:
                continue
            t1, t2 = tokens[i], tokens[i + 1]
            gap = s[t1.end: t2.start]
            if not _RANGE_GAP_RE.match(gap):
                continue
            explicit_cur = t1.currency or t2.currency
            clause = _clause_before(s, t1.start)
            if not (explicit_cur or _RANGE_CUE_RE.search(clause)):
                continue
            if gap.strip() in ("-", "–", "—") and not explicit_cur:
                continue
            if _PB_CUE.search(clause[-_CUE_MAX_GAP:]):
                continue
            if _is_expense_floor(s, t1) or _is_threshold_amount(s, t1):
                continue
            v1, v2 = t1.value, t2.value
            if not t1.has_mult and t2.has_mult and t1.num_value < t2.num_value:
                v1 = t1.num_value * (t2.value / t2.num_value)
            if not v1 < v2:
                continue
            if result.amount_type == AmountType.RANGE and (v1, v2) != (result.amount_min, result.amount_max):
                continue
            if result.amount_type != AmountType.RANGE:
                result.amount_min, result.amount_max = v1, v2
                result.amount_type = AmountType.RANGE
                beneficiary_currency = t1.currency or t2.currency
                source_span = (t1.start, t2.end)
                result.signals.append(f"range:{v1}-{v2}")
                role = AmountRole.INVESTMENT_TICKET if _INVESTMENT_RE.search(clause[-60:]) else AmountRole.BENEFICIARY_AMOUNT
                note(t1, role)
                note(t2, role)
            used.update((i, i + 1))

        max_tok: Optional[_Money] = None
        for i, tok in enumerate(tokens):
            if i in used:
                continue
            kind = _classify_token(s, tok, tok.currency or inferred)
            if kind is None:
                note(tok, AmountRole.UNKNOWN_AMOUNT)
                continue
            note(tok, _ROLE_OF_KIND[kind])
            if kind == "pb":
                if result.program_budget is None:
                    result.program_budget = tok.value
                    result.program_budget_currency = tok.currency
                    result.signals.append(f"program_budget:{tok.value}")
                    if source_span is None and result.amount_max is None:
                        source_span = (tok.start, tok.end)
                    source_currency = source_currency or tok.currency
            elif kind == "cap":
                if result.eligible_expense_cap is None:
                    result.eligible_expense_cap = tok.value
                    result.eligible_expense_cap_currency = tok.currency
                    result.signals.append(f"eligible_expense_cap:{tok.value}")
            elif kind == "floor":
                if result.eligible_expense_floor is None:
                    result.eligible_expense_floor = tok.value
                    result.signals.append(f"eligible_expense_floor:{tok.value}")
            elif kind == "project_cost":
                if result.project_cost is None:
                    result.project_cost = tok.value
                result.signals.append(f"project_cost:{tok.value}")
            elif kind == "threshold":
                result.signals.append(f"eligibility_threshold_amount:{tok.value}")
            elif kind == "max" and result.amount_max is None:
                max_tok = tok
                result.amount_max = tok.value
                beneficiary_currency = tok.currency or beneficiary_currency
                source_span = (tok.start, tok.end)
                result.signals.append(f"beneficiary_max:{tok.value}")
            elif kind == "min" and result.amount_min is None:
                result.amount_min = tok.value
                beneficiary_currency = tok.currency or beneficiary_currency
                result.signals.append(f"beneficiary_min:{tok.value}")

        if (
            max_tok is not None
            and result.amount_type != AmountType.RANGE
            and result.funding_rate is not None
            and _TAX_CREDIT_RE.search(s)
            and _LIMIT_CLAUSE_RE.search(_cue_tail(s, max_tok))
            and not _AID_SUBJECT_CEILING_RE.search(_cue_tail(s, max_tok))
            and not _PER_BENEFICIARY_AFTER_RE.match(s[max_tok.end: max_tok.end + 40])
            and not _PER_YEAR_AFTER_RE.match(s[max_tok.end: max_tok.end + 40])
        ):
            result.eligible_expense_cap = result.eligible_expense_cap or max_tok.value
            result.eligible_expense_cap_currency = result.eligible_expense_cap_currency or max_tok.currency
            result.amount_max = None
            result.signals.append("tax_credit_ceiling_is_expense_cap")

        if result.amount_min is not None and result.amount_max is not None and result.amount_min > result.amount_max:
            result.amount_min = None

        if institutional_project and (result.amount_min is not None or result.amount_max is not None):
            # Costs and financing lines of a multilateral / government project are not an amount a company can obtain.
            result.project_cost = result.project_cost or result.amount_max or result.amount_min
            result.amount_min = result.amount_max = None
            result.amount_type = AmountType.UNKNOWN
            beneficiary_currency = None
            result.signals.append("institutional_project_amounts_not_beneficiary")

        # An institutional project offers no amount to a beneficiary, hence no currency to attach to the record.
        result.currency = None if institutional_project else (beneficiary_currency or source_currency)
        if result.currency:
            result.currency_inferred = result.currency
        if source_span:
            result.amount_source_text = s[max(0, source_span[0] - 30): source_span[1] + 30].strip()

        has_beneficiary = result.amount_min is not None or result.amount_max is not None
        if result.amount_type == AmountType.RANGE and has_beneficiary:
            pass
        elif has_beneficiary:
            both = result.amount_min is not None and result.amount_max is not None
            result.amount_type = AmountType.RANGE if both else AmountType.BENEFICIARY_AMOUNT
        elif result.program_budget is not None:
            result.amount_type = AmountType.PROGRAM_BUDGET
        elif result.funding_rate is not None:
            result.amount_type = AmountType.RATE_ONLY
        else:
            result.amount_type = AmountType.UNKNOWN

        if result.amount_type == AmountType.BENEFICIARY_AMOUNT and result.amount_max:
            result.amount_confidence = 0.85
        elif result.amount_type == AmountType.RANGE:
            result.amount_confidence = 0.90
        elif result.amount_type == AmountType.PROGRAM_BUDGET:
            result.amount_confidence = 0.70
        elif result.amount_type == AmountType.RATE_ONLY:
            result.amount_confidence = 0.75
        else:
            result.amount_confidence = 0.0

        return result
