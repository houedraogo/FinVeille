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


def test_quality_gate_keeps_weak_summary_pending_even_with_other_fields():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            short_description="Aide courte.",
            full_description="Description longue avec contenu metier exploitable. " * 10,
            eligibility_criteria="PME eligibles avec dossier complet et activite conforme aux criteres du programme.",
            funding_details="Subvention jusqu'a 25 000 EUR selon le projet.",
        )
    )

    assert decision.decision == "pending_review"
    assert decision.validation_status == "pending_review"
    assert "insufficient_summary_for_auto_publish" in decision.reasons


def test_quality_gate_keeps_recurring_without_evidence_pending():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            status="recurring",
            is_recurring=False,
            close_date=None,
            recurrence_notes=None,
        )
    )

    assert decision.decision == "pending_review"
    assert "recurring_without_evidence" in decision.reasons


def test_quality_gate_rejects_unusable_source_page():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            short_description="Aucun contenu editorial exploitable trouve sur cette page.",
            full_description="Le site peut utiliser du JavaScript dynamique ou une structure HTML trop pauvre.",
            source_raw="Impossible d'acceder a l'URL (404).",
        )
    )

    assert decision.decision == "reject"
    assert decision.validation_status == "rejected"
    assert "unusable_source_page" in decision.reasons


def test_quality_gate_requires_business_proof_before_auto_publish():
    gate = DeviceQualityGate()

    decision = gate.evaluate(
        make_device(
            full_description="Description assez longue et propre sur le programme et son contexte. " * 8,
            eligibility_criteria="",
            funding_details="",
            close_date=None,
            status="standby",
            is_recurring=False,
        )
    )

    assert decision.decision == "pending_review"
    assert decision.validation_status == "pending_review"
    assert "insufficient_business_proof" in decision.reasons


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
