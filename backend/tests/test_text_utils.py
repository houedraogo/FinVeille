from datetime import date, timedelta

from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    dedupe_text_fields,
    derive_device_status,
    extract_cdata_text,
    extract_close_date,
    has_recurrence_evidence,
    localize_investment_text,
    looks_english_text,
    sanitize_text,
)


def test_extract_cdata_text_unwraps_serialized_payload():
    raw = "{'cdata!': 'The development objective of the project is to improve access to energy.'}"
    cleaned = extract_cdata_text(raw)

    assert "development objective" in cleaned
    assert "cdata" not in cleaned.lower()


def test_sanitize_text_cleans_cdata_and_entities():
    raw = "{'cdata!': 'Energy &amp; climate support project'}"

    assert sanitize_text(raw) == "Energy & climate support project"


def test_sanitize_text_cleans_cdata_with_mixed_quotes():
    raw = """'cdata!': "The Third Urban Development Project improves access to services." """

    assert sanitize_text(raw) == "The Third Urban Development Project improves access to services."


def test_sanitize_text_cleans_truncated_cdata_prefix():
    raw = """{'cdata!': 'The Third Urban Development Project improves access to services"""

    assert sanitize_text(raw) == "The Third Urban Development Project improves access to services"


def test_sanitize_text_strips_html_and_decodes_entities():
    raw = "<p>Montant&nbsp;: <strong>50 000 &amp;euro;</strong></p>"

    assert sanitize_text(raw) == "Montant : 50 000 &euro;"


def test_clean_editorial_text_restores_spaces_between_words_and_dates():
    raw = "La date limite est fixée au28 avril 2026.Retour avant01/05/2026."

    cleaned = clean_editorial_text(raw)

    assert "au 28 avril 2026." in cleaned
    assert "avant 01/05/2026." in cleaned


def test_looks_english_text_detects_english_sentence():
    assert looks_english_text("The project supports climate resilience and energy access for rural communities.")


def test_looks_english_text_ignores_french_sentence():
    assert not looks_english_text("Le projet soutient la résilience climatique et l'accès à l'énergie pour les zones rurales.")


def test_derive_device_status_marks_expired_for_past_date():
    past_date = date.today() - timedelta(days=1)

    assert derive_device_status(past_date, "open") == "expired"


def test_derive_device_status_keeps_recurring_when_future_date_exists():
    future_date = date.today() + timedelta(days=10)

    assert derive_device_status(future_date, "recurring") == "recurring"


def test_extract_close_date_parses_numeric_deadline():
    value = extract_close_date("Date limite : 24/04/2026")

    assert value == date(2026, 4, 24)


def test_extract_close_date_parses_literal_deadline():
    value = extract_close_date("Clôture le 15 mars 2027 pour le dépôt final.")

    assert value == date(2027, 3, 15)


def test_extract_close_date_parses_english_closing_date():
    value = extract_close_date("Closing date: 30/09/2026")

    assert value == date(2026, 9, 30)


def test_extract_close_date_parses_iso_date_from_serialized_metadata():
    value = extract_close_date('{"date_de_fin_du_projet":"2017-12-27"}')

    assert value == date(2017, 12, 27)


def test_extract_close_date_parses_french_application_range_end_date():
    value = extract_close_date("Appel a candidatures ouvert du 1er avril au 30 mai 2026.")

    assert value == date(2026, 5, 30)


def test_localize_investment_text_rewrites_common_english_phrases_in_french():
    raw = "## Investment focus\nThe fund invests in startups and SMEs across Africa. Ticket size: 100k to 500k."

    localized = localize_investment_text(raw)

    assert "## Présentation" in localized
    assert "secteurs" not in localized.lower() or "cible" in localized.lower() or "fonds d'investissement" in localized.lower()
    assert "Afrique" in localized
    assert "ticket d'investissement" in localized.lower()
    assert "Investment focus" not in localized
    assert "The fund invests" not in localized


def test_dedupe_text_fields_removes_funding_when_already_in_full_description():
    short, full, funding, eligibility = dedupe_text_fields(
        "Concours panafricain pour entrepreneurs.",
        "## Présentation\nConcours panafricain pour entrepreneurs.\n\n## Récompenses\nDotation de 1,5 million de dollars partagée entre les finalistes.",
        "Dotation de 1,5 million de dollars partagée entre les finalistes.",
        "Ouvert aux entrepreneurs africains.",
    )

    assert short == "Concours panafricain pour entrepreneurs."
    assert full is not None
    assert funding is None
    assert eligibility == "Ouvert aux entrepreneurs africains."


def test_build_structured_sections_creates_all_business_sections_with_fallbacks():
    value = build_structured_sections(
        presentation="Dispositif de soutien a l'innovation pour les PME.",
        eligibility="PME implantee en France avec projet innovant.",
        funding="Subvention jusqu'a 30 000 EUR.",
        close_date=date(2026, 6, 15),
        procedure=None,
    )

    assert value is not None
    assert "## Presentation" in value
    assert "## Criteres d'eligibilite" in value
    assert "## Montant / avantages" in value
    assert "## Calendrier" in value
    assert "- Cloture : 15/06/2026" in value
    assert "## Demarche" in value
    assert "source officielle" in value


def test_build_contextual_eligibility_uses_beneficiaries_and_scope():
    value = build_contextual_eligibility(
        text="Aide regionale pour soutenir les entreprises industrielles dans leurs investissements.",
        beneficiaries=["PME", "ETI"],
        country="France",
        geographic_scope="regional",
    )

    assert "pme et eti" in value.lower()
    assert "echelle regionale" in value.lower()
    assert "source officielle" in value.lower()


def test_build_contextual_funding_reuses_financing_sentence_when_present():
    value = build_contextual_funding(
        text="Le dispositif prend en charge 50 % des depenses eligibles dans la limite de 20 000 EUR.",
        device_type="subvention",
    )

    assert "50 %" in value
    assert "20 000 EUR" in value or "20 000 eur" in value.lower()


def test_has_recurrence_evidence_detects_open_ended_program():
    assert has_recurrence_evidence("Ce dispositif est ouvert en continu, sans date limite de depot.")


def test_has_recurrence_evidence_ignores_standard_open_call():
    assert not has_recurrence_evidence("Appel a projets en cours pour soutenir l'innovation des PME.")
