"""
DeviceQualityGate — décision de qualité en 4 états, fondée sur des critères métier.

VALID           → auto_published
SUSPECT         → auto_published + tag quality:suspect (publiée mais incomplète)
REVIEW_REQUIRED → pending_review
INVALID         → rejected

Critères (aucun seuil de longueur de description) :
  nature de l'opportunité · bénéficiaire identifiable · mécanisme financier identifiable ·
  source exploitable · territoire identifiable · deadline / récurrence correctement représentée ·
  absence de contradiction critique.

Principe : « information absente de la source » ≠ « information non extraite ».
Un montant présent dans le texte mais pas dans les champs structurés compte comme identifiable ;
une échéance que la source déclare ne pas communiquer est documentée, pas manquante.

Politique de deadline :
  deadline connue                          → OK
  récurrent / statut d'attente documenté   → OK
  source déclare ne communiquer aucune date → SUSPECT publiable si le reste est fiable
  impossible de déterminer s'il y en a une → REVIEW_REQUIRED (raison open_without_close_date)
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlparse

from unidecode import unidecode

from app.services.amount_engine import AmountEngine
from app.services.content_classifier import BENEFICIARY_RE, UNUSABLE_SOURCE_MARKERS, ContentClassifier, ContentType
from app.utils.encoding_repair import looks_mojibake
from app.utils.text_utils import clean_editorial_text, looks_english_text


@dataclass(frozen=True)
class QualityDecision:
    decision: str          # "publish" | "pending_review" | "reject"
    validation_status: str # "auto_published" | "pending_review" | "rejected"
    quality_state: str     # "VALID" | "SUSPECT" | "REVIEW_REQUIRED" | "INVALID"
    score: int
    reasons: list[str]
    content_type: str = "UNKNOWN"
    criteria: dict = field(default_factory=dict)


_classifier = ContentClassifier()
_amounts = AmountEngine()

_TERRITORY = re.compile(
    r"(?<![a-z])(?:france|cote d'ivoire|senegal|mali|burkina|togo|benin|niger|guinee|cameroun|cameroon|congo|gabon|maroc|"
    r"morocco|tunisie|tunisia|algerie|kenya|nigeria|ghana|ethiopi\w+|afrique|africa|europe|europeen\w*|international|"
    r"mondial\w*|worldwide|global|outre-mer|uemoa|cedeao|ecowas|sub-saharan|union europeenne|monde|region|regional\w*|"
    r"departement|metropole|territoire)(?![a-z])"
)
_NO_DEADLINE = re.compile(
    r"sans date limite|pas de date limite|aucune date limite|no (?:specific )?deadline|open[- ]ended|rolling|en continu|"
    r"au fil de l'eau|permanent|apply anytime|toute l'annee|ongoing|"
    r"date limite\s*:?\s*(?:a confirmer|non communiquee|non precisee|non definie|contacter)|"
    r"deadline (?:not|to be) (?:specified|confirmed|announced)|dates? non communiquee"
)
_SOURCE_UNAVAILABLE = re.compile(r"source (?:non disponible|indisponible)|page indisponible|contenu indisponible")
_STOPWORDS = frozenset(
    "avec dans pour cette dont sont mais plus tous tout leur leurs entre chez sans sous vers ainsi comme "
    "that this with from have will your their which about into more than also such been were what when where".split()
)


def _is_absolute_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


_EN_WORDS = frozenset(
    "the and for with from of per is are be by or apply application applications deadline eligibility grants open up no any "
    "specific ongoing process research fund supporting to in as".split()
)
_FR_WORDS = frozenset("le la les des du de et pour avec dans sur par est sont au aux une un en ce cette qui que ou".split())
_RECURRENCE_TEXT = re.compile(
    r"chaque annee|annuel(?:le)?|tous les (?:ans|mois)|mensuel(?:le)?|recurren\w+|editions? consecutives|permanent|"
    r"en continu|au fil de l'eau|recurring|annual|every year|rolling"
)


def _english_language(text: str) -> bool:
    """Ratio de mots-outils anglais / français : plus robuste que le décompte de marqueurs sur de courts textes."""
    words = re.findall(r"[a-z']+", unidecode(text.lower()))
    en = sum(1 for w in words if w in _EN_WORDS)
    fr = sum(1 for w in words if w in _FR_WORDS)
    return en >= 3 and en > 2 * fr


def _informative_tokens(text: str) -> int:
    return len({w for w in re.findall(r"[a-z]{4,}", text) if w not in _STOPWORDS})


_STATES = {
    "VALID": ("publish", "auto_published"),
    "SUSPECT": ("publish", "auto_published"),
    "REVIEW_REQUIRED": ("pending_review", "pending_review"),
    "INVALID": ("reject", "rejected"),
}


def _decide(state: str, reasons: list[str], score: int, content_type: str, criteria: dict | None = None) -> QualityDecision:
    decision, validation_status = _STATES[state]
    return QualityDecision(decision, validation_status, state, score, reasons, content_type, criteria or {})


class DeviceQualityGate:
    """Décide si une fiche peut être publiée automatiquement ou non."""

    def evaluate(self, device: dict[str, Any]) -> QualityDecision:
        raw_title = str(device.get("title") or "")
        title = clean_editorial_text(raw_title)
        short_description = clean_editorial_text(device.get("short_description") or "")
        full_description = clean_editorial_text(device.get("full_description") or "")
        eligibility_criteria = clean_editorial_text(device.get("eligibility_criteria") or "")
        funding_details = clean_editorial_text(device.get("funding_details") or "")
        source_raw = clean_editorial_text(device.get("source_raw") or "")
        source_url = str(device.get("source_url") or "")
        status = str(device.get("status") or "open").lower()
        is_recurring = bool(device.get("is_recurring"))
        close_date = device.get("close_date")

        blob = unidecode(
            " ".join(
                v.lower() for v in (short_description, full_description, eligibility_criteria, funding_details, source_raw) if v
            )
        )

        # ---- Source inutilisable / champs requis ----
        if any(marker in blob for marker in UNUSABLE_SOURCE_MARKERS):
            return _decide("INVALID", ["unusable_source_page"], 0, "UNKNOWN")
        if not title or not short_description or not source_url:
            return _decide("INVALID", ["missing_required_fields"], 0, "UNKNOWN")

        # ---- Nature de l'opportunité ----
        classification = _classifier.classify(device)
        content_type = classification.content_type
        ct = content_type.value
        confident = classification.confidence >= 0.70
        if content_type in (ContentType.RESULT_ANNOUNCEMENT, ContentType.NEWS, ContentType.PUBLIC_PROCUREMENT) and confident:
            return _decide("INVALID", [f"content_type:{ct.lower()}"], 10, ct)
        if content_type == ContentType.INSTITUTIONAL_PROJECT and confident:
            if classification.private_access_denied:
                return _decide("INVALID", ["content_type:institutional_project", "private_access_denied"], 10, ct)
            return _decide("REVIEW_REQUIRED", ["content_type:institutional_project"], 10, ct)
        if content_type == ContentType.EVENT and confident:
            return _decide("REVIEW_REQUIRED", ["content_type:event"], 10, ct)

        # ---- Faits sur la fiche ----
        non_financial = content_type == ContentType.NON_FINANCIAL_SUPPORT
        beneficiary = bool(BENEFICIARY_RE.search(blob)) or len(eligibility_criteria) >= 30
        text_amounts = _amounts.extract(
            f"{funding_details} {short_description} {full_description}", country=str(device.get("country") or "")
        )
        quantified = bool(
            device.get("amount_min") or device.get("amount_max") or device.get("funding_rate")
            or text_amounts.amount_min or text_amounts.amount_max or text_amounts.funding_rate
            or text_amounts.eligible_expense_cap
        )
        program_budget = bool(device.get("_program_budget") or text_amounts.program_budget)
        if quantified:
            mechanism = "quantified"
        elif program_budget:
            mechanism = "program_budget"
        elif classification.financial_mechanism:
            mechanism = "instrument"
        else:
            mechanism = "none"
        territory = bool(str(device.get("country") or "").strip()) or bool(_TERRITORY.search(blob))

        # ---- Deadline / récurrence ----
        close_date_in_past = False
        parsed_close_date = None
        if close_date:
            try:
                parsed_close_date = close_date if isinstance(close_date, date) else date.fromisoformat(str(close_date)[:10])
                close_date_in_past = parsed_close_date < date.today()
            except (TypeError, ValueError):
                parsed_close_date = None
        if parsed_close_date:
            timing = "known"
        elif is_recurring or status == "recurring":
            timing = "recurring"
        elif status in {"standby", "closed", "expired"}:
            timing = "status_documented"
        elif _NO_DEADLINE.search(blob):
            timing = "none_communicated"
        else:
            timing = "undetermined"

        # ---- Contradictions critiques → REVIEW_REQUIRED ----
        reasons: list[str] = []
        if any(looks_english_text(v) or _english_language(v) for v in (short_description, full_description) if v):
            reasons.append("english_content_remaining")
        if not _is_absolute_url(source_url):
            reasons.append("relative_source_url")
        raw_texts = (raw_title, str(device.get("short_description") or ""), str(device.get("full_description") or ""))
        if any(looks_mojibake(v) for v in raw_texts):
            reasons.append("encoding_corrupted")
        if status == "open" and close_date_in_past:
            reasons.append("open_with_past_close_date")
        if status == "recurring" and not (is_recurring or device.get("recurrence_notes")):
            reasons.append("recurring_without_evidence")
        if _SOURCE_UNAVAILABLE.search(blob):
            reasons.append("source_unavailable")
        contradictions = list(reasons)

        # ---- Score composite (informatif, aucun seuil de longueur) ----
        nature_ok = content_type in (ContentType.FINANCING_OPPORTUNITY, ContentType.NON_FINANCIAL_SUPPORT)
        score = (
            (20 if nature_ok and classification.confidence >= 0.6 else 10 if nature_ok else 0)
            + (15 if beneficiary else 0)
            + (25 if quantified else 15 if mechanism in ("program_budget", "instrument") else 0)
            + (20 if timing in ("known", "recurring", "status_documented") else 10 if timing == "none_communicated" else 0)
            + (10 if _is_absolute_url(source_url) else 0)
            + (10 if territory else 0)
        )
        criteria = {
            "nature": ct, "beneficiary": beneficiary, "mechanism": mechanism, "territory": territory,
            "timing": timing, "application_mechanism": classification.application_mechanism,
        }

        # ---- Aucune substance métier → INVALID (sauf contradiction récupérable) ----
        summary_informative = _informative_tokens(unidecode(short_description.lower())) >= 4
        if not contradictions and not beneficiary and mechanism == "none" and _informative_tokens(blob) < 6:
            return _decide("INVALID", ["no_business_substance"], score, ct, criteria)

        # ---- REVIEW_REQUIRED : critère bloquant non satisfait ----
        if content_type == ContentType.UNKNOWN:
            reasons.append("nature_undetermined")
        if not summary_informative:
            reasons.append("insufficient_summary_for_auto_publish")
        if not beneficiary and (non_financial or mechanism in ("none", "program_budget")):
            reasons.append("insufficient_business_proof")
        if timing == "undetermined":
            reasons.append("open_without_close_date")
        if reasons:
            return _decide("REVIEW_REQUIRED", reasons, score, ct, criteria)

        # ---- SUSPECT (publiable) vs VALID ----
        suspect: list[str] = []
        if non_financial:
            suspect.append("non_financial_support")
        elif mechanism == "program_budget":
            suspect.append("program_budget_only")
        elif mechanism != "quantified":
            suspect.append("no_beneficiary_amount")
        if timing == "none_communicated":
            suspect.append("no_deadline_communicated")
        recurrence_documented = timing == "recurring" and bool(_RECURRENCE_TEXT.search(blob))
        if not beneficiary and timing != "known" and not classification.application_mechanism and not recurrence_documented:
            suspect.append("not_actionable")
        if not territory:
            suspect.append("territory_unidentified")
        if classification.confidence < 0.60:
            suspect.append("nature_low_confidence")

        if suspect:
            return _decide("SUSPECT", [f"suspect:{r}" for r in suspect], score, ct, criteria)
        return _decide("VALID", reasons, score, ct, criteria)
