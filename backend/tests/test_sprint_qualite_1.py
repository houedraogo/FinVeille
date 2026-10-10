"""
Tests Sprint Qualité 1.

Couvre :
  - ContentClassifier (classification de contenu)
  - AmountEngine (extraction montants / programme budget)
  - DeviceQualityGate (4 états : VALID / SUSPECT / REVIEW_REQUIRED / INVALID)
  - Pipeline URL reconstruction
  - GSO prefix fix dans le normalizer
  - Golden dataset : précision avant/après
"""
import pytest

from app.services.content_classifier import ContentClassifier, ContentType
from app.services.amount_engine import AmountEngine, AmountType, parse_money
from app.services.device_quality import DeviceQualityGate


# ── Helpers ────────────────────────────────────────────────────────────────

def make_device(**overrides):
    base = {
        "title": "Aide à l'innovation",
        "source_url": "https://example.org/aide",
        "short_description": (
            "Programme de soutien financier aux PME innovantes désireuses de développer "
            "un projet de R&D en France, avec un accompagnement personnalisé."
        ),
        "full_description": (
            "Description longue avec plusieurs informations structurées sur le dispositif, "
            "ses objectifs, ses modalités, le contexte et la façon dont il peut être mobilisé "
            "par les bénéficiaires. Le programme couvre les dépenses de personnel, de sous-traitance "
            "et d'équipement directement liées au projet de R&D."
        ),
        "eligibility_criteria": (
            "PME immatriculée en France avec projet innovant éligible, situation régulière, "
            "dossier complet et activité conforme aux critères du programme."
        ),
        "funding_details": "Subvention jusqu'à 30 000 EUR. Montant à confirmer selon le projet.",
        "amount_max": 30000,
        "close_date": "2027-06-30",
        "status": "open",
        "is_recurring": False,
    }
    base.update(overrides)
    return base


# ════════════════════════════════════════════════════════════════════════════
# I. CONTENT CLASSIFIER
# ════════════════════════════════════════════════════════════════════════════

class TestContentClassifier:
    def setup_method(self):
        self.classifier = ContentClassifier()

    def test_event_workshop_no_financing(self):
        """Un atelier sans signal de financement est classé EVENT."""
        device = make_device(
            title="Atelier de formation PME Abidjan mars 2025",
            short_description=(
                "Le CIPME organise un atelier de formation destiné aux PME ivoiriennes. "
                "Inscription gratuite, 50 places disponibles. Date : 14 mars 2025."
            ),
            full_description=(
                "Programme de la journée : accueil, présentation, sessions intervenants. "
                "Organisé par le CIPME au Centre des Conférences d'Abidjan. "
                "En présentiel. Intervenants experts du financement."
            ),
            funding_details="",
            eligibility_criteria="",
            close_date=None,
        )
        result = self.classifier.classify(device)
        assert result.content_type == ContentType.EVENT, (
            f"Expected EVENT, got {result.content_type}, signals: {result.signals}"
        )
        assert result.confidence >= 0.60

    def test_french_news_announcement(self):
        """Une actualité institutionnelle en français est classée NEWS."""
        device = make_device(
            title="Signature de convention CIPME-BNI 2025",
            short_description=(
                "Le CIPME et la BNI ont signé une convention de partenariat stratégique "
                "pour faciliter l'accès au financement des PME."
            ),
            full_description=(
                "Le CIPME annonce la signature d'une convention avec la BNI. "
                "Communiqué de presse. Nous sommes heureux de cette collaboration."
            ),
            funding_details="",
            eligibility_criteria="",
            close_date=None,
        )
        result = self.classifier.classify(device)
        assert result.content_type == ContentType.NEWS, (
            f"Expected NEWS, got {result.content_type}, signals: {result.signals}"
        )

    def test_event_containing_financing_word_is_not_misclassified(self):
        """Un événement mentionnant 'financement' reste EVENT si pas de candidature."""
        device = make_device(
            title="Forum sur le financement des PME africaines",
            short_description=(
                "Forum organisé pour discuter des enjeux du financement des PME. "
                "Inscription gratuite. Intervenants de la finance et des institutions."
            ),
            full_description=(
                "Programme du forum : tables rondes sur l'accès au financement, "
                "présentations des acteurs du secteur. En présentiel à Abidjan. "
                "Organisé par la Chambre de Commerce. Journée de conférences."
            ),
            funding_details="",
            eligibility_criteria="",
            close_date=None,
        )
        result = self.classifier.classify(device)
        # Le mot "financement" seul ne suffit pas à classifier FINANCING_OPPORTUNITY
        assert result.content_type in (ContentType.EVENT, ContentType.UNKNOWN), (
            f"Should not be FINANCING_OPPORTUNITY, got {result.content_type}"
        )

    def test_genuine_subvention_with_event_mention(self):
        """Une vraie subvention qui mentionne un événement reste FINANCING_OPPORTUNITY."""
        device = make_device(
            title="Appel à projets innovation numérique — ADEME",
            short_description=(
                "Subvention jusqu'à 150 000 EUR pour les entreprises innovantes dans le numérique. "
                "Présentation du dispositif lors du forum numérique de Paris. Dépôt avant le 30 juin 2027."
            ),
            full_description=(
                "Cet appel à projets financé par l'ADEME vise à soutenir les solutions numériques "
                "à impact environnemental. Les projets sélectionnés recevront une subvention directe. "
                "Dossier de candidature à déposer en ligne avant le 30 juin 2027. "
                "Critères d'éligibilité : PME ou startup française, projet en phase pilote ou R&D. "
                "Un accompagnement technique est proposé aux lauréats tout au long du projet."
            ),
            funding_details="Subvention jusqu'à 150 000 EUR, taux de financement 60 % des dépenses éligibles.",
            eligibility_criteria="PME ou startup immatriculée en France, projet innovant en phase pilote, dossier complet.",
            close_date="2027-06-30",
        )
        result = self.classifier.classify(device)
        assert result.content_type == ContentType.FINANCING_OPPORTUNITY, (
            f"Expected FINANCING_OPPORTUNITY, got {result.content_type}"
        )

    def test_result_announcement_laureats(self):
        """Une annonce de lauréats est classée RESULT_ANNOUNCEMENT."""
        device = make_device(
            title="Résultats du programme d'appui aux PME 2024 — CIPME",
            short_description=(
                "Le CIPME annonce les résultats de son programme : 142 entreprises sélectionnées. "
                "Félicitations aux lauréats ! Palmarès complet disponible."
            ),
            full_description=(
                "Les projets retenus ont été sélectionnés parmi 400 candidatures. "
                "Palmarès complet : voir liste jointe. Cérémonie de remise des prix prévue."
            ),
            funding_details="",
            eligibility_criteria="",
            close_date=None,
        )
        result = self.classifier.classify(device)
        assert result.content_type == ContentType.RESULT_ANNOUNCEMENT, (
            f"Expected RESULT_ANNOUNCEMENT, got {result.content_type}"
        )

    def test_non_financial_diagnostic(self):
        """Un diagnostic gratuit est classé NON_FINANCIAL_SUPPORT."""
        device = make_device(
            title="Diagnostic numérique TPE — Bpifrance",
            short_description=(
                "Bilan de maturité numérique de votre entreprise par un expert Bpifrance. "
                "Prestation de conseil gratuit, pas de financement direct."
            ),
            full_description=(
                "Le diagnostic numérique est une prestation de conseil financée à 100 % par Bpifrance. "
                "Accompagnement non financier. Conseil gratuit. "
                "Aucun financement direct n'est accordé dans le cadre de ce dispositif."
            ),
            funding_details="Prestation gratuite — accompagnement uniquement, sans financement direct.",
            eligibility_criteria="TPE de moins de 10 salariés, tous secteurs.",
        )
        result = self.classifier.classify(device)
        assert result.content_type in (ContentType.NON_FINANCIAL_SUPPORT, ContentType.FINANCING_OPPORTUNITY), (
            f"Got {result.content_type}"
        )
        # Non-financial: should not be EVENT or NEWS
        assert result.content_type not in (ContentType.EVENT, ContentType.NEWS)

    def test_institutional_project_world_bank_loan(self):
        """Un prêt souverain Banque Mondiale est classé INSTITUTIONAL_PROJECT."""
        device = make_device(
            title="Projet réhabilitation routes nationales — Cameroun (Banque Mondiale)",
            short_description=(
                "Prêt souverain de 300 millions USD de la Banque Mondiale au Gouvernement du Cameroun. "
                "Opération de financement institutionnel non accessible au secteur privé."
            ),
            full_description=(
                "Ce projet institutionnel finance la réhabilitation de 500 km de routes nationales. "
                "Accord de prêt entre la Banque Mondiale et l'État camerounais. "
                "Budget de l'État. Programme gouvernemental d'infrastructure."
            ),
            funding_details="Prêt souverain — non accessible aux entreprises ou ONG.",
            eligibility_criteria="Agence d'exécution : Ministère des Travaux Publics.",
        )
        result = self.classifier.classify(device)
        assert result.content_type == ContentType.INSTITUTIONAL_PROJECT, (
            f"Expected INSTITUTIONAL_PROJECT, got {result.content_type}"
        )


# ════════════════════════════════════════════════════════════════════════════
# II. AMOUNT ENGINE
# ════════════════════════════════════════════════════════════════════════════

class TestAmountEngine:
    def setup_method(self):
        self.engine = AmountEngine()

    def test_beneficiary_amount_max_euros(self):
        text = "Subvention jusqu'à 30 000 EUR pour les PME françaises."
        result = self.engine.extract(text, country="France")
        assert result.amount_max == 30_000
        assert result.currency == "EUR"
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT
        assert result.program_budget is None

    def test_xof_amount_extracted(self):
        text = "Financement jusqu'à 50 000 000 XOF par projet sélectionné."
        result = self.engine.extract(text, country="Côte d'Ivoire")
        assert result.amount_max == 50_000_000
        assert result.currency == "XOF"
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT

    def test_usd_amount_extracted(self):
        text = "Grant up to USD 7 500 per researcher."
        result = self.engine.extract(text, country="International")
        assert result.amount_max == 7_500
        assert result.currency == "USD"
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT

    def test_range_min_max(self):
        text = "Prêt de 50 000 à 200 000 EUR pour les PME et ETI industrielles."
        result = self.engine.extract(text, country="France")
        assert result.amount_min == 50_000
        assert result.amount_max == 200_000
        assert result.amount_type == AmountType.RANGE

    def test_program_budget_not_in_amount_max(self):
        """Budget programme de 50M EUR ne doit pas contaminer amount_max."""
        text = (
            "Programme doté d'un budget global de 50 millions EUR. "
            "Chaque projet peut recevoir jusqu'à 100 000 EUR."
        )
        result = self.engine.extract(text, country="France")
        assert result.program_budget == 50_000_000, f"Expected 50M program_budget, got {result.program_budget}"
        assert result.amount_max == 100_000, f"Expected 100k amount_max, got {result.amount_max}"
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT

    def test_large_number_alone_is_program_budget(self):
        """Un seul grand nombre sans contexte bénéficiaire → program_budget."""
        text = "Ce programme dispose d'un budget de 200 millions EUR pour financer l'innovation."
        result = self.engine.extract(text, country="France")
        assert result.program_budget == 200_000_000
        assert result.amount_max is None
        assert result.amount_type == AmountType.PROGRAM_BUDGET

    def test_funding_rate_extraction(self):
        text = "Taux de financement à hauteur de 70 % des dépenses éligibles."
        result = self.engine.extract(text, country="France")
        # funding_rate est en pourcentage (70 = 70 %), comme devices.funding_rate (Numeric(5,2))
        assert result.funding_rate == 70.0

    def test_no_amount_returns_unknown(self):
        text = "Aide aux PME dans le secteur numérique. Contacter l'antenne régionale."
        result = self.engine.extract(text, country="France")
        assert result.amount_max is None
        assert result.amount_min is None
        assert result.program_budget is None
        assert result.amount_type == AmountType.UNKNOWN
        assert result.amount_confidence == 0.0

    def test_country_default_currency_is_inferred_never_sourced(self):
        """SQ1.2 R9: sans devise écrite dans la source, la devise du pays reste une déduction interne."""
        text = "Aide aux PME ivoiriennes. Montant max 10 000 000."
        result = self.engine.extract(text, country="Côte d'Ivoire")
        assert result.currency is None
        assert result.currency_inferred == "XOF"
        assert result.amount_max == 10_000_000

    def test_percentage_without_absolute_amount(self):
        text = "Financement couvert à 80 % des coûts du projet."
        result = self.engine.extract(text, country="France")
        assert result.funding_rate is not None
        assert result.amount_type == AmountType.RATE_ONLY
        assert result.amount_max is None


MONEY_FORMATS = [
    ("$50,000", 50_000, "USD"),
    ("$50k", 50_000, "USD"),
    ("USD 50,000", 50_000, "USD"),
    ("50,000 USD", 50_000, "USD"),
    ("50000USD", 50_000, "USD"),
    ("50k USD", 50_000, "USD"),
    ("50K USD", 50_000, "USD"),
    ("1.5M USD", 1_500_000, "USD"),
    ("1,5 million USD", 1_500_000, "USD"),
    ("500 000 FCFA", 500_000, "XOF"),
    ("500000XOF", 500_000, "XOF"),
    ("2 milliards de FCFA", 2_000_000_000, "XOF"),
    ("€200k", 200_000, "EUR"),
    ("200K€", 200_000, "EUR"),
    ("2,5 M€", 2_500_000, "EUR"),
    ("50 millions d'euros", 50_000_000, "EUR"),
    ("30 000 EUR", 30_000, "EUR"),
    ("30 000 €", 30_000, "EUR"),
    ("30000 euros", 30_000, "EUR"),
    ("1 500 000 EUR", 1_500_000, "EUR"),
    ("1.500.000 EUR", 1_500_000, "EUR"),
]


class TestAmountEngineCurrencyFormats:
    """C1 — symbole/code avant ou après, avec ou sans espace, avec multiplicateurs."""

    @pytest.mark.parametrize("text,value,currency", MONEY_FORMATS)
    def test_money_token_is_parsed(self, text, value, currency):
        assert parse_money(text) == [(value, currency)]

    @pytest.mark.parametrize("text,value,currency", MONEY_FORMATS)
    def test_engine_extracts_beneficiary_amount_in_any_format(self, text, value, currency):
        result = AmountEngine().extract(f"Subvention jusqu'à {text} par projet.", country="France")
        assert result.amount_max == value
        assert result.currency == currency
        assert result.program_budget is None
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT

    def test_mis_decoded_euro_sign_is_repaired(self):
        """'€' encodé en UTF-8 puis décodé en cp1252 ('â‚¬') est réparé avant extraction."""
        text = "Aide Ã  la PME. Subvention jusqu'Ã  50 000 â‚¬ par projet."
        result = AmountEngine().extract(text, country="France")
        assert result.amount_max == 50_000
        assert result.currency == "EUR"

    def test_year_and_quantities_are_not_money(self):
        assert parse_money("Édition 2026, 50 000 ménages, 5 ans, 20 % des coûts") == []


class TestAmountEngineProgramBudget:
    """C2 — le budget global est reconnu par son contexte lexical, pas par un seuil."""

    @pytest.mark.parametrize("text", [
        "Le programme dispose d'une enveloppe globale de 50 millions EUR.",
        "Budget total : 50 millions EUR.",
        "Programme doté de 50 millions EUR pour la période.",
        "Le budget global du programme est de 50 millions EUR.",
        "Overall budget of EUR 50 million for the programme.",
        "Total programme funding: 50 million EUR.",
    ])
    def test_global_envelope_is_program_budget_not_amount_max(self, text):
        result = AmountEngine().extract(text, country="France")
        assert result.program_budget == 50_000_000
        assert result.amount_max is None
        assert result.amount_min is None
        assert result.amount_type == AmountType.PROGRAM_BUDGET

    def test_per_beneficiary_amount_is_amount_max(self):
        result = AmountEngine().extract(
            "Chaque bénéficiaire peut recevoir jusqu'à 50 millions XOF.", country="Côte d'Ivoire"
        )
        assert result.amount_max == 50_000_000
        assert result.currency == "XOF"
        assert result.program_budget is None
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT

    def test_explicit_beneficiary_context_beats_size_threshold(self):
        """20 M EUR dépasse le seuil de taille, mais le contexte 'jusqu'à … par projet' l'emporte."""
        result = AmountEngine().extract("Financement jusqu'à 20 millions EUR par projet.", country="France")
        assert result.amount_max == 20_000_000
        assert result.program_budget is None

    def test_both_amounts_are_separated(self):
        result = AmountEngine().extract(
            "Enveloppe globale de 50 millions EUR. Chaque projet reçoit au maximum 2 millions EUR.",
            country="France",
        )
        assert result.program_budget == 50_000_000
        assert result.amount_max == 2_000_000
        assert result.amount_type == AmountType.BENEFICIARY_AMOUNT


class TestAmountEngineFundingRate:
    """C3 — un pourcentage seul est un taux, jamais un montant."""

    def test_rate_alone_sets_no_amount(self):
        result = AmountEngine().extract("Aide jusqu'à 70 % des dépenses éligibles.", country="France")
        assert result.funding_rate == 70.0
        assert result.amount_min is None
        assert result.amount_max is None
        assert result.amount_type == AmountType.RATE_ONLY

    def test_rate_and_ceiling_are_both_extracted(self):
        result = AmountEngine().extract(
            "Subvention de 70 % des dépenses, dans la limite de 100 000 €.", country="France"
        )
        assert result.funding_rate == 70.0
        assert result.amount_max == 100_000
        assert result.currency == "EUR"
        assert result.amount_min is None

    def test_decimal_rate(self):
        result = AmountEngine().extract("Prise en charge de 12,5 % des coûts du projet.", country="France")
        assert result.funding_rate == 12.5

    def test_interest_rate_is_not_a_funding_rate(self):
        result = AmountEngine().extract("Prêt bancaire à 3 % d'intérêt annuel.", country="France")
        assert result.funding_rate is None
        assert result.amount_max is None


# ════════════════════════════════════════════════════════════════════════════
# III. QUALITY GATE — 4 états
# ════════════════════════════════════════════════════════════════════════════

class TestDeviceQualityGate:
    def setup_method(self):
        self.gate = DeviceQualityGate()

    def test_valid_complete_device(self):
        """Fiche complète → VALID → auto_published."""
        decision = self.gate.evaluate(make_device())
        assert decision.validation_status == "auto_published"
        assert decision.quality_state == "VALID"
        assert decision.score >= 70

    def test_english_source_is_review_required_not_invalid(self):
        """Source anglaise pertinente → REVIEW_REQUIRED, pas INVALID."""
        device = make_device(
            title="AGNES Intra-Africa Mobility Grants for Junior Researchers 2026",
            short_description=(
                "The program supports junior researchers from African universities with grants "
                "up to USD 7 500 for collaborative research visits across Africa."
            ),
            full_description=(
                "AGNES provides funding for junior researchers to conduct collaborative research. "
                "Eligible applicants must be enrolled at an African university. "
                "Apply before the deadline: March 31, 2026."
            ),
            eligibility_criteria="Junior researchers from African universities, valid research proposal.",
            funding_details="Grant of up to USD 7 500 per researcher.",
            close_date="2026-03-31",
        )
        decision = self.gate.evaluate(device)
        assert decision.quality_state == "REVIEW_REQUIRED", (
            f"Expected REVIEW_REQUIRED for English content, got {decision.quality_state}"
        )
        assert decision.validation_status == "pending_review"
        assert "english_content_remaining" in decision.reasons

    def test_http_403_source_is_review_required(self):
        """Source 403 (contenu inutilisable) → INVALID via unusable marker."""
        device = make_device(
            short_description="Impossible d'acceder a l'URL (HTTP 403 Forbidden). Page non publique.",
            full_description="Aucun contenu exploitable trouve sur cette page.",
        )
        decision = self.gate.evaluate(device)
        assert decision.quality_state == "INVALID"
        assert decision.validation_status == "rejected"

    def test_relative_url_is_review_required(self):
        """URL relative non résolue → REVIEW_REQUIRED."""
        device = make_device(source_url="/aides/1209-aide-relative-non-resolue")
        decision = self.gate.evaluate(device)
        assert decision.quality_state == "REVIEW_REQUIRED", (
            f"Expected REVIEW_REQUIRED for relative URL, got {decision.quality_state}"
        )
        assert "relative_source_url" in decision.reasons

    def test_event_with_high_confidence_is_review_required(self):
        """Contenu EVENT détecté → REVIEW_REQUIRED (pas INVALID, car peut contenir un AAP)."""
        device = make_device(
            title="Atelier de formation PME Abidjan mars 2025",
            short_description=(
                "Le CIPME organise un atelier de formation destiné aux PME ivoiriennes. "
                "Inscription gratuite, 50 places disponibles. Date : 14 mars 2025."
            ),
            full_description=(
                "Programme de la journée : accueil, présentation, sessions intervenants. "
                "Organisé par le CIPME au Centre des Conférences d'Abidjan. "
                "En présentiel. Intervenants experts du financement."
            ),
            funding_details="",
            eligibility_criteria="",
            close_date="2025-03-14",
        )
        decision = self.gate.evaluate(device)
        assert decision.quality_state == "REVIEW_REQUIRED", (
            f"Expected REVIEW_REQUIRED for EVENT, got {decision.quality_state} (content_type: {decision.content_type})"
        )

    def test_prêt_honneur_classifies_correctly(self):
        """Prêt d'honneur reste publiable (VALID ou SUSPECT), pas INVALID."""
        device = make_device(
            title="Prêt d'honneur solidaire — Initiative France",
            short_description=(
                "Prêt à taux zéro de 3 000 à 50 000 EUR accordé à titre personnel au créateur. "
                "Dispositif permanent, dépôt mensuel en comité territorial."
            ),
            full_description=(
                "Initiative France accorde un prêt d'honneur aux créateurs et repreneurs d'entreprise. "
                "Montant : 3 000 à 50 000 EUR. Durée 5 ans, sans garantie personnelle. "
                "Ce prêt facilite l'accès au crédit bancaire en renforçant les fonds propres."
            ),
            eligibility_criteria=(
                "Créateur ou repreneur d'entreprise en difficulté financière, "
                "projet viable, résidence en France."
            ),
            funding_details="Prêt d'honneur de 3 000 à 50 000 EUR à taux zéro.",
            status="recurring",
            is_recurring=True,
            close_date=None,
            recurrence_notes="Comité mensuel, dispositif permanent.",
        )
        decision = self.gate.evaluate(device)
        assert decision.quality_state in ("VALID", "SUSPECT"), (
            f"Expected VALID or SUSPECT for Prêt d'honneur, got {decision.quality_state}"
        )
        assert decision.validation_status == "auto_published"

    def _program_budget_device(self, **overrides):
        """Fiche complète dont seul le budget programme est connu (pas de montant bénéficiaire)."""
        return make_device(
            title="Programme innovation ANCT — doté de 50 millions EUR",
            funding_details="Budget programme : 50 millions EUR. Montant par collectivité à définir.",
            **{
                "short_description": (
                    "L'ANCT lance un programme doté d'un budget global de 50 millions EUR "
                    "pour soutenir les collectivités dans leur transition numérique."
                ),
                "amount_max": None,
                "close_date": None,
                "status": "recurring",
                "is_recurring": True,
                "recurrence_notes": "Programme pluriannuel, dépôts au fil de l'eau.",
                "_program_budget": 50_000_000,
                **overrides,
            },
        )

    def test_program_budget_without_beneficiary_amount_is_suspect(self):
        """Fiche financière complète, budget programme seul → SUSPECT publiable, jamais INVALID."""
        decision = self.gate.evaluate(self._program_budget_device())
        assert decision.quality_state == "SUSPECT"
        assert decision.validation_status == "auto_published"
        assert "suspect:program_budget_only" in decision.reasons

    def test_program_budget_is_never_the_reason_for_invalid(self):
        """Le budget programme ne change pas la validité : même fiche sans _program_budget → même état."""
        with_budget = self.gate.evaluate(self._program_budget_device())
        without_budget = self.gate.evaluate(self._program_budget_device(_program_budget=None))
        assert with_budget.quality_state != "INVALID"
        assert without_budget.quality_state != "INVALID"
        assert "program_budget" not in " ".join(r for r in with_budget.reasons if not r.startswith("suspect:"))

    def test_program_budget_never_changes_state_versus_a_real_amount_on_a_thin_device(self):
        """Fiche sans bénéficiaire ni preuve : l'état ne dépend pas de la présence d'un budget programme."""
        thin = {"full_description": "Programme ANCT.", "eligibility_criteria": "", "short_description": "Programme ANCT."}
        with_budget = self.gate.evaluate(self._program_budget_device(**thin))
        with_amount = self.gate.evaluate(self._program_budget_device(**thin, amount_max=30_000, _program_budget=None))
        assert with_budget.quality_state in ("INVALID", "REVIEW_REQUIRED")
        assert all("program_budget" not in r for r in with_budget.reasons)
        assert with_amount.quality_state in ("INVALID", "REVIEW_REQUIRED")

    def test_recurring_without_evidence_is_review_required(self):
        """Récurrent sans preuve → REVIEW_REQUIRED."""
        decision = self.gate.evaluate(make_device(
            status="recurring",
            is_recurring=False,
            close_date=None,
            recurrence_notes=None,
        ))
        assert decision.quality_state == "REVIEW_REQUIRED"
        assert "recurring_without_evidence" in decision.reasons

    def test_open_without_any_deadline_information_is_review_required(self):
        """Politique deadline : le pipeline ne sait pas s'il existe une échéance → REVIEW_REQUIRED, jamais INVALID."""
        decision = self.gate.evaluate(make_device(close_date=None, status="open", is_recurring=False))
        assert decision.quality_state == "REVIEW_REQUIRED"
        assert "open_without_close_date" in decision.reasons

    def test_source_declaring_no_deadline_is_suspect_and_published(self):
        """La source déclare ne communiquer aucune date → SUSPECT publiable si le reste est fiable."""
        decision = self.gate.evaluate(make_device(
            close_date=None, status="open", is_recurring=False,
            funding_details="Subvention jusqu'à 30 000 EUR. Sans date limite communiquée.",
        ))
        assert decision.quality_state == "SUSPECT"
        assert decision.validation_status == "auto_published"
        assert "suspect:no_deadline_communicated" in decision.reasons

    def test_open_ended_status_without_close_date_is_not_rejected(self):
        """Statut d'attente documenté (standby) : pas de deadline obligatoire."""
        decision = self.gate.evaluate(make_device(close_date=None, status="standby", is_recurring=False))
        assert decision.validation_status == "auto_published"

    def test_valid_device_publishes(self):
        """Fiche complète avec tout → VALID."""
        decision = self.gate.evaluate(make_device())
        assert decision.quality_state == "VALID"
        assert decision.decision == "publish"

    def test_unusable_source_page_is_invalid(self):
        """Contenu inutilisable → INVALID."""
        decision = self.gate.evaluate(make_device(
            short_description="Aucun contenu editorial exploitable trouve sur cette page.",
            full_description="Le site peut utiliser du JavaScript dynamique.",
            source_raw="Impossible d'acceder a l'URL (404).",
        ))
        assert decision.quality_state == "INVALID"
        assert decision.validation_status == "rejected"

    def test_missing_required_fields_is_invalid(self):
        """Champs requis manquants → INVALID."""
        decision = self.gate.evaluate(make_device(
            title="",
            short_description="",
            source_url="",
        ))
        assert decision.quality_state == "INVALID"

    def test_update_admin_only_device_reapplies_visibility(self):
        """Le pipeline doit ré-appliquer les règles de visibilité sur update."""
        from app.collector.pipeline import CollectionPipeline

        # Vérifie que _apply_source_visibility_rules est appellée dans la branche update
        # via la présence de la logique dans _process_item (test structurel)
        import inspect
        source = inspect.getsource(CollectionPipeline._process_item)
        assert "_apply_source_visibility_rules" in source, (
            "_apply_source_visibility_rules doit être appelé dans _process_item pour les updates"
        )

    def test_gso_prefix_not_duplicated(self):
        """Le normalizer ne doit pas ajouter un préfixe déjà présent."""
        from app.collector.normalizer import Normalizer
        source = {
            "id": "test-gso-source",
            "name": "Global South Opportunities",
            "url": "https://globalsouthopportunities.com",
            "organism": "GSO",
            "country": "International",
            "config": {},
        }
        normalizer = Normalizer(source)
        # Simule un titre déjà préfixé (comme stocké en DB après 1ère ingestion)
        title_already_prefixed = "Subvention - AGNES Junior Grants 2026"
        result = normalizer._localize_global_south_title(
            title=title_already_prefixed,
            opportunity_type="subvention",
            country="International",
            amount_label=None,
        )
        # Ne doit pas commencer par "Subvention - Subvention - "
        assert not result.lower().startswith("subvention - subvention"), (
            f"Préfixe dupliqué détecté: {result}"
        )

    def test_gso_triple_prefix_stripped(self):
        """Triple préfixe GSO → complètement nettoyé avant ajout du bon préfixe."""
        from app.collector.normalizer import Normalizer
        source = {
            "id": "test-gso",
            "name": "Global South Opportunities",
            "url": "https://globalsouthopportunities.com",
            "organism": "GSO",
            "country": "International",
            "config": {},
        }
        normalizer = Normalizer(source)
        triple = "Subvention - Subvention - Subvention - Real Program Title"
        result = normalizer._localize_global_south_title(
            title=triple,
            opportunity_type="subvention",
            country="International",
            amount_label=None,
        )
        # Doit contenir "Real Program Title" sans triple préfixe
        assert result.count("Subvention") <= 1, f"Trop de préfixes dans: {result}"
        assert "Real Program Title" in result, f"Titre original perdu: {result}"

    @pytest.mark.parametrize("title", [
        "Subvention - Programme X",
        "Subvention - Subvention - Programme X",
        "Subvention - Subvention - Subvention - Programme X",
        "Programme X",
    ])
    def test_gso_prefixes_normalize_to_exactly_one_and_are_idempotent(self, title):
        from app.collector.normalizer import Normalizer
        normalizer = Normalizer({
            "id": "test-gso",
            "name": "Global South Opportunities",
            "url": "https://globalsouthopportunities.com",
            "organism": "GSO",
            "country": "International",
            "config": {},
        })

        def normalize(value):
            return normalizer._localize_global_south_title(
                title=value, opportunity_type="subvention", country="International", amount_label=None
            )

        once = normalize(title)
        assert once == "Subvention - Programme X"
        assert normalize(once) == once


# ════════════════════════════════════════════════════════════════════════════
# IV. URL RECONSTRUCTION
# ════════════════════════════════════════════════════════════════════════════

class TestUrlReconstruction:
    def _make_pipeline(self, source_url: str):
        from unittest.mock import MagicMock
        from app.collector.pipeline import CollectionPipeline
        db = MagicMock()
        source = {
            "id": "test-src",
            "name": "Test source",
            "url": source_url,
            "organism": "ANCT",
            "country": "France",
            "config": {},
            "level": 2,
        }
        pipeline = CollectionPipeline.__new__(CollectionPipeline)
        pipeline.source = source
        pipeline.source_id = "test-src"
        pipeline.source_level = 2
        return pipeline

    def test_relative_url_resolved_with_base(self):
        """URL relative + base URL connue → URL absolue reconstruite."""
        pipeline = self._make_pipeline("https://aides-territoires.beta.gouv.fr")
        resolved = pipeline._try_resolve_relative_url("/aides/1209-aide-vegetation")
        assert resolved == "https://aides-territoires.beta.gouv.fr/aides/1209-aide-vegetation", (
            f"URL non résolue correctement: {resolved}"
        )

    def test_relative_url_without_base_stays_relative(self):
        """URL relative sans base URL → reste relative (quality gate la flaggera)."""
        pipeline = self._make_pipeline("")
        resolved = pipeline._try_resolve_relative_url("/aides/9999")
        assert resolved == "/aides/9999"

    def test_absolute_url_unchanged(self):
        """URL absolue → inchangée."""
        pipeline = self._make_pipeline("https://www.bpifrance.fr")
        resolved = pipeline._try_resolve_relative_url("https://www.bpifrance.fr/nos-solutions/aide")
        assert resolved == "https://www.bpifrance.fr/nos-solutions/aide"


# ════════════════════════════════════════════════════════════════════════════
# V. GOLDEN DATASET — comparaison avant/après
# ════════════════════════════════════════════════════════════════════════════

class TestGoldenDataset:
    """Mesures agrégées sur le golden dataset, via le harnais partagé (tests/fixtures/golden_harness.py)."""

    def test_golden_dataset_publish_precision(self):
        from tests.fixtures.golden_dataset import GOLDEN_DATASET
        from tests.fixtures.golden_harness import evaluate_case

        results = [(c, evaluate_case(c)["decision"]) for c in GOLDEN_DATASET]
        wrong = [
            c["id"] for c, d in results
            if (d.validation_status == "auto_published") != c["expected"]["should_publish"]
        ]
        precision = 1 - len(wrong) / len(results)
        print(f"\n[GOLDEN DATASET] Précision publication: {precision:.1%} ({len(results) - len(wrong)}/{len(results)})")
        assert precision >= 0.60, f"Précision publication trop basse: {precision:.1%}. Cas incorrects: {wrong}"

    def test_golden_dataset_no_false_positives_on_events(self):
        """Aucun événement clair ne doit être auto_published."""
        from tests.fixtures.golden_dataset import GOLDEN_DATASET
        from tests.fixtures.golden_harness import evaluate_case

        false_positives = [
            c["id"] for c in GOLDEN_DATASET
            if c["expected"]["content_nature"] == "EVENT"
            and evaluate_case(c)["decision"].validation_status == "auto_published"
        ]
        assert false_positives == [], f"Faux positifs EVENT auto-publiés : {false_positives}"

    def test_golden_dataset_a_category_all_publishable(self):
        """Les cas A publiables (français) doivent être auto_published."""
        from tests.fixtures.golden_dataset import get_cases_by_category
        from tests.fixtures.golden_harness import evaluate_case

        not_published = [
            (c["id"], d.quality_state, d.reasons[:3])
            for c in get_cases_by_category("A")
            if c["expected"]["should_publish"]
            for d in [evaluate_case(c)["decision"]]
            if d.validation_status != "auto_published"
        ]
        assert not_published == [], f"Cas A non publiés: {not_published}"

    def test_golden_dataset_amounts_match_expected(self):
        """Extraction des montants : min, max, devise et type pour les 40 cas."""
        from tests.fixtures.golden_dataset import GOLDEN_DATASET
        from tests.fixtures.golden_harness import evaluate_case

        mismatches = []
        for c in GOLDEN_DATASET:
            e, a = c["expected"], evaluate_case(c)["amounts"]
            has_amount = e.get("amount_min") is not None or e.get("amount_max") is not None
            got = (a.amount_min, a.amount_max, a.amount_type.value, a.currency if has_amount else None)
            want = (e.get("amount_min"), e.get("amount_max"), e["amount_type"], e["currency"] if has_amount else None)
            if got != want:
                mismatches.append((c["id"], got, want))
        assert mismatches == []


# ════════════════════════════════════════════════════════════════════════════
# VI. RAPPORT AVANT/APRÈS (pour le livrable)
# ════════════════════════════════════════════════════════════════════════════

def test_sprint_qualite_1_summary(capsys):
    """Produit le rapport avant/après du sprint."""
    from tests.fixtures.golden_dataset import GOLDEN_DATASET
    from tests.fixtures.golden_harness import evaluate_case

    results = {
        "publish_correct": 0,
        "quality_state_correct": 0,
        "content_type_correct": 0,
        "amount_extracted": 0,
        "total": len(GOLDEN_DATASET),
        "false_positive_events": 0,
        "false_negative_financing": 0,
    }

    for case in GOLDEN_DATASET:
        expected = case["expected"]
        outcome = evaluate_case(case)
        decision, content, amount = outcome["decision"], outcome["content"], outcome["amounts"]

        if (decision.validation_status == "auto_published") == expected["should_publish"]:
            results["publish_correct"] += 1
        if decision.quality_state == expected["quality_state"]:
            results["quality_state_correct"] += 1
        if content.content_type.value == expected["content_nature"]:
            results["content_type_correct"] += 1

        expected_max = expected.get("amount_max")
        if expected_max and amount.amount_max and abs(amount.amount_max - expected_max) / expected_max < 0.05:
            results["amount_extracted"] += 1
        elif expected_max is None and amount.amount_max is None:
            results["amount_extracted"] += 1

        if expected["content_nature"] == "EVENT" and decision.validation_status == "auto_published":
            results["false_positive_events"] += 1
        if expected["content_nature"] == "FINANCING_OPPORTUNITY" and expected["should_publish"] and decision.validation_status != "auto_published":
            results["false_negative_financing"] += 1

    total = results["total"]
    print("\n" + "═" * 60)
    print("SPRINT QUALITÉ 1 — RAPPORT AVANT/APRÈS (Golden Dataset)")
    print("═" * 60)
    print(f"  Précision publication:       {results['publish_correct']}/{total} ({results['publish_correct']/total:.1%})")
    print(f"  Précision quality_state:     {results['quality_state_correct']}/{total} ({results['quality_state_correct']/total:.1%})")
    print(f"  Précision content_type:      {results['content_type_correct']}/{total} ({results['content_type_correct']/total:.1%})")
    print(f"  Précision montant:           {results['amount_extracted']}/{total} ({results['amount_extracted']/total:.1%})")
    print(f"  Faux positifs événements:    {results['false_positive_events']}")
    print(f"  Faux négatifs financement:   {results['false_negative_financing']}")
    print("═" * 60)

    assert results["false_positive_events"] == 0, (
        "Des événements ont été auto-publiés (faux positifs critiques)"
    )
