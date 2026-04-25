from app.services.taxonomy_classifier import classify_taxonomy


def make_device(**overrides):
    payload = {
        "title": "Aide a l'innovation",
        "organism": "Kafundo",
        "device_type": "autre",
        "short_description": "Soutenir les entreprises dans leur projet.",
        "full_description": "",
        "funding_details": "",
        "status": "standby",
        "is_recurring": False,
    }
    payload.update(overrides)
    return payload


def test_detects_investment_fund():
    result = classify_taxonomy(
        make_device(
            title='Fonds d’Investissement "Croissance et Proximité 2"',
            short_description="Faire entrer au capital des entreprises le fonds d'investissement regional.",
        )
    )

    assert result.device_type == "investissement"
    assert result.confidence >= 55


def test_detects_credit_bail_as_loan():
    result = classify_taxonomy(make_device(title="Credit-Bail Immobilier"))

    assert result.device_type == "pret"


def test_detects_diagnostic_as_support():
    result = classify_taxonomy(make_device(title="Diag Data IA", short_description="Diagnostic et conseil avec un expert."))

    assert result.device_type == "accompagnement"


def test_detects_world_bank_as_institutional_project():
    result = classify_taxonomy(
        make_device(title="Mali Education Project"),
        {"name": "Banque Mondiale - projets Mali", "organism": "World Bank Group", "url": "https://worldbank.org"},
    )

    assert result.device_type == "institutional_project"
    assert result.taxonomy_tag == "taxonomy:projet_institutionnel"


def test_keeps_unclear_type_to_qualify():
    result = classify_taxonomy(make_device(title="Programme territorial"))

    assert result.device_type == "autre"
    assert result.taxonomy_tag == "taxonomy:a_qualifier"
    assert result.confidence < 55
