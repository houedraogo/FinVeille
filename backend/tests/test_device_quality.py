from app.services.device_quality import DeviceQualityGate


def make_device(**overrides):
    payload = {
        "title": "Aide a l'innovation",
        "source_url": "https://example.org/aide",
        "short_description": "Resume utile et assez detaille pour decrire clairement le dispositif, son objectif et son public cible.",
        "full_description": (
            "Description longue avec plusieurs informations structurees sur le dispositif, ses objectifs, "
            "ses modalites, le contexte et la facon dont il peut etre mobilise par les beneficiaires."
        ),
        "eligibility_criteria": "PME implantee en France avec projet innovant eligible, situation reguliere et dossier complet.",
        "funding_details": "Subvention jusqu'a 30 000 EUR. Montant a confirmer selon le projet.",
        "close_date": "2026-06-30",
        "status": "open",
        "is_recurring": False,
    }
    payload.update(overrides)
    return payload


def test_quality_gate_publishes_rich_device():
    gate = DeviceQualityGate()

    decision = gate.evaluate(make_device())

    assert decision.decision == "publish"
    assert decision.validation_status == "auto_published"
    assert decision.score >= 70


def test_quality_gate_sends_open_without_close_date_to_review():
    gate = DeviceQualityGate()

    decision = gate.evaluate(make_device(close_date=None, funding_details="Montant a confirmer.", full_description="Description assez longue " * 20))

    assert decision.decision == "pending_review"
    assert decision.validation_status == "pending_review"
    assert "open_without_close_date" in decision.reasons


def test_quality_gate_rejects_too_poor_device():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            short_description="Aide.",
            full_description="",
            eligibility_criteria="",
            funding_details="",
            close_date=None,
            source_url="https://example.org/aide",
        )
    )

    assert decision.decision == "reject"
    assert decision.validation_status == "rejected"


def test_quality_gate_flags_remaining_english_content():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            short_description="The program supports startups with financing and mentoring across Africa.",
            full_description="The program supports startups with financing, mentoring and expert guidance across Africa.",
        )
    )

    assert decision.decision == "pending_review"
    assert decision.validation_status == "pending_review"
    assert "english_content_remaining" in decision.reasons
