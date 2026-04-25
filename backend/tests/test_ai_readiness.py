from app.services.ai_readiness import (
    AI_CAUTION,
    AI_READY,
    AI_REVIEW,
    AI_UNUSABLE,
    compute_ai_readiness,
)


def make_sections():
    return [
        {"key": "presentation", "title": "Presentation", "content": "Presentation detaillee du dispositif et de ses objectifs principaux."},
        {"key": "eligibility", "title": "Eligibilite", "content": "PME, associations et porteurs de projets eligibles avec un dossier complet."},
        {"key": "funding", "title": "Montant", "content": "Subvention pouvant atteindre 50 000 EUR selon la nature du projet."},
        {"key": "calendar", "title": "Calendrier", "content": "Cloture : 30/09/2026."},
        {"key": "procedure", "title": "Demarche", "content": "La candidature se fait en ligne via la source officielle."},
        {"key": "official_source", "title": "Source officielle", "content": "Source de reference : organisme officiel."},
        {"key": "checks", "title": "Points a verifier", "content": "Verifier les conditions definitives sur le site officiel."},
    ]


def make_device(**overrides):
    payload = {
        "title": "Aide a l'innovation",
        "source_url": "https://example.org/aide",
        "short_description": "Resume utile et assez detaille pour decrire clairement le dispositif et son public cible.",
        "full_description": "Description longue et structuree du dispositif avec presentation, conditions, financement, calendrier et demarche. " * 5,
        "content_sections_json": make_sections(),
        "eligibility_criteria": "PME, associations et porteurs de projets eligibles avec un dossier complet et une situation reguliere.",
        "funding_details": "Subvention pouvant atteindre 50 000 EUR selon la nature du projet.",
        "amount_max": 50000,
        "close_date": "2026-09-30",
        "status": "open",
        "device_type": "subvention",
        "validation_status": "auto_published",
        "tags": ["deadline:known", "taxonomy:subvention"],
    }
    payload.update(overrides)
    return payload


def make_source(**overrides):
    payload = {
        "name": "Source officielle",
        "reliability": 5,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def test_ai_readiness_marks_rich_device_ready():
    readiness = compute_ai_readiness(make_device(), make_source())

    assert readiness.label == AI_READY
    assert readiness.score >= 80
    assert "date_limite_fiable" in readiness.reasons
    assert "criteres_presents" in readiness.reasons


def test_ai_readiness_uses_caution_when_deadline_is_not_communicated():
    readiness = compute_ai_readiness(
        make_device(close_date=None, status="standby", tags=["deadline:not_communicated", "taxonomy:subvention"]),
        make_source(reliability=4),
    )

    assert readiness.label in {AI_CAUTION, AI_REVIEW}
    assert "cloture_non_communiquee" in readiness.reasons


def test_ai_readiness_caps_english_content_below_ready():
    readiness = compute_ai_readiness(
        make_device(
            short_description="The program supports startups with funding and mentoring across Africa.",
            full_description="The program supports entrepreneurs with funding, mentoring, guidance and application support across Africa. " * 4,
        ),
        make_source(),
    )

    assert readiness.label != AI_READY
    assert "texte_anglais_restant" in readiness.reasons


def test_ai_readiness_rejects_unusable_pages():
    readiness = compute_ai_readiness(
        make_device(
            validation_status="rejected",
            short_description="Aucun contenu editorial exploitable trouve sur cette page.",
            source_raw="Impossible d'acceder a l'URL (404).",
        ),
        make_source(),
    )

    assert readiness.label == AI_UNUSABLE
    assert readiness.score == 0


def test_ai_readiness_sends_missing_source_and_url_to_review():
    readiness = compute_ai_readiness(
        make_device(source_url="", tags=["deadline:known", "taxonomy:subvention"]),
        None,
    )

    assert readiness.label in {AI_CAUTION, AI_REVIEW}
    assert "source_non_rattachee" in readiness.reasons
    assert "url_non_fiable" in readiness.reasons


def test_ai_readiness_caps_when_funding_is_only_to_confirm():
    sections = make_sections()
    for section in sections:
        if section["key"] == "funding":
            section["content"] = "Le montant ou les avantages ne sont pas precises clairement par la source."

    readiness = compute_ai_readiness(
        make_device(
            amount_max=None,
            funding_details="",
            content_sections_json=sections,
        ),
        make_source(),
    )

    assert readiness.label == AI_CAUTION
    assert readiness.score <= 79
    assert "montant_a_confirmer" in readiness.reasons


def test_ai_readiness_caps_when_funding_is_absent():
    sections = make_sections()
    sections = [section for section in sections if section["key"] != "funding"]

    readiness = compute_ai_readiness(
        make_device(
            amount_max=None,
            funding_details="",
            content_sections_json=sections,
        ),
        make_source(),
    )

    assert readiness.label == AI_CAUTION
    assert readiness.score <= 79
    assert "montant_absent" in readiness.reasons
