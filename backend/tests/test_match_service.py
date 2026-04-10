from datetime import datetime, timedelta, timezone

from app.services.match_service import _score_fallback_row, analyse_text


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
