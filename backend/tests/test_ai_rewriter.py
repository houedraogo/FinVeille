from datetime import date

import pytest

from app.config import settings
from app.services.ai_rewriter import (
    AIRewriter,
    REWRITE_FAILED,
    build_rewrite_prompt,
    validate_rewritten_sections,
)


def make_device(**overrides):
    payload = {
        "title": "Concours i-PhD",
        "organism": "Bpifrance",
        "country": "France",
        "device_type": "aap",
        "status": "open",
        "close_date": date(2026, 4, 30),
        "amount_min": None,
        "amount_max": None,
        "currency": "EUR",
        "content_sections_json": [
            {
                "key": "presentation",
                "title": "Presentation",
                "content": "Le concours i-PhD accompagne les jeunes chercheurs vers la creation de startup deeptech.",
            },
            {
                "key": "eligibility",
                "title": "Criteres d'eligibilite",
                "content": "Doctorants a partir de la deuxieme annee ou docteurs depuis moins de cinq ans.",
            },
            {
                "key": "funding",
                "title": "Montant / avantages",
                "content": "Programme d'accompagnement. Montant a confirmer sur la source officielle.",
            },
            {"key": "calendar", "title": "Calendrier", "content": "Cloture : 30/04/2026."},
            {"key": "procedure", "title": "Demarche", "content": "Depot du dossier sur la source officielle."},
            {"key": "checks", "title": "Points a verifier", "content": "Montant a confirmer."},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_rewriter_fails_cleanly_when_ai_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    result = await AIRewriter().rewrite_device(make_device())

    assert result.status == REWRITE_FAILED
    assert result.sections == []
    assert "ia_non_configuree" in result.issues


def test_rewrite_prompt_contains_strict_no_invention_instruction():
    prompt = build_rewrite_prompt(make_device(), make_device()["content_sections_json"])

    assert "N'invente aucune information" in prompt
    assert "Retourne uniquement un objet JSON valide" in prompt
    assert "Concours i-PhD" in prompt


def test_rewritten_sections_need_review_when_deadline_disappears():
    rewritten = [
        {
            "key": "presentation",
            "title": "Presentation",
            "content": "Ce concours accompagne les jeunes chercheurs dans leur projet entrepreneurial deeptech.",
        },
        {"key": "eligibility", "title": "Criteres d'eligibilite", "content": "Jeunes chercheurs eligibles."},
        {"key": "funding", "title": "Montant / avantages", "content": "Montant a confirmer."},
        {"key": "calendar", "title": "Calendrier", "content": "Date limite a confirmer."},
        {"key": "procedure", "title": "Demarche", "content": "Consulter la source officielle."},
        {"key": "checks", "title": "Points a verifier", "content": "Verifier les conditions."},
    ]

    issues = validate_rewritten_sections(rewritten, make_device()["content_sections_json"], make_device())

    assert "date_limite_absente_de_la_reformulation" in issues


def test_rewritten_sections_pass_when_expected_sections_and_deadline_are_present():
    rewritten = [
        {
            "key": "presentation",
            "title": "Presentation",
            "content": "Le concours i-PhD accompagne les jeunes chercheurs qui souhaitent creer une startup deeptech a partir de leurs travaux de recherche.",
        },
        {
            "key": "eligibility",
            "title": "Criteres d'eligibilite",
            "content": "Il s'adresse aux doctorants a partir de la deuxieme annee et aux docteurs ayant soutenu depuis moins de cinq ans.",
        },
        {
            "key": "funding",
            "title": "Montant / avantages",
            "content": "Le dispositif apporte un accompagnement. Le montant financier reste a confirmer sur la source officielle.",
        },
        {"key": "calendar", "title": "Calendrier", "content": "La cloture est indiquee au 30/04/2026."},
        {"key": "procedure", "title": "Demarche", "content": "La candidature doit etre deposee depuis la source officielle."},
        {
            "key": "checks",
            "title": "Points a verifier",
            "content": "Verifier la dotation financiere et les pieces attendues avant de candidater.",
        },
    ]

    issues = validate_rewritten_sections(rewritten, make_device()["content_sections_json"], make_device())

    assert issues == []
