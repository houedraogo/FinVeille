from app.routers.devices import resolve_onboarding_result_filters
from app.services.device_service import DeviceService


def test_onboarding_keeps_direct_result_filters_when_matches_exist():
    total, result_types = resolve_onboarding_result_filters(
        total=11,
        institutional_total=33,
        device_types=["subvention", "aap", "concours"],
    )

    assert total == 11
    assert result_types == ["subvention", "aap", "concours"]


def test_onboarding_opens_institutional_signals_when_direct_matches_are_empty():
    total, result_types = resolve_onboarding_result_filters(
        total=0,
        institutional_total=33,
        device_types=["subvention", "aap", "concours"],
    )

    assert total == 33
    assert result_types == ["institutional_project"]


def test_onboarding_keeps_empty_direct_result_when_no_signal_exists():
    total, result_types = resolve_onboarding_result_filters(
        total=0,
        institutional_total=0,
        device_types=["subvention"],
    )

    assert total == 0
    assert result_types == ["subvention"]


def test_country_filter_includes_regional_africa_opportunities_for_west_africa():
    countries = DeviceService._expanded_country_filter(["Burkina Faso", "Bénin", "Côte d'Ivoire"])

    assert "Burkina Faso" in countries
    assert "Bénin" in countries
    assert "Côte d'Ivoire" in countries
    assert "Afrique de l'Ouest" in countries
    assert "Afrique" in countries


def test_country_filter_does_not_add_africa_for_france():
    countries = DeviceService._expanded_country_filter(["France"])

    assert countries == ["France"]
