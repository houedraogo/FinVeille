"""SQ1.1 — classification adversariale, sémantique des montants, critères métier du Quality Gate, encodage."""
import pytest

from app.services.amount_engine import AmountEngine, AmountType
from app.services.content_classifier import ContentClassifier, ContentType
from app.services.device_quality import DeviceQualityGate
from app.utils.encoding_repair import looks_mojibake, repair_mojibake

FAR_FUTURE = "2099-12-31"


def device(**overrides):
    base = {
        "title": "Prêt d'honneur Initiative Cotentin",
        "source_url": "https://example.org/pret-honneur",
        "short_description": "Prêt d'honneur de 20 000 EUR pour les créateurs d'entreprise du Cotentin.",
        "full_description": "",
        "eligibility_criteria": "",
        "funding_details": "",
        "country": "France",
        "status": "recurring",
        "is_recurring": True,
        "close_date": None,
    }
    base.update(overrides)
    return base


# ════════════════════════════════════════════════════════════════════════════
# 1. CLASSIFIER — cas adversariaux
# ════════════════════════════════════════════════════════════════════════════

ADVERSARIAL = {
    "event_announcing_a_subsidy": (ContentType.EVENT, dict(
        title="Forum de lancement du Fonds Innovation Sahel",
        short_description="Le Fonds Innovation Sahel sera présenté lors du forum. Une subvention de 50 000 EUR sera annoncée en clôture.",
        full_description="Inscription gratuite, intervenants et panélistes, en présentiel à Dakar. Organisé par la Chambre de commerce.",
    )),
    "subsidy_presented_at_an_event": (ContentType.FINANCING_OPPORTUNITY, dict(
        title="Subvention export PME — Région Sud",
        short_description="Subvention jusqu'à 80 000 EUR pour les PME exportatrices, présentée lors du salon Export Days de Marseille.",
        full_description="Dossier de candidature à déposer en ligne. Date limite : 15 mars 2027. Critères d'éligibilité : PME de la région.",
    )),
    "publication_of_a_call_results": (ContentType.RESULT_ANNOUNCEMENT, dict(
        title="Résultats de l'appel à projets Innovation 2025",
        short_description="La Région publie les résultats de l'appel à projets : 40 lauréats sélectionnés parmi 300 dossiers.",
        full_description="Félicitations aux lauréats. La liste complète des projets retenus est disponible. La prochaine session sera annoncée en 2027.",
    )),
    "new_call_referring_to_previous_results": (ContentType.FINANCING_OPPORTUNITY, dict(
        title="Nouvel appel à candidatures Innovation 2026",
        short_description="Suite aux résultats de l'édition 2025 (40 lauréats sélectionnés), la Région lance un nouvel appel : subvention jusqu'à 50 000 EUR.",
        full_description="Date limite de dépôt : 30 juin 2026. Dossier de candidature en ligne. Critères d'éligibilité : PME de la région.",
    )),
    "world_bank_institutional_project": (ContentType.INSTITUTIONAL_PROJECT, dict(
        title="Niger Basic Services Project",
        short_description="IDA credit approved for the Republic of Niger. The Ministry of Finance is the implementing agency.",
        full_description="World Bank project appraisal document. Financing agreement signed with the Government of Niger. Disbursements through 2029.",
    )),
    "world_bank_funded_call_open_to_smes": (ContentType.FINANCING_OPPORTUNITY, dict(
        title="Programme d'appui aux PME — financé par la Banque mondiale",
        short_description="Appel à candidatures ouvert aux PME : subvention jusqu'à 20 000 USD, financée par la Banque mondiale via le ministère.",
        full_description="Date limite : 30 septembre 2026. Critères d'éligibilité : PME formelle, chiffre d'affaires minimal.",
    )),
    "support_without_funding": (ContentType.NON_FINANCIAL_SUPPORT, dict(
        title="Programme d'accompagnement export",
        short_description="Accompagnement individuel par un expert pour préparer votre développement export. Sans financement : uniquement un accompagnement.",
        full_description="Mentorat et mise en relation avec des acheteurs. Pas de financement direct.",
    )),
    "support_with_financial_coverage": (ContentType.FINANCING_OPPORTUNITY, dict(
        title="Programme d'accompagnement startups",
        short_description="Six mois d'accompagnement avec prise en charge financière : bourse de 5 000 EUR versée à chaque startup lauréate.",
        full_description="Candidatures ouvertes jusqu'au 30 novembre 2026. Critères d'éligibilité : startups de moins de 3 ans.",
    )),
}


@pytest.mark.parametrize("name", list(ADVERSARIAL))
def test_adversarial_classification(name):
    expected, fields = ADVERSARIAL[name]
    result = ContentClassifier().classify(fields)
    assert result.content_type == expected, f"{name}: got {result.content_type} {result.signals}"


def test_world_bank_project_closed_to_private_sector_is_denied_access():
    result = ContentClassifier().classify(dict(
        title="Cameroon Roads Rehabilitation Project",
        short_description="World Bank loan of USD 300 million to the Government of Cameroon. Not accessible to private sector or NGOs.",
    ))
    assert result.content_type == ContentType.INSTITUTIONAL_PROJECT
    assert result.private_access_denied


def test_unusable_source_page_is_unknown_not_financing():
    result = ContentClassifier().classify(dict(
        title="Aide inaccessible", short_description="Impossible d'acceder a l'URL (HTTP 403 Forbidden).",
    ))
    assert result.content_type == ContentType.UNKNOWN


# ════════════════════════════════════════════════════════════════════════════
# 2. MONEY SEMANTICS
# ════════════════════════════════════════════════════════════════════════════

class TestMoneySemantics:
    def extract(self, text):
        return AmountEngine().extract(text, country="France")

    def test_cir_rate_with_expense_cap_leaves_amount_max_null(self):
        r = self.extract("crédit d'impôt de 30 % des dépenses éligibles dans la limite de 100 M€ de dépenses")
        assert r.funding_rate == 30.0
        assert r.eligible_expense_cap == 100_000_000
        assert r.amount_max is None and r.amount_min is None
        assert r.amount_type == AmountType.RATE_ONLY

    def test_real_cir_wording_from_the_recette_sample(self):
        r = self.extract(
            "Crédit d'impôt représentant : - 30 % du montant des dépenses éligibles exposées au cours de l'année, "
            "dans la limite de 100 millions € ; - 5 % du montant des dépenses éligibles, sans plafond."
        )
        assert r.funding_rate == 30.0
        assert r.eligible_expense_cap == 100_000_000
        assert r.amount_max is None

    def test_expense_ceiling(self):
        r = self.extract("Subvention de 40 % des dépenses, avec un plafond de dépenses éligibles de 200 000 EUR.")
        assert (r.funding_rate, r.eligible_expense_cap, r.amount_max) == (40.0, 200_000, None)

    def test_maximum_base(self):
        r = self.extract("Aide de 50 % sur une assiette maximale de 300 000 EUR HT.")
        assert (r.funding_rate, r.eligible_expense_cap, r.amount_max) == (50.0, 300_000, None)

    def test_total_project_cost_is_not_an_aid_amount(self):
        r = self.extract("Le coût total du projet de 500 000 EUR est financé à 40 %.")
        assert r.funding_rate == 40.0
        assert r.amount_max is None and r.eligible_expense_cap is None and r.program_budget is None

    def test_program_budget_stays_program_budget(self):
        r = self.extract("Enveloppe globale de 20 millions EUR pour le programme.")
        assert r.program_budget == 20_000_000
        assert r.amount_max is None and r.eligible_expense_cap is None

    def test_per_beneficiary_ceiling_is_amount_max(self):
        r = self.extract("Plafond d'aide par bénéficiaire : 150 000 EUR.")
        assert r.amount_max == 150_000
        assert r.eligible_expense_cap is None

    def test_explicit_aid_amount_and_expense_ceiling_coexist(self):
        r = self.extract("Subvention de 30 000 EUR. Taux de financement : 70 % des dépenses éligibles plafonnées à 30 000 EUR.")
        assert r.amount_max == 30_000
        assert r.funding_rate == 70.0
        assert r.eligible_expense_cap == 30_000

    def test_service_paid_by_funder_with_no_direct_funding_has_no_rate(self):
        r = self.extract("Prestation de conseil financée à 100 % par Bpifrance. Pas de financement direct.")
        assert r.funding_rate is None


# ════════════════════════════════════════════════════════════════════════════
# 3. QUALITY GATE — critères métier
# ════════════════════════════════════════════════════════════════════════════

class TestBusinessCriteria:
    def setup_method(self):
        self.gate = DeviceQualityGate()

    def test_short_but_precise_description_can_be_valid(self):
        decision = self.gate.evaluate(device(full_description="Ouverture permanente, dépôt mensuel en comité."))
        assert decision.quality_state == "VALID", decision.reasons

    def test_long_but_ambiguous_description_is_not_valid(self):
        prose = (
            "Ce dispositif s'inscrit dans une dynamique globale de transformation des territoires et de renforcement "
            "de l'attractivité, en cohérence avec les orientations stratégiques et les priorités partagées par l'ensemble "
            "des parties prenantes, dans un esprit de concertation et de valorisation des initiatives locales. "
        ) * 4
        decision = self.gate.evaluate(device(
            title="Dispositif territorial", short_description=prose[:180], full_description=prose,
            status="open", is_recurring=False, close_date=FAR_FUTURE,
        ))
        assert decision.validation_status != "auto_published", (decision.quality_state, decision.reasons)

    def test_amount_present_in_text_but_not_extracted_is_not_reported_missing(self):
        decision = self.gate.evaluate(device(
            funding_details="Subvention jusqu'à 30 000 EUR par projet.", short_description="Aide aux PME innovantes de la région.",
            status="open", is_recurring=False, close_date=FAR_FUTURE,
        ))
        assert decision.criteria["mechanism"] == "quantified"
        assert "suspect:no_beneficiary_amount" not in decision.reasons

    def test_instrument_without_amount_is_suspect_not_invalid(self):
        decision = self.gate.evaluate(device(
            short_description="Subvention disponible pour les PME ivoiriennes souhaitant accéder aux marchés export.",
            status="open", is_recurring=False, close_date=FAR_FUTURE,
        ))
        assert decision.quality_state == "SUSPECT"
        assert decision.validation_status == "auto_published"

    def test_results_and_news_are_invalid_events_need_review(self):
        gate = self.gate
        results = gate.evaluate({**ADVERSARIAL["publication_of_a_call_results"][1], "source_url": "https://example.org/r"})
        event = gate.evaluate({**ADVERSARIAL["event_announcing_a_subsidy"][1], "source_url": "https://example.org/e"})
        assert results.quality_state == "INVALID"
        assert event.quality_state == "REVIEW_REQUIRED"

    def test_institutional_project_review_unless_private_access_is_denied(self):
        base = dict(title="Mali Agricultural Transformation Project", source_url="https://example.org/p")
        open_case = self.gate.evaluate({**base, "short_description": "World Bank loan to the Government of Mali for agricultural productivity. Project duration 2024-2030."})
        closed_case = self.gate.evaluate({**base, "short_description": "World Bank loan to the Government of Mali. Not accessible to private sector or NGOs."})
        assert open_case.quality_state == "REVIEW_REQUIRED"
        assert closed_case.quality_state == "INVALID"

    def test_no_business_substance_is_invalid(self):
        decision = self.gate.evaluate(device(
            title="Aide", short_description="Aide.", status="open", is_recurring=False, close_date=None, country="",
        ))
        assert decision.quality_state == "INVALID"
        assert "no_business_substance" in decision.reasons

    def test_missing_deadline_alone_never_rejects(self):
        for status, recurring, text in (("open", False, ""), ("open", False, " Sans date limite communiquée."), ("recurring", True, "")):
            decision = self.gate.evaluate(device(
                short_description=f"Subvention de 20 000 EUR pour les PME innovantes.{text}", status=status, is_recurring=recurring,
            ))
            assert decision.quality_state != "INVALID", (status, text, decision.reasons)

    def test_english_content_is_detected_on_short_texts(self):
        decision = self.gate.evaluate(device(
            title="Research Fund", short_description="Grants for agricultural research in Africa. Application process ongoing, no specific deadline.",
        ))
        assert "english_content_remaining" in decision.reasons
        assert decision.quality_state == "REVIEW_REQUIRED"


# ════════════════════════════════════════════════════════════════════════════
# 4. ENCODAGE (cas D07)
# ════════════════════════════════════════════════════════════════════════════

MOJIBAKE_BUDGET = "Aide Ã  l'innovation numérique pour les PME. Budget : 50 000 â‚¬. Contact : aide@exemple.fr"


class TestEncoding:
    def test_helper_detects_and_repairs(self):
        assert looks_mojibake(MOJIBAKE_BUDGET)
        repaired = repair_mojibake(MOJIBAKE_BUDGET)
        assert "50 000 €" in repaired and "Aide à l'innovation" in repaired
        assert not looks_mojibake(repaired)
        assert repair_mojibake(repaired) == repaired

    def test_clean_text_is_untouched(self):
        text = "Aide à l'innovation numérique — budget 50 000 € pour les PME."
        assert not looks_mojibake(text)
        assert repair_mojibake(text) == text

    def test_corrupted_source_is_held_for_review_and_amount_is_recovered(self):
        decision = DeviceQualityGate().evaluate(device(
            title="Aide Ã  l'innovation", short_description=MOJIBAKE_BUDGET, status="open", is_recurring=False,
        ))
        assert "encoding_corrupted" in decision.reasons
        assert decision.validation_status == "pending_review"
        assert AmountEngine().extract(MOJIBAKE_BUDGET, country="France").amount_max == 50_000


# ════════════════════════════════════════════════════════════════════════════
# 5. RÉGRESSIONS ISSUES DU REJEU SUR DONNÉES RÉELLES (232 fiches)
# ════════════════════════════════════════════════════════════════════════════

class TestRealDataRegressions:
    clf = ContentClassifier()
    engine = AmountEngine()

    def test_lender_that_also_offers_non_financial_services_stays_financing(self):
        result = self.clf.classify(dict(
            title="SAFINE Burkina Faso - crédits et accompagnement des MPME",
            short_description="SAFINE propose des crédits d'exploitation, des crédits d'équipement et des services d'accompagnement.",
            funding_details="L'appui peut prendre la forme de crédit d'exploitation et de services non financiers comme le conseil et la formation.",
            device_type="pret",
        ))
        assert result.content_type == ContentType.FINANCING_OPPORTUNITY

    def test_reserved_access_to_public_procurement_is_support_not_a_tender(self):
        scheme = self.clf.classify(dict(
            title="PJFE Togo - accès à 25% des marchés publics pour jeunes et femmes",
            short_description="Pas de financement direct. L'avantage principal est l'accès réservé à une part de marchés publics.",
        ))
        tender = self.clf.classify(dict(
            title="Avis de marché - fourniture de matériel",
            short_description="Appel d'offres ouvert. Dossier de consultation disponible auprès de l'acheteur public. Marché public de fournitures.",
        ))
        assert scheme.content_type == ContentType.NON_FINANCIAL_SUPPORT
        assert tender.content_type == ContentType.PUBLIC_PROCUREMENT

    def test_support_whose_goal_is_access_to_financing_is_not_financing(self):
        result = self.clf.classify(dict(
            title="PACA CI - accompagnement de 150 PME à la transformation digitale",
            short_description="L'appui porte sur l'accompagnement technique, la transformation digitale et l'accès au financement.",
        ))
        assert result.content_type == ContentType.NON_FINANCIAL_SUPPORT

    def test_date_limite_as_a_label_is_not_an_open_call_but_a_real_date_is(self):
        label = self.clf.classify(dict(
            title="Fiche de veille", short_description="Vérifier la zone couverte, le secteur et la date limite. Critères d'éligibilité à confirmer.",
        ))
        dated = self.clf.classify(dict(
            title="Subvention innovation", short_description="Subvention pour les PME. Date limite : 5 octobre 2027.",
        ))
        assert not label.application_mechanism
        assert dated.application_mechanism

    def test_aid_page_with_weak_partnership_wording_is_not_news(self):
        result = self.clf.classify(dict(
            title="Aide à la connaissance - Innovation",
            short_description="Aide de l'Etat destinée aux PME, dans le cadre d'une convention de partenariat avec la région. Subvention plafonnée.",
        ))
        assert result.content_type == ContentType.FINANCING_OPPORTUNITY

    def test_source_typed_institutional_project_is_institutional(self):
        result = self.clf.classify(dict(
            title="Burkina Faso Energy Access Project", short_description="Ce projet est porté au Burkina Faso. La clôture prévisionnelle est fixée au 31/12/2028.",
            device_type="institutional_project",
        ))
        assert result.content_type == ContentType.INSTITUTIONAL_PROJECT

    def test_tax_credit_capped_on_the_credit_itself_keeps_amount_max(self):
        r = self.engine.extract("Le crédit d'impôt est plafonné à 30 000 € par an et par entreprise. Taux de 15 %.", country="France")
        assert r.amount_max == 30_000
        assert r.eligible_expense_cap is None

    def test_repeated_investment_range_is_one_range_not_a_program_budget(self):
        line = "Montant indicatif compris entre 10 000 000 EUR et 50 000 000 EUR."
        r = self.engine.extract(f"{line} Le fonds cible des entreprises innovantes. {line} Présentation. {line}", country="France")
        assert (r.amount_min, r.amount_max) == (10_000_000, 50_000_000)
        assert r.program_budget is None
        assert r.amount_type == AmountType.RANGE

    def test_minimum_expense_threshold_is_not_an_aid_range(self):
        r = self.engine.extract(
            "Le montant minimal de dépenses est de 10 000 EUR HT et le plafond de dépenses éligibles est fixé à 100 000 EUR HT. "
            "Subvention jusqu'à 70 % sur une assiette plafonnée à 100 000 EUR HT.",
            country="France",
        )
        assert r.amount_min is None and r.amount_max is None
        assert r.eligible_expense_cap == 100_000
        assert r.funding_rate == 70.0

    def test_offered_instrument_with_qualifier_words_is_read(self):
        r = self.engine.extract("Prêt d'honneur de 20 000 EUR pour les créateurs.", country="France")
        assert r.amount_max == 20_000

    def test_template_mention_of_non_financial_benefits_does_not_make_a_competition_non_financial(self):
        result = self.clf.classify(dict(
            title="Challenge mondial MIT Solve - Solver Impact Fund", device_type="concours",
            short_description="Challenge ouvert aux PME et associations. La date limite actuellement repérée est le 21/05/2026.",
            funding_details="Les montants, avantages non financiers et éventuelles contreparties doivent être confirmés sur la source officielle.",
        ))
        assert result.content_type == ContentType.FINANCING_OPPORTUNITY

    def test_asserted_non_financial_support_is_still_recognised(self):
        result = self.clf.classify(dict(
            title="Programme Phoenix", short_description="Croissance et mise à niveau des PME.",
            funding_details="L'appui est surtout non financier : diagnostic, coaching et mise à niveau.",
        ))
        assert result.content_type == ContentType.NON_FINANCIAL_SUPPORT
