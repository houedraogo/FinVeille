"""
ContentClassifier — classifie la nature réelle d'un contenu avant publication.

La décision repose sur des familles d'indices génériques (FR/EN), pas sur des titres :
  - instrument financier (subvention, prêt, bourse, grant, prize…) ;
  - preuve chiffrée (montant, taux, budget) ;
  - appel ouvert : ce que le lecteur peut faire maintenant (candidater, date limite, apply…) ;
  - voix rétrospective (résultats, lauréats récompensés, signature, retour sur…) ;
  - acteur institutionnel + projet public, avec ou sans accès pour le secteur privé ;
  - accompagnement sans dotation explicite.

Un appel ouvert ou un accès explicite pour les bénéficiaires l'emporte sur une simple mention
(un événement qui « annonce » une subvention reste un événement ; un nouvel appel qui cite les
résultats précédents reste un financement).
"""
import re
from dataclasses import dataclass, field
from enum import Enum

from unidecode import unidecode

from app.services.amount_engine import AmountEngine
from app.utils.encoding_repair import repair_mojibake
from app.utils.text_utils import clean_editorial_text, looks_like_provider_call


class ContentType(str, Enum):
    FINANCING_OPPORTUNITY = "FINANCING_OPPORTUNITY"
    NON_FINANCIAL_SUPPORT = "NON_FINANCIAL_SUPPORT"
    EVENT = "EVENT"
    NEWS = "NEWS"
    RESULT_ANNOUNCEMENT = "RESULT_ANNOUNCEMENT"
    PUBLIC_PROCUREMENT = "PUBLIC_PROCUREMENT"
    INSTITUTIONAL_PROJECT = "INSTITUTIONAL_PROJECT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ContentClassification:
    content_type: ContentType
    confidence: float  # 0.0–1.0
    signals: list[str] = field(default_factory=list)
    financial_mechanism: bool = False    # instrument, montant, taux ou budget identifiable
    application_mechanism: bool = False  # le lecteur peut candidater / une échéance est donnée
    private_access_denied: bool = False  # la source exclut explicitement le secteur privé / les ONG


def _rx(*alternatives: str) -> "re.Pattern[str]":
    return re.compile(r"(?<![a-z])(?:" + "|".join(alternatives) + r")(?![a-z])")


# Instrument précis remis au bénéficiaire.
_INSTRUMENT_SPECIFIC = _rx(
    r"subventions?", r"grants?", r"bourses?", r"scholarships?", r"fellowships?", r"prets?", r"loans?",
    r"equity", r"venture capital", r"venture debt", r"capital[- ]risque", r"dotations?", r"prix", r"prizes?", r"awards?",
    r"cash transfers?", r"transferts? monetaires?", r"avances? remboursables?", r"garanties?", r"guarantees?", r"cautions?",
    r"credits?", r"tax credits?", r"exonerations?", r"abattements?", r"cheques?", r"vouchers?", r"micro-?credits?",
    r"aides? financieres?", r"financial (?:aid|support|assistance)",
)
# Termes génériques : simple mention (« accès au financement ») tant qu'aucun verbe d'offre ne les porte.
_INSTRUMENT_GENERIC = _rx(r"financements?", r"financing", r"funding", r"investissements?", r"investment")
_OFFER_INSTRUMENT = re.compile(
    r"(?<![a-z])(?:propos\w+|offre\w*|offer\w*|accord\w+|octroi\w+|fournit|fournissent|provid\w+|attribu\w+|verse\w*)"
    r"[^.]{0,60}?(?<![a-z])(?:credits?|prets?|subventions?|financements?|bourses?|garanties?|cautions?|loans?|grants?|"
    r"funding|financing|investissements?|equity|prix|prizes?)(?![a-z])"
)
_WEAK_AID = _rx(r"aides?", r"soutiens?", r"support", r"programme", r"programmes", r"program", r"dispositif")

# Le lecteur peut agir maintenant : ce n'est pas la simple mention d'un appel passé.
_OPEN_CALL = _rx(
    r"apply (?:before|by|via|now|anytime|online|at|until|for)", r"applications? (?:are |is )?(?:open|invited|accepted|being accepted)",
    r"applications? (?:process|deadline|form|link|period)", r"direct applications?", r"submit (?:your|an?|the) ",
    r"rolling (?:submissions?|basis|applications?)", r"candidatez", r"candidatures? (?:ouvertes?|jusqu)",
    r"deposer (?:votre|un|une|le|la) (?:dossier|candidature|projet)", r"deposez", r"dossier de candidature",
    r"depot (?:des|de) (?:candidatures?|dossiers?)", r"depot avant", r"date limite[^.]{0,30}?\d", r"deadline[^.]{0,30}?\d",
    r"nouvel appel", r"new call", r"call is open", r"appel (?:est )?ouvert", r"ouvert(?:e|es|s)? (?:en continu|toute l'annee|jusqu)",
    r"en continu", r"au fil de l'eau", r"open to (?:ngos?|smes?|startups?|entrepreneurs|applicants)",
)
_CALL_NOUN = _rx(r"appels? a projets?", r"appels? a candidatures?", r"call for (?:proposals?|applications?)")
_APPLY_ANYTIME = _rx(r"apply anytime", r"application process ongoing", r"rolling", r"en continu", r"au fil de l'eau")

_RESULT = _rx(
    r"resultats? (?:du|de la|de l'|des|of|de)", r"results? of", r"laureats?", r"laureates?", r"gagnants?", r"winners?",
    r"vainqueurs?", r"selectionnes?", r"selectionnees?", r"(?:have|were|has been|ont ete) selected", r"palmares",
    r"remise des prix", r"ceremonie de remise", r"recompenses?", r"felicitations", r"congratulations",
    r"les projets retenus", r"projets selectionnes", r"awardees?", r"retour sur",
)
_RESULT_TITLE = _rx(r"resultats?", r"results?", r"laureats?", r"winners?", r"palmares", r"remise des prix")

_NEWS = _rx(
    r"a signe", r"ont signe", r"signature de", r"annonce (?:la|le|l'|son|sa|ses|les)", r"announces?", r"announced",
    r"partenariat", r"partnership", r"convention", r"communique de presse", r"press release",
    r"nous avons le plaisir", r"nous sommes heureux", r"vient de (?:lancer|signer|publier|annoncer)",
    r"inaugur\w+", r"interview", r"portrait", r"bilan(?: annuel)?", r"rapport annuel", r"permettra",
)

# Voix de communiqué : sans l'un de ces marqueurs, « partenariat » ou « convention » n'établissent pas une actualité.
_NEWS_STRONG = _rx(
    r"a signe", r"ont signe", r"signature de", r"communique de presse", r"press release",
    r"nous avons le plaisir", r"nous sommes heureux", r"vient de (?:lancer|signer|publier|annoncer)", r"annonce la signature",
    r"inaugur\w+",
)

_EVENT_TITLE = _rx(
    r"atelier", r"workshop", r"seminaires?", r"seminars?", r"conferences?", r"forums?", r"salons?", r"webinaires?",
    r"webinars?", r"journees?", r"reunions?", r"rencontres?", r"hackathons?", r"bootcamps?", r"ceremonies?",
    r"masterclass", r"meetup", r"summit", r"sommet", r"formations?",
)
_EVENT_BODY = _rx(
    r"inscriptions? gratuites?", r"s'inscrire", r"register (?:now|here|online)", r"free registration", r"places? disponibles?",
    r"programme de la journee", r"programme du forum", r"intervenants?", r"speakers?", r"panelistes?",
    r"en presentiel", r"en distanciel", r"organise par", r"nos partenaires vous invitent", r"lieu ?:", r"venue",
)

# A call that is open now, described in the present tense or as an edition being launched. It takes priority over
# the narration of past laureates on the same page. Future / "next" calls are excluded (see _FUTURE_GUARD).
_ACTIVE_CALL = re.compile(
    r"(?<![a-z])(?:lance(?:nt)?|ouvre(?:nt)?|launch(?:es|ed|ing)?|opens?|est\s+ouvert\w*|sont\s+ouvert\w*|is\s+open|are\s+open|now\s+open)"
    r"(?![a-z])[^.]{0,70}?(?:appels?\s+a|call\s+for|candidatures?|applications?)"
    r"|appels?\s+a\s+(?:candidatures?|projets?)[^.]{0,120}?(?:porte(?:nt)?\s+sur|vise(?:nt)?|s'adresse|est\s+destine|destine\w*\s+aux|concerne|cible)"
    r"|cette\s+annee[^.]{0,40}?appel"
    r"|(?:deuxieme|troisieme|quatrieme|nouvelle|\d+(?:e|eme))\s+edition[^.]{0,80}?(?:appel|candidature)"
    r"|appels?\s+a\s+candidatures?\s*(?::|-)"
)
_FUTURE_GUARD = re.compile(r"prochain\w*|next|sera|seront|will|bientot|soon|prochainement|ulterieur\w*|future?s?")


def _has_active_call(text: str) -> bool:
    for m in _ACTIVE_CALL.finditer(text):
        if not _FUTURE_GUARD.search(text[max(0, m.start() - 30): m.end()]):
            return True
    return False


_PROCUREMENT_STRONG = _rx(r"appels? d'offres?", r"appels? d offres?", r"avis de marche", r"tender notice", r"invitation to tender", r"request for quotations?", r"dossier de consultation", r"dce", r"rcai", r"mapa", r"procedure ouverte")
_PROCUREMENT_WEAK = _rx(r"marches? publics?", r"consultation", r"acheteur public", r"tender", r"procurement")

_INSTITUTION_ACTOR = _rx(
    r"banque mondiale", r"world bank", r"ida", r"ibrd", r"banque africaine de developpement", r"african development bank",
    r"afdb", r"afd", r"agence francaise de developpement", r"imf", r"fmi", r"fonds monetaire",
    r"banque europeenne d'investissement", r"european investment bank", r"eib", r"bei", r"undp", r"pnud",
    r"asian development bank", r"islamic development bank",
)
_GOVERNMENT_PROJECT = _rx(
    r"government of", r"gouvernement (?:du|de la|de l'|des)", r"republic of", r"republique (?:du|de|des)",
    r"ministry of", r"ministere (?:de|du|des|d')", r"implementing agency", r"agence d'execution",
    r"project (?:approved|duration|closing|appraisal)", r"financing agreement", r"accord de (?:pret|financement)",
    r"loan to the government", r"pret (?:a|au) (?:gouvernement|l'etat)", r"pret souverain", r"souverain",
    r"decaissements?", r"projet institutionnel", r"programme gouvernemental",
)
_PROJECT_NOUN = _rx(r"projects?", r"projets?")
_PRIVATE_ACCESS_DENIED = re.compile(
    r"(?:not (?:accessible|open|available) to|non accessible (?:au|aux|a)|n'est pas accessible|pas accessible|reserve(?:e)? (?:au|aux|a l')|reserved for)"
    r"[^.]{0,40}?(?:private sector|ngos?|enterprises|entreprises|smes?|pme|secteur prive|prive|governments?|etat|gouvernement)"
)
# Qui peut prétendre à l'aide. Partagé avec le Quality Gate.
BENEFICIARY_RE = _rx(
    r"pme", r"tpe", r"eti", r"smes?", r"entreprises?", r"startups?", r"start-ups?", r"createurs?", r"repreneurs?",
    r"porteurs?", r"entrepreneurs?", r"collectivites?", r"communes?", r"associations?", r"ong", r"ngos?",
    r"cooperatives?", r"agriculteurs?", r"producteurs?", r"chercheurs?", r"researchers?", r"etudiants?", r"doctorants?",
    r"students?", r"jeunes", r"femmes", r"women", r"youth", r"households?", r"menages?", r"institutions?",
    r"universites?", r"universities", r"hebergeurs?", r"artisans?", r"commercants?", r"social enterprises",
    r"organisations?", r"organizations?", r"grantees?", r"applicants?", r"beneficiaires?", r"founders?",
    r"fondateurs?", r"exploitants?", r"etablissements?", r"laboratoires?", r"hopitaux", r"ecoles?",
)

_SUPPORT_SERVICE = _rx(
    r"accompagnement", r"diagnostics?", r"conseil", r"coaching", r"mentorat", r"mentoring", r"incubation",
    r"acceleration", r"mise en (?:relation|reseau)", r"networking", r"expertise", r"technical assistance",
    r"assistance technique", r"audit", r"bilan de maturite", r"prestations?", r"formation",
)
# Le marqueur doit affirmer que l'offre elle-même est non financière (pas « avantages non financiers à confirmer »).
_NON_FINANCIAL_ASSERTION = (
    r"(?:appui|aide|soutien|accompagnement|avantage principal|offre)(?: principa(?:l|le|ux))?(?: est| reste)?"
    r"(?: surtout| principalement| essentiellement| uniquement)? non[- ]financ\w+"
    r"|(?:est|sont) non[- ]financ\w+|non-financial (?:support|only)"
)
_NO_CASH_EXPLICIT = re.compile(
    r"pas de financement(?: direct)?|sans financement|aucun financement|no (?:direct )?(?:funding|financing|financial)|"
    r"accompagnement uniquement|uniquement (?:un )?accompagnement|sans dotation|" + _NON_FINANCIAL_ASSERTION
)
_NO_CASH = re.compile(
    r"pas de financement(?: direct)?|sans financement|aucun financement|no (?:direct )?(?:funding|financing|financial)|"
    r"accompagnement uniquement|uniquement (?:un )?accompagnement|sans dotation|gratuit(?:e|es|s)?|free of charge|" + _NON_FINANCIAL_ASSERTION
)

# Page vide ou inaccessible : la nature du contenu est indéterminable.
UNUSABLE_SOURCE_MARKERS = (
    "aucun contenu exploitable trouve",
    "aucun contenu editorial exploitable",
    "javascript dynamique",
    "structure html trop pauvre",
    "token invalide ou expire",
    "impossible d'acceder a l'url",
    "url non publique",
    "page non publique",
    "activation deconseillee",
)

_FINANCING_DEVICE_TYPES = {
    "subvention", "pret", "avance_remboursable", "garantie", "credit_impot", "exoneration", "aap", "ami",
    "investissement", "concours", "bourse", "equity", "aap_sans_financement",
}


def _n(text: str) -> str:
    return unidecode(repair_mojibake(clean_editorial_text(text or "")).lower())


def _count(rx: "re.Pattern[str]", text: str) -> int:
    return len(rx.findall(text))


class ContentClassifier:
    """Distingue une opportunité de financement d'un événement, d'une actualité, de résultats ou d'un projet institutionnel."""

    def classify(self, device: dict) -> ContentClassification:
        title = _n(device.get("title") or "")
        body = " ".join(
            _n(device.get(k) or "") for k in ("short_description", "full_description", "funding_details", "eligibility_criteria", "source_raw")
        )
        blob = f"{title} {body}"
        device_type = str(device.get("device_type") or "").lower()
        signals: list[str] = []

        if any(marker in blob for marker in UNUSABLE_SOURCE_MARKERS):
            return ContentClassification(ContentType.UNKNOWN, 0.20, ["unusable_source"])

        amounts = AmountEngine().extract(blob, country=str(device.get("country") or ""))
        beneficiary_amount = any(
            v is not None for v in (amounts.amount_min, amounts.amount_max, amounts.funding_rate, amounts.eligible_expense_cap)
        )
        has_amount = beneficiary_amount or amounts.program_budget is not None
        offered = _OFFER_INSTRUMENT.search(blob) is not None
        instrument = _count(_INSTRUMENT_SPECIFIC, blob) > 0 or device_type in _FINANCING_DEVICE_TYPES or offered
        open_call = _count(_OPEN_CALL, blob) > 0 or _has_active_call(blob)
        mechanism = instrument or has_amount
        if has_amount:
            signals.append("amount_evidence")
        if instrument:
            signals.append("instrument")
        if open_call:
            signals.append("open_call")

        def result(kind: ContentType, confidence: float, **flags) -> ContentClassification:
            return ContentClassification(
                kind, round(min(confidence, 0.95), 2), signals,
                financial_mechanism=flags.get("mechanism", mechanism),
                application_mechanism=open_call,
                private_access_denied=flags.get("denied", False),
            )

        # ---- Marché public ----
        strong, weak = _count(_PROCUREMENT_STRONG, blob), _count(_PROCUREMENT_WEAK, blob)
        if strong >= 1 and strong + weak >= 2:
            signals.append("procurement")
            return result(ContentType.PUBLIC_PROCUREMENT, 0.85)

        # ---- Appel adressé à des experts / prestataires : un marché de prestation, pas un financement pour le candidat ----
        if looks_like_provider_call(blob) and not offered and not beneficiary_amount:
            signals.append("provider_selection")
            return result(ContentType.PUBLIC_PROCUREMENT, 0.80, mechanism=False)

        # ---- Projet institutionnel : acteur multilatéral + projet public, sans accès direct pour les bénéficiaires ----
        actor, gov, project = (_count(_INSTITUTION_ACTOR, blob) > 0, _count(_GOVERNMENT_PROJECT, blob) > 0, _count(_PROJECT_NOUN, blob) > 0)
        denied = bool(_PRIVATE_ACCESS_DENIED.search(blob))
        if actor and (gov or denied) and project:
            if denied:
                signals.append("institutional:private_access_denied")
                return result(ContentType.INSTITUTIONAL_PROJECT, 0.90, denied=True)
            if not open_call:
                signals.append("institutional")
                return result(ContentType.INSTITUTIONAL_PROJECT, 0.80)

        # Type fourni par la source : opération d'une institution multilatérale sans candidature possible.
        if device_type == "institutional_project":
            signals.append("institutional:device_type")
            return result(ContentType.INSTITUTIONAL_PROJECT, 0.80)

        # ---- Résultats : voix rétrospective, aucun appel ouvert ----
        # Narration of results must dominate the page: in its title or its opening, not buried in a long programme page.
        result_hits = _count(_RESULT, blob)
        head_hits = _count(_RESULT, f"{title} {body[:1500]}")
        title_is_result = _count(_RESULT_TITLE, title) > 0
        long_programme_page = len(body) > 3000 and instrument and not title_is_result
        if not open_call and not long_programme_page and (
            (result_hits >= 3 and head_hits >= 2) or (result_hits >= 2 and title_is_result) or (head_hits >= 2 and not instrument)
        ):
            signals.append(f"result:{result_hits}")
            return result(ContentType.RESULT_ANNOUNCEMENT, 0.80)

        news_hits = _count(_NEWS, blob)
        event_title, event_body = _count(_EVENT_TITLE, title), _count(_EVENT_BODY, blob)
        event_score = event_title * 2 + event_body
        signals.append(f"news_hits:{news_hits}")
        signals.append(f"event_score:{event_score}")

        # ---- Événement : inscription, intervenants… sans appel ouvert ----
        if not open_call and event_score >= 3:
            return result(ContentType.EVENT, 0.6 + min(event_score, 6) * 0.05)

        # ---- Actualité : voix de communiqué, ni appel ouvert ni preuve chiffrée ----
        if not open_call and not beneficiary_amount and not instrument and news_hits >= 2 and _count(_NEWS_STRONG, blob) >= 1:
            return result(ContentType.NEWS, 0.6 + min(news_hits, 6) * 0.05)

        # ---- Accompagnement sans dotation explicite ----
        support = _count(_SUPPORT_SERVICE, blob)
        no_cash = bool(_NO_CASH.search(blob))
        explicit_no_cash = bool(_NO_CASH_EXPLICIT.search(blob))
        if (explicit_no_cash or (support >= 1 and no_cash)) and not has_amount and not offered:
            signals.append("no_cash_marker")
            return result(ContentType.NON_FINANCIAL_SUPPORT, 0.80, mechanism=False)

        # ---- Financement : instrument + (montant | appel ouvert | bénéficiaire) ----
        beneficiary = _count(BENEFICIARY_RE, blob) > 0
        if (instrument or beneficiary_amount) and (beneficiary_amount or open_call or beneficiary):
            return result(
                ContentType.FINANCING_OPPORTUNITY,
                0.70 + (0.10 if beneficiary_amount else 0) + (0.10 if open_call else 0),
                mechanism=True,
            )

        # Programme doté d'un budget global pour des bénéficiaires nommés : programme de financement (budget seul connu).
        if amounts.program_budget is not None and beneficiary and not open_call:
            signals.append("program_budget_for_beneficiaries")
            return result(ContentType.FINANCING_OPPORTUNITY, 0.60, mechanism=True)

        # « Appel à projets » qui évoque un financement sans en préciser le mécanisme : à vérifier.
        if _CALL_NOUN.search(blob) and _count(_INSTRUMENT_GENERIC, blob) > 0:
            signals.append("financial_mechanism_unverified")
            return result(ContentType.FINANCING_OPPORTUNITY, 0.50, mechanism=False)

        # Le titre nomme l'instrument proposé (« Prêt … », « Bourse … ») sans voix d'événement, de résultat ou d'actualité.
        if _count(_INSTRUMENT_SPECIFIC, title) > 0 or _count(_INSTRUMENT_GENERIC, title) > 0:
            return result(ContentType.FINANCING_OPPORTUNITY, 0.55, mechanism=True)

        # Appel ouvert sur un programme, sans instrument explicite : opportunité dont le mécanisme reste à vérifier.
        if open_call and (_count(_WEAK_AID, blob) > 0 or _APPLY_ANYTIME.search(blob)):
            signals.append("financial_mechanism_unverified")
            return result(ContentType.FINANCING_OPPORTUNITY, 0.50, mechanism=False)

        # Intitulé de type « Aide … » : dispositif d'aide, contenu insuffisant pour aller plus loin.
        if re.search(r"(?<![a-z])aides?(?![a-z])", title) or re.search(r"(?<![a-z])aides? (?:aux|au|a la|a l')", body):
            signals.append("financial_mechanism_unverified")
            return result(ContentType.FINANCING_OPPORTUNITY, 0.45, mechanism=False)

        # Accompagnement pur : services sans instrument, sans montant, sans appel ouvert.
        if support >= 1 and not instrument and not beneficiary_amount and not open_call:
            signals.append("support_without_instrument")
            return result(ContentType.NON_FINANCIAL_SUPPORT, 0.60, mechanism=False)

        return result(ContentType.UNKNOWN, 0.30, mechanism=False)
