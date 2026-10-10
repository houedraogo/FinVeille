"""SQ1.2 — semantic role of every number, source-grounded on real pages captured during the SQ1.1 staging recette."""
import pytest

from app.collector.base_connector import RawItem
from app.collector.normalizer import Normalizer
from app.schemas.device import DeviceCreate
from app.services.amount_engine import AmountEngine, AmountRole, AmountType, PercentRole, parse_money
from app.services.content_classifier import ContentClassifier, ContentType
from app.services.device_quality import DeviceQualityGate
from app.services.taxonomy_classifier import classify_taxonomy
from tests.fixtures.real_pages import REAL_PAGES as P

engine = AmountEngine()
classifier = ContentClassifier()


def roles(result):
    return {(round(v, 4), r) for v, r, *_ in result.percent_roles}


def amount_roles(result):
    return {(v, r) for v, r, *_ in result.amount_roles}


# ════════════════════════════════════════════════════════════════════════════
# R1 — EUROGIA: a partner-share limit is not a subsidy rate
# ════════════════════════════════════════════════════════════════════════════

class TestR1PartnerShareCap:
    @pytest.mark.parametrize("page", ["eurogia", "eureka_biotech"])
    def test_real_page_partner_share_is_not_a_funding_rate(self, page):
        r = engine.extract(P[page]["text"], country="France")
        assert r.funding_rate is None
        assert (70.0, PercentRole.PARTNER_SHARE_CAP.value) in roles(r)
        # the aid range stated on the same page is kept
        assert (r.amount_min, r.amount_max) == (50_000, 3_000_000)

    @pytest.mark.parametrize("text", [
        "A partner or a group of partners from the same country must not exceed 70% of the project budget.",
        "No more than 70% of the project budget may come from a single partner.",
        "Un partenaire issu du même pays ne doit pas représenter plus de 70 % du budget du projet.",
    ])
    def test_partner_share_wording_variants(self, text):
        r = engine.extract(text, country="France")
        assert r.funding_rate is None
        assert any(role == PercentRole.PARTNER_SHARE_CAP.value for _, role, _ in r.percent_roles)

    def test_a_real_funding_rate_on_the_project_budget_is_still_a_rate(self):
        r = engine.extract("La subvention finance 70 % du budget du projet éligible.", country="France")
        assert r.funding_rate == 70.0


# ════════════════════════════════════════════════════════════════════════════
# R2 — JEI: an eligibility percentage is not a rate
# ════════════════════════════════════════════════════════════════════════════

class TestR2EligibilityThreshold:
    def test_real_page_rd_share_of_charges_is_a_threshold(self):
        r = engine.extract(P["jei"]["text"], country="France")
        assert r.funding_rate is None
        assert (15.0, PercentRole.ELIGIBILITY_THRESHOLD.value) in roles(r)

    @pytest.mark.parametrize("text", [
        "Avoir des dépenses de R&D représentant entre 5 et 15 % des charges fiscalement déductibles.",
        "Le capital doit être détenu à au moins 50 % par des personnes physiques.",
        "Réaliser un chiffre d'affaires dont 30 % à l'export.",
    ])
    def test_eligibility_percentages_never_feed_funding_rate(self, text):
        assert engine.extract(text, country="France").funding_rate is None


# ════════════════════════════════════════════════════════════════════════════
# R3 — CIR: the main rate is 30 %, competing percentages must not override it
# ════════════════════════════════════════════════════════════════════════════

class TestR3CirMainRate:
    def test_real_page_main_rate_cap_and_no_amount_max(self):
        r = engine.extract(P["cir"]["text"], country="France")
        assert r.funding_rate == 30.0
        assert r.eligible_expense_cap == 100_000_000
        assert r.amount_max is None and r.amount_min is None

    def test_competing_percentages_by_role(self):
        r = engine.extract(P["cir"]["text"], country="France")
        by_role = roles(r)
        assert (40.0, PercentRole.EXPENSE_SHARE.value) in by_role       # flat-rate expense rule
        assert (75.0, PercentRole.EXPENSE_SHARE.value) in by_role
        assert (30.0, PercentRole.FUNDING_RATE.value) in by_role
        # bonus / above-ceiling / pre-financing rates are recorded but never chosen
        secondary = [(v, role) for v, role, sec in r.percent_roles if sec]
        assert any(v in (5.0, 50.0) for v, _ in secondary)

    def test_synthetic_competing_percentages(self):
        text = (
            "Crédit d'impôt représentant : - 30 % du montant des dépenses éligibles, dans la limite de 100 millions € ; "
            "- 5 % du montant des dépenses éligibles, sans plafond. Dans les DOM, le taux du CIR est majoré : "
            "- 50 % du montant des dépenses éligibles. Frais de fonctionnement fixés forfaitairement à 40 % des dépenses de personnel."
        )
        r = engine.extract(text, country="France")
        assert (r.funding_rate, r.eligible_expense_cap, r.amount_max) == (30.0, 100_000_000, None)

    def test_when_only_secondary_rates_exist_no_rate_is_invented(self):
        r = engine.extract("Le taux est majoré à 50 % du montant des dépenses éligibles pour les entreprises des DOM.", country="France")
        assert r.funding_rate is None


# ════════════════════════════════════════════════════════════════════════════
# R4 / R5 — size floors of the expense basis are not aid amounts
# ════════════════════════════════════════════════════════════════════════════

class TestR4R5ExpenseFloor:
    def test_grands_defis_project_size_floor(self):
        r = engine.extract(P["grands_defis"]["text"], country="France")
        assert r.amount_max is None and r.amount_min is None
        assert r.eligible_expense_floor == 4_000_000
        assert (4_000_000, AmountRole.ELIGIBLE_EXPENSE_FLOOR.value) in amount_roles(r)

    def test_vehicules_routiers_minimum_eligible_expense_basis(self):
        r = engine.extract(P["vehicules"]["text"], country="France")
        assert r.amount_min is None and r.amount_max is None
        assert r.eligible_expense_floor == 1_000_000
        assert (2_000_000, AmountRole.ELIGIBLE_EXPENSE_FLOOR.value) in amount_roles(r)   # the collaborative-project floor too

    @pytest.mark.parametrize("text", [
        "Le montant minimal de dépenses est de 10 000 EUR HT.",
        "Projets présentant un coût total supérieur à 2 millions d'euros.",
        "Projects must have eligible expenses of at least EUR 500 000.",
    ])
    def test_floor_wordings_variants(self, text):
        r = engine.extract(text, country="France")
        assert r.amount_min is None and r.amount_max is None
        assert r.eligible_expense_floor is not None

    @pytest.mark.parametrize("text,expected_min", [
        ("Aide minimale de 5 000 € par bénéficiaire.", 5_000),
        ("Subvention d'au moins 10 000 € pour les PME.", 10_000),
        ("Le prêt est d'un montant minimum de 3 000 €.", 3_000),
    ])
    def test_a_real_minimum_aid_is_still_a_minimum_aid(self, text, expected_min):
        r = engine.extract(text, country="France")
        assert r.amount_min == expected_min
        assert r.eligible_expense_floor is None


# ════════════════════════════════════════════════════════════════════════════
# R6 — institutional projects: project-level money is not a beneficiary amount
# ════════════════════════════════════════════════════════════════════════════

WB_SOURCE = {
    "id": "wb-bf", "name": "Banque Mondiale - projets Burkina Faso", "organism": "World Bank Group", "country": "Burkina Faso",
    "url": "https://search.worldbank.org/api/v3/projects", "level": 2, "collection_mode": "api", "config": {},
}
AFDB_SOURCE = {
    "id": "afdb", "name": "Banque africaine de développement - projets", "organism": "African Development Bank", "country": "Sénégal",
    "url": "https://www.afdb.org/en/projects-and-operations", "level": 2, "collection_mode": "html", "config": {},
}


class TestR6InstitutionalProjectAmounts:
    def test_engine_flag_demotes_every_amount_of_the_real_wb_abstract(self):
        without = engine.extract(P["wb_resilience"]["text"], country="Burkina Faso")
        demoted = engine.extract(P["wb_resilience"]["text"], country="Burkina Faso", institutional_project=True)
        assert without.amount_max is not None or without.amount_min is not None   # the raw figures exist in the page
        assert demoted.amount_min is None and demoted.amount_max is None
        assert demoted.project_cost is not None

    def test_normalizer_on_the_real_wb_page_stores_no_beneficiary_amount(self):
        page = P["wb_resilience"]
        item = RawItem(title=page["title"], url=page["url"], raw_content=page["text"],
                       metadata={"id": "P511652", "countryshortname": "Burkina Faso", "closingdate": "2031-06-30"})
        payload = Normalizer(WB_SOURCE).normalize(item)
        assert payload["amount_min"] is None and payload["amount_max"] is None
        assert payload["currency"] is None

    def test_generalises_to_another_multilateral_bank_without_a_source_typed_device(self):
        """No World Bank name, no device_type hint: detected from the content itself."""
        text = (
            "The African Development Bank approved a loan of US$85 million to the Government of Senegal for the Rural Roads Project. "
            "The Ministry of Infrastructure is the implementing agency. The financing agreement was signed with the Republic of Senegal. "
            "The total project cost is US$120 million, including a US$85 million ADB loan and US$35 million of government counterpart funding."
        )
        item = RawItem(title="Senegal Rural Roads Project", url="https://www.afdb.org/en/projects/P-SN-DB0-001", raw_content=text, metadata={})
        payload = Normalizer(AFDB_SOURCE).normalize(item)
        assert payload["amount_min"] is None and payload["amount_max"] is None

    def test_a_company_facing_grant_with_the_same_wording_keeps_its_amount(self):
        text = "Subvention jusqu'à 50 000 EUR pour les PME innovantes. Date limite : 30 juin 2027. Financée par la Banque mondiale."
        assert engine.extract(text, country="France").amount_max == 50_000


# ════════════════════════════════════════════════════════════════════════════
# R7 — EDURÉNOV: an active call beats the narration of past laureates
# ════════════════════════════════════════════════════════════════════════════

def _device(page, **extra):
    text = page["text"]
    return {"title": page["title"], "source_url": page["url"], "short_description": text[:300], "full_description": text,
            "status": "standby", "is_recurring": False, "country": "France", **extra}


class TestR7ActiveCallBeatsHistory:
    def test_real_edurenov_page_is_not_a_result_announcement(self):
        result = classifier.classify(_device(P["edurenov"]))
        assert result.content_type != ContentType.RESULT_ANNOUNCEMENT
        assert result.application_mechanism

    def test_real_edurenov_page_is_not_rejected_by_the_gate(self):
        decision = DeviceQualityGate().evaluate(_device(P["edurenov"], device_type="aap"))
        assert decision.quality_state != "INVALID"
        assert decision.validation_status != "rejected"

    def test_results_only_page_is_still_a_result_announcement(self):
        result = classifier.classify({
            "title": "Résultats de l'appel à projets Innovation 2025",
            "short_description": "La Région publie les résultats de l'appel à projets : 40 lauréats sélectionnés parmi 300 dossiers.",
            "full_description": "Félicitations aux lauréats. La liste complète des projets retenus est disponible.",
        })
        assert result.content_type == ContentType.RESULT_ANNOUNCEMENT

    def test_programme_with_past_results_and_a_current_call_is_not_a_result(self):
        result = classifier.classify({
            "title": "Programme Innov'Ville : financer la rénovation des bâtiments publics",
            "short_description": "Innov'Ville accompagne les collectivités. Les lauréats 2024 ont été récompensés lors de la cérémonie de remise des prix.",
            "full_description": (
                "Retour sur les lauréats des éditions précédentes : 12 lauréats sélectionnés en 2023, 15 en 2024, palmarès complet en ligne. "
                "La Banque annonce la deuxième édition des défis : cette année, l'appel à projets destiné aux entreprises porte sur deux thématiques. "
                "L'appel à candidatures est ouvert jusqu'au 30 novembre 2026."
            ),
        })
        assert result.content_type != ContentType.RESULT_ANNOUNCEMENT

    def test_news_announcing_laureates_with_a_next_call_not_yet_open_stays_a_result(self):
        result = classifier.classify({
            "title": "Découvrez les lauréats 2025 du concours régional",
            "short_description": "Le jury a désigné les lauréats 2025. Félicitations aux gagnants sélectionnés parmi 200 candidatures.",
            "full_description": "Retour sur la cérémonie de remise des prix. Le prochain appel à candidatures sera ouvert à l'automne ; les dates seront annoncées prochainement.",
        })
        assert result.content_type == ContentType.RESULT_ANNOUNCEMENT
        assert not result.application_mechanism


# ════════════════════════════════════════════════════════════════════════════
# R8 — DIAGS AMORÇAGE RH: a call for experts is not a financing
# ════════════════════════════════════════════════════════════════════════════

class TestR8ProviderCalls:
    def test_real_page_is_not_typed_investissement(self):
        page = P["diags_rh"]
        taxonomy = classify_taxonomy({"title": page["title"], "short_description": page["text"][:400], "full_description": page["text"],
                                      "device_type": "autre"})
        assert taxonomy.device_type != "investissement"
        assert taxonomy.taxonomy_tag == "taxonomy:appel_prestataires"

    def test_real_page_is_not_a_financing_opportunity(self):
        page = P["diags_rh"]
        result = classifier.classify({"title": page["title"], "short_description": page["text"][:400], "full_description": page["text"]})
        assert result.content_type == ContentType.PUBLIC_PROCUREMENT
        assert "provider_selection" in result.signals

    @pytest.mark.parametrize("title,text", [
        ("Appel à experts évaluateurs", "Appel à experts pour évaluer les dossiers de l'appel à projets 2026. Rémunération à la vacation."),
        ("Référencement de consultants", "Bpifrance procède au référencement de consultants spécialisés en stratégie numérique."),
        ("Marché de prestation de services", "Marché de prestation de services de conseil : le titulaire du marché réalisera les diagnostics. Cahier des charges disponible."),
    ])
    def test_provider_calls_are_not_financing(self, title, text):
        assert classifier.classify({"title": title, "short_description": text}).content_type == ContentType.PUBLIC_PROCUREMENT
        assert classify_taxonomy({"title": title, "short_description": text, "device_type": "autre"}).device_type not in (
            "investissement", "subvention", "pret", "aap")

    def test_a_financial_aid_for_hr_in_smes_stays_a_financing(self):
        text = "Aide financière de 10 000 € pour recruter un responsable RH dans les PME de moins de 50 salariés. Dépôt des dossiers avant le 30 juin 2027."
        device = {"title": "Aide au recrutement RH des PME", "short_description": text, "device_type": "autre"}
        assert classifier.classify(device).content_type == ContentType.FINANCING_OPPORTUNITY
        assert classify_taxonomy(device).device_type == "subvention"

    def test_amorcage_alone_does_not_make_an_investment(self):
        assert classify_taxonomy({"title": "Prêt d'amorçage pour startups", "short_description": "Prêt d'amorçage", "device_type": "autre"}).device_type == "pret"


class TestR8EnglishRfpProviderCalls:
    """384 AGRA "RFP AGRA-XX-####" procurement notices were stuck as pending_review "subvention" (removed
    from production on 2026-10-01): the provider-call detection only covered French phrasing and a narrow
    English list, missing "Provision of ... services", "Consultancy for/to ...", "Request for Proposals"."""

    @pytest.mark.parametrize("title,text", [
        ("RFP AGRA-NB-1434-2", "Provision of co-sourced internal audit services: review of corporate process audits. "
                                "Deadline for submissions is 14 April 2026."),
        ("RFP AGRA-RW-1079", "Consultancy for media, communications and external engagement. Interested firms should "
                              "submit a technical and financial proposal before the closing date."),
        ("RFP AGRA-GH-1053", "Consultancy to strengthen inclusive regional trade in ECOWAS through actionable "
                              "non-tariff barriers reform."),
        ("RFP AGRA-RW-1078", "Africa Food Systems Forum 2026 - Local Service Provider. AGRA is seeking a local "
                              "service provider to support logistics for the forum."),
        ("Advertisement - RFP", "Request for Proposals: provision of facilitation services for a learning event. "
                                 "Bidders must submit by the deadline indicated."),
    ])
    def test_agra_style_rfp_is_public_procurement(self, title, text):
        device = {"title": title, "short_description": text, "full_description": text, "device_type": "subvention"}
        assert classifier.classify(device).content_type == ContentType.PUBLIC_PROCUREMENT
        assert classify_taxonomy(device).device_type not in ("subvention", "investissement", "pret", "aap")

    def test_a_genuine_call_for_grant_proposals_with_an_amount_stays_a_financing(self):
        """"Request for Proposals" is also how NGOs phrase an open grant competition: an explicit amount
        offered to applicants must keep it a financing opportunity, never procurement."""
        text = ("Request for Proposals: the foundation offers grants of up to $50,000 to support community "
                "projects. Proposals must be submitted before the deadline.")
        device = {"title": "Request for Proposals - Community Grants 2026", "short_description": text, "device_type": "autre"}
        assert classifier.classify(device).content_type == ContentType.FINANCING_OPPORTUNITY


class TestR8FrenchTenderReferenceCodes:
    """187 BOAD "AMI/AOON/AOOI N°..." tender notices (recrutement de consultant/bureau, fourniture de biens)
    were stuck in pending_review as subvention/aap/accompagnement - one even auto_published. The French
    provider-call patterns required spelled-out "appel à manifestation d'intérêt" or "référencement", never
    the abbreviated reference code BOAD and similar institutions actually use in their titles."""

    @pytest.mark.parametrize("title,text", [
        ("AOON N°041/2026/DAG/DPA/BOAD – Fourniture de cartes de visite digitales",
         "Fourniture de cartes de visite digitales (cartes et application d'administration) pour le siège de la BOAD."),
        ("AMI N° 2026/036/MCP – Recrutement de consultant",
         "Recrutement de consultant pour la réalisation d'étude de faisabilité des travaux de construction de deux échangeurs."),
        ("AMI N°008/AT2ER-PER172 – Recrutement de bureau chargé des prestations",
         "Recrutement de bureau chargé des prestations de suivi et évaluation de projet."),
        ("AOOI N° 08/2026/010/SOMAPEP SA – Réalisation de 9 765 branchements domiciliaires",
         "Avis d'appel d'offres pour la réalisation de 9 765 branchements domiciliaires."),
        ("AOON/N°034/2026/DAG/DPA/BOAD – Fourniture de consommables",
         "Fourniture de consommables et pièces informatiques pour le siège de la BOAD, exercice 2026."),
        ("AMI N°001/2026/DGD-FI/BOAD – Recrutement de consultant",
         "Recrutement de consultant pour le développement d'une solution de modélisation financière pour la BOAD. "
         "Les cabinets intéressés peuvent solliciter des informations complémentaires sur la mission."),
        ("AOOI N°002/APGB/F/2026 – Fourniture d'Équipements de manutention",
         "Fourniture d'équipements de manutention portuaire et services connexes pour le Port de Bissau."),
        ("AOOR N°2026-005/MESRI – Acquisition et installation d'équipements de laboratoire",
         "Acquisition et installation d'équipements de laboratoire de réalité virtuelle au profit de PCEP-UV/BF."),
        ("AOI N°2026-001/ONBAH/DG – Travaux de réhabilitation du périmètre irrigué",
         "Travaux de réhabilitation du périmètre irrigué et du barrage de Mogtédo dans la province du Ganzourgou."),
        ("AAOP N° 0004/2026/SoBAA/PRMP/DDA – Travaux de génie civil et de terrassement",
         "Travaux de génie civil et de terrassement pour l'aménagement de 983 ha, Lot 2."),
        ("Avis d'Appel d'Offres Ouvert National N°017/2026/DAG/DPA/BOAD – Fourniture de mobiliers",
         "Fourniture de mobiliers d'appoint pour le siège de la BOAD."),
        ("DAO – Recrutement d'un cabinet pour une formation sur la modélisation du risque de crédit",
         "La BOAD recrute un cabinet pour un séminaire de formation sur la maîtrise des risques opérationnels."),
        ("Avis de préqualification N 001_2025/SONABEL/PEQ/DP",
         "Acquisition, installation et mise en service d'un système de télésurveillance des postes de distribution."),
    ])
    def test_boad_style_tender_is_public_procurement(self, title, text):
        device = {"title": title, "short_description": text, "full_description": text, "device_type": "subvention"}
        assert classifier.classify(device).content_type == ContentType.PUBLIC_PROCUREMENT
        assert classify_taxonomy(device).device_type not in ("subvention", "investissement", "pret", "aap")

    def test_a_genuine_ami_funding_call_with_an_amount_stays_a_financing(self):
        """An AMI that itself offers funding to selected projects (not a reference-numbered BOAD-style tender,
        no "recrutement de consultant/bureau") must stay a financing opportunity."""
        text = ("Appel à manifestation d'intérêt : la fondation offre des subventions pouvant atteindre 5 000 000 FCFA "
                "aux porteurs de projets agricoles sélectionnés. Dépôt des dossiers avant le 30 juin 2027.")
        device = {"title": "AMI - Soutien aux porteurs de projets agricoles", "short_description": text, "device_type": "autre"}
        assert classifier.classify(device).content_type == ContentType.FINANCING_OPPORTUNITY


class TestR8BareEnglishTenderAbbreviations:
    """53 AGRA "AGRA-XX-####" / "RFQ AGRA-..." / "RFP-AGRA-..." tender references (a second AGRA source,
    agra.org/opportunities/procurement-notices/, not the one fixed earlier) were sitting in pending_review
    as subvention. Distinct from AGRA's genuine grant mechanism, "Request for Concept Notes (RFCN)" /
    "Request for Grant Applications (RFA)", which must stay a financing opportunity."""

    @pytest.mark.parametrize("title", [
        "(RFQ) AGRA-ML14",
        "RFQ AGRA -RW-1038",
        "RFP-AGRA-NB-1443",
        "Readvertising - RFP AGRA-US-1075-2",
    ])
    def test_bare_rfp_rfq_reference_code_is_public_procurement(self, title):
        device = {"title": title, "short_description": title, "full_description": title, "device_type": "subvention"}
        assert classifier.classify(device).content_type == ContentType.PUBLIC_PROCUREMENT
        assert classify_taxonomy(device).device_type not in ("subvention", "investissement", "pret", "aap")

    def test_a_genuine_rfcn_grant_call_with_an_amount_stays_a_financing(self):
        text = ("Request for Concept Notes (RFCN): the programme offers grants of up to $200,000 to NGOs "
                "and SMEs working on youth employment in agrifood systems. Concept notes must be submitted "
                "before the deadline indicated on the official page.")
        device = {"title": "Request for Concept Notes (RFCN): Unlocking Jobs for Africa's Rural Youth",
                  "short_description": text, "device_type": "subvention"}
        assert classifier.classify(device).content_type == ContentType.FINANCING_OPPORTUNITY


# ════════════════════════════════════════════════════════════════════════════
# R9 — INFERRED CURRENCY: never stored as if the source said it
# ════════════════════════════════════════════════════════════════════════════

MANUAL_SOURCE = {
    "id": "manual", "name": "Import manuel / historique", "organism": "Import manuel", "country": "International",
    "url": "https://www.service-public.fr", "level": 2, "collection_mode": "manual", "config": {},
}


class TestR9Currency:
    def test_no_money_means_no_currency(self):
        r = engine.extract("Aide aux PME dans le secteur numérique. Contacter l'antenne régionale.", country="Côte d'Ivoire")
        assert r.currency is None and r.currency_source is None
        assert r.currency_inferred == "XOF"

    def test_arce_never_becomes_usd(self):
        page = P["arce"]
        item = RawItem(title=page["title"], url=page["url"], raw_content=page["text"], metadata={})
        payload = Normalizer(MANUAL_SOURCE).normalize(item)
        assert payload["currency"] is None
        assert payload["_currency_inferred"] == "USD"          # kept for internal use only, distinct from the source currency
        assert payload["amount_min"] is None and payload["amount_max"] is None

    def test_explicit_currency_is_the_source_currency(self):
        r = engine.extract("Subvention jusqu'à 50 000 EUR par projet.", country="Côte d'Ivoire")
        assert (r.currency, r.currency_source) == ("EUR", "EUR")
        assert r.currency_inferred == "EUR"

    def test_bare_amount_keeps_the_amount_but_not_a_guessed_currency(self):
        r = engine.extract("Aide aux PME ivoiriennes. Montant max 10 000 000.", country="Côte d'Ivoire")
        assert r.amount_max == 10_000_000
        assert r.currency is None
        assert r.currency_inferred == "XOF"

    def test_schema_keeps_a_null_currency_null(self):
        device = DeviceCreate(title="Aide test", organism="Org", country="France", device_type="autre", source_url="https://example.org/a",
                              short_description="Aide de test pour les PME.", currency=None)
        assert device.currency is None
        assert DeviceCreate(title="Aide test", organism="Org", country="France", device_type="autre", source_url="https://example.org/a",
                            short_description="Aide de test pour les PME.").currency is None

    @pytest.mark.parametrize("page", ["faij", "papsgouv"])
    def test_real_francophone_pages_have_no_invented_currency_without_amounts(self, page):
        r = engine.extract(P[page]["text"], country="Burkina Faso")
        if not (r.amount_min or r.amount_max):
            assert r.currency is None


# ════════════════════════════════════════════════════════════════════════════
# BEE CAUSE (pre-existing): thousands vs millions, no source-specific code
# ════════════════════════════════════════════════════════════════════════════

GSO_SOURCE = {
    "id": "gso", "name": "Global South Opportunities - Funding", "organism": "Global South Opportunities", "country": "International",
    "url": "https://www.globalsouthopportunities.com/category/funding/feed/", "level": 3, "collection_mode": "rss", "config": {},
}


def gso_normalize(title, body):
    from app.collector.base_connector import RawItem
    raw = RawItem(title=title, url="https://www.globalsouthopportunities.com/2026/01/x/", raw_content=body, source_id="gso", metadata={})
    return Normalizer(GSO_SOURCE).normalize(raw)


class TestGsoAmountsGoThroughRoles:
    """A source-specific parser must never write amount_min/amount_max: the role layer decides."""

    def test_total_fund_is_program_budget_not_beneficiary_amount(self):
        n = gso_normalize("Applications are open for the Health Fund 2026", "The Health Fund is a EUR fund. €2 Million Funding is available in total for innovative projects in Africa. Apply before 30 June 2026 on the official website.")
        assert n["_program_budget"] == 2_000_000
        assert n["amount_max"] is None and n["amount_min"] is None
        assert n["currency"] == "EUR"

    def test_grants_up_to_per_winner(self):
        n = gso_normalize("Innovation Prize", "Grants up to $20,000 per winner are offered to young entrepreneurs. Apply before 30 June 2026 on the website.")
        assert n["amount_max"] == 20_000 and n["currency"] == "USD"

    def test_grant_per_organisation(self):
        n = gso_normalize("Community Grants", "A $2,000 grant per organisation is offered to schools. Apply before 30 June 2026 on the website.")
        assert n["amount_max"] == 2_000

    def test_fund_and_grant_ceiling(self):
        n = gso_normalize("Youth Fund", "A $5 million fund will provide grants of up to $50,000 to young founders. Apply before 30 June 2026 on the website.")
        assert n["_program_budget"] == 5_000_000
        assert n["amount_max"] == 50_000

    def test_million_elsewhere_never_multiplies_beneficiary_amount(self):
        n = gso_normalize("Student Grants", "The programme has supported 1 million students and offers grants up to $2,000 to schools. Apply before 30 June 2026 on the website.")
        assert n["amount_max"] == 2_000

    def test_no_parser_writes_money_fields(self):
        import inspect
        src = inspect.getsource(Normalizer)
        assert 'result["amount_max"]' not in src and 'result["currency"]' not in src

    def test_extra_fields_cannot_override_money(self):
        from app.collector.normalizer import _AMOUNT_OWNED_FIELDS
        assert {"amount_min", "amount_max", "funding_rate", "currency"} <= set(_AMOUNT_OWNED_FIELDS)

    def test_bee_cause_real_page(self):
        page = P["bee_cause"]
        n = gso_normalize(page["title"], page["text"])
        assert n["amount_max"] == 2_000


class TestBeeCauseAmountScale:
    @pytest.mark.parametrize("text,value", [("$2,000", 2_000), ("$20,000", 20_000), ("$2 million", 2_000_000), ("$2M", 2_000_000), ("2,000,000 USD", 2_000_000)])
    def test_shared_money_parser_scale(self, text, value):
        assert parse_money(text) == [(value, "USD")]

    def test_engine_on_the_real_page(self):
        r = engine.extract(f"{P['bee_cause']['title']} {P['bee_cause']['text']}", country="États-Unis")
        assert r.amount_max == 2_000


# ════════════════════════════════════════════════════════════════════════════
# NON-REGRESSION: improvements obtained in SQ1.1 must be kept
# ════════════════════════════════════════════════════════════════════════════

class TestKeepPreviousImprovements:
    def test_pret_boost_range(self):
        r = engine.extract(P["pret_boost"]["text"], country="France")
        assert (r.amount_min, r.amount_max, r.currency) == (5_000, 75_000, "EUR")

    def test_frg_guarantee(self):
        r = engine.extract(P["frg"]["text"], country="France")
        assert (r.amount_max, r.funding_rate) == (1_000_000, 70.0)

    def test_innowwide_grant_and_rate(self):
        r = engine.extract(P["innowwide"]["text"], country="France")
        assert (r.amount_max, r.funding_rate) == (60_000, 70.0)

    def test_kitty_carr_amount(self):
        r = engine.extract(f"{P['kitty_carr']['title']} {P['kitty_carr']['text']}", country="États-Unis")
        assert (r.amount_max, r.currency) == (20_000, "USD")

    def test_faij_xof_range_is_a_sourced_currency(self):
        r = engine.extract(P["faij"]["text"], country="Burkina Faso")
        assert (r.amount_min, r.amount_max, r.currency) == (200_000, 2_000_000, "XOF")

    def test_cir_expense_cap_distinction_is_kept(self):
        r = engine.extract("crédit d'impôt de 30 % des dépenses éligibles dans la limite de 100 M€ de dépenses", country="France")
        assert (r.funding_rate, r.eligible_expense_cap, r.amount_max) == (30.0, 100_000_000, None)

    def test_institutional_projects_are_still_sent_to_review(self):
        page = P["wb_resilience"]
        decision = DeviceQualityGate().evaluate({
            "title": page["title"], "source_url": page["url"], "short_description": page["text"][:300], "full_description": page["text"],
            "status": "open", "is_recurring": False, "close_date": "2031-06-30", "country": "Burkina Faso", "device_type": "institutional_project",
        })
        assert decision.quality_state == "REVIEW_REQUIRED"

    def test_non_financial_support_is_still_detected(self):
        page = P["papsgouv"]
        result = classifier.classify({"title": page["title"], "short_description": page["text"], "device_type": "accompagnement"})
        assert result.content_type == ContentType.NON_FINANCIAL_SUPPORT

    def test_a_real_subsidy_rate_and_ceiling_still_produce_both(self):
        r = engine.extract("Subvention de 70 % des dépenses, dans la limite de 100 000 €.", country="France")
        assert (r.funding_rate, r.amount_max) == (70.0, 100_000)


class TestAmountLabelKeepsUnitTogether:
    """Descriptive label: number + multiplier + currency is one semantic unit, never cut at the multiplier."""

    @pytest.mark.parametrize("text,expected", [
        ("Funding of €2 Million is available", "€2 Million"),
        ("A $5 million fund", "$5 million"),
        ("Budget de 2 M€ pour le programme", "2 M€"),
        ("Enveloppe de 2,5 milliards d'euros pour des prêts", "2,5 milliards d'euros"),
        ("Grants of $20,000 each", "$20,000"),
        ("Un prêt de 500 000 FCFA maximum", "500 000 FCFA"),
        ("Loans of 1.5M USD", "1.5 M USD"),
        ("Grants up to €2 Million Funding", "€2 Million"),
    ])
    def test_label_is_not_truncated(self, text, expected):
        label = Normalizer(GSO_SOURCE)._extract_amount_label(text)
        assert label == expected

    def test_two_million_funding_never_yields_a_fragment(self):
        n = gso_normalize("Applications are open for the Health Fund 2026: €2 Million Funding",
                          "The Health Fund is a EUR fund. €2 Million Funding is available in total for innovative projects in Africa. Apply before 30 June 2026 on the official website.")
        texts = " ".join(str(n.get(k) or "") for k in ("funding_details", "short_description", "full_description", "title"))
        assert "€2." not in texts and "€2 ." not in texts
        assert n["_program_budget"] == 2_000_000 and n["amount_max"] is None and n["amount_min"] is None
