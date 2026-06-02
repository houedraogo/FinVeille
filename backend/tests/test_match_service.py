from datetime import datetime, timedelta, timezone

from app.services.match_service import (
    _normalize_chatgpt_profile,
    _score_fallback_row,
    analyse_text,
    analyse_text_with_chatgpt,
)


def test_analyse_text_detects_fintech_investment_profile():
    profile = analyse_text(
        "Fintech ivoirienne de paiements pour PME en phase seed. "
        "Nous recherchons des investisseurs venture capital pour accelerer en Afrique de l'Ouest."
    )

    assert "finance" in profile["sectors"]
    assert "numerique" in profile["sectors"]
    assert profile["dominant_type"] == "investissement"
    assert any(country in profile["countries"] for country in ["Côte d'Ivoire", "Afrique de l'Ouest", "Afrique"])


def test_fallback_score_penalizes_low_quality_sources():
    profile = {
      "keywords": ["fintech", "paiement"],
      "countries": ["France"],
      "country_scopes": ["France", "Europe", "International"],
      "types": ["investissement"],
      "dominant_type": "investissement",
      "sectors": ["finance", "numerique"],
      "amount_min": None,
      "amount_max": None,
    }
    strong_row = {
      "title": "Fonds fintech seed",
      "description_courte": "Investissement seed pour fintech",
      "sectors": ["finance", "numerique"],
      "country": "France",
      "region": "France",
      "zone": None,
      "geographic_scope": None,
      "device_type": "investissement",
      "amount_min": None,
      "amount_max": None,
      "source_reliability": 5,
      "source_errors": 0,
      "source_is_active": True,
      "source_last_success_at": datetime.now(timezone.utc) - timedelta(days=2),
      "last_verified_at": datetime.now(timezone.utc) - timedelta(days=3),
    }
    weak_row = {
      **strong_row,
      "source_reliability": 2,
      "source_errors": 4,
      "source_is_active": False,
      "source_last_success_at": datetime.now(timezone.utc) - timedelta(days=180),
      "last_verified_at": datetime.now(timezone.utc) - timedelta(days=200),
    }

    assert _score_fallback_row(strong_row, profile) > _score_fallback_row(weak_row, profile)


def test_fallback_score_penalizes_investment_fund_outside_selected_country_scope():
    profile = {
        "keywords": ["fintech"],
        "countries": ["Bénin"],
        "country_scopes": ["Bénin", "Afrique", "Afrique de l'Ouest", "International", "France / Afrique"],
        "types": ["investissement"],
        "dominant_type": "investissement",
        "sectors": ["finance"],
        "amount_min": None,
        "amount_max": None,
    }
    africa_fund = {
        "title": "Fonds africain fintech",
        "description_courte": "Investissement fintech en Afrique",
        "sectors": ["finance"],
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "investissement",
        "amount_min": None,
        "amount_max": None,
        "source_reliability": 5,
        "source_errors": 0,
        "source_is_active": True,
        "source_last_success_at": datetime.now(timezone.utc),
        "last_verified_at": datetime.now(timezone.utc),
    }
    france_fund = {
        **africa_fund,
        "title": "Fonds France fintech",
        "country": "France",
        "region": "Europe",
        "zone": None,
        "geographic_scope": None,
    }

    assert _score_fallback_row(africa_fund, profile) > 0
    assert _score_fallback_row(france_fund, profile) < _score_fallback_row(africa_fund, profile)
    assert _score_fallback_row(france_fund, profile) <= 0


def test_normalize_chatgpt_profile_keeps_allowed_precise_values():
    heuristic = analyse_text(
        "Fintech de paiement au Burkina Faso cherchant une subvention ou un programme d'accompagnement."
    )
    profile = _normalize_chatgpt_profile(
        {
            "summary": "Plateforme fintech de paiement pour PME.",
            "sectors": ["finance", "numerique", "secteur-inconnu"],
            "countries": ["Burkina Faso", "Atlantide"],
            "types": ["subvention", "accompagnement"],
            "dominant_type": "subvention",
            "amount_min": 25000,
            "amount_max": 100000,
            "keywords": ["fintech", "paiement", "pme", "startup", "document"],
            "project_stage": "amorçage",
            "business_model": "commission sur transactions",
            "target_customers": "PME",
            "evidence": ["paiement pour PME", "Burkina Faso"],
            "missing_information": ["chiffre d'affaires"],
            "confidence": 88,
        },
        heuristic,
    )

    assert profile["analysis_provider"] == "openai"
    assert profile["sectors"] == ["finance", "numerique"]
    assert profile["countries"] == ["Burkina Faso"]
    assert profile["dominant_type"] == "subvention"
    assert profile["amount_min"] == 25000
    assert "document" not in profile["keywords"]
    assert profile["confidence"] == 88


async def test_analyse_text_with_chatgpt_uses_openai_payload(monkeypatch):
    async def fake_call(raw_text, heuristic):
        return {
            "summary": "Startup solaire au Bénin pour électrifier des PME rurales.",
            "sectors": ["energie"],
            "countries": ["Bénin"],
            "types": ["subvention", "accompagnement"],
            "dominant_type": "subvention",
            "amount_min": None,
            "amount_max": None,
            "keywords": ["solaire", "electrification", "pme", "rural"],
            "project_stage": "pilote",
            "business_model": "vente et maintenance de kits solaires",
            "target_customers": "PME rurales",
            "evidence": ["kits solaires", "Bénin"],
            "missing_information": ["budget exact"],
            "confidence": 91,
        }

    monkeypatch.setattr("app.services.match_service._call_openai_match_analysis", fake_call)

    profile = await analyse_text_with_chatgpt("Projet solaire au Bénin pour PME rurales.")

    assert profile["analysis_provider"] == "openai"
    assert profile["analysis_model"]
    assert profile["sectors"] == ["energie"]
    assert profile["countries"] == ["Bénin"]
    assert profile["dominant_type"] == "subvention"
