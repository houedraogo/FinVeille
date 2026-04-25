from datetime import date

from app.services.deadline_classifier import classify_deadline


def make_device(**overrides):
    payload = {
        "title": "Aide a l'innovation",
        "organism": "Kafundo",
        "device_type": "subvention",
        "status": "open",
        "is_recurring": False,
        "close_date": None,
        "short_description": "Aide pour financer un projet.",
        "full_description": "Description du dispositif.",
        "recurrence_notes": None,
    }
    payload.update(overrides)
    return payload


def test_known_deadline_is_open():
    result = classify_deadline(make_device(close_date=date(2026, 6, 30)), today=date(2026, 4, 22))

    assert result.key == "known"
    assert result.status == "open"
    assert result.tag == "deadline:known"


def test_past_deadline_is_expired():
    result = classify_deadline(make_device(close_date=date(2025, 6, 30)), today=date(2026, 4, 22))

    assert result.key == "expired"
    assert result.status == "expired"
    assert result.tag == "deadline:expired"


def test_recurring_without_close_date_is_permanent():
    result = classify_deadline(
        make_device(
            status="recurring",
            is_recurring=True,
            recurrence_notes="Dispositif ouvert en continu toute l'annee.",
        ),
        today=date(2026, 4, 22),
    )

    assert result.key == "permanent"
    assert result.status == "recurring"
    assert result.tag == "deadline:permanent"


def test_institutional_project_without_close_date_is_not_open_call():
    result = classify_deadline(
        make_device(device_type="institutional_project", status="open"),
        today=date(2026, 4, 22),
    )

    assert result.key == "institutional_project"
    assert result.status == "standby"
    assert result.validation_status == "pending_review"


def test_unknown_deadline_signal_is_not_communicated():
    result = classify_deadline(
        make_device(status="standby", full_description="Cloture non communiquee par la source officielle."),
        today=date(2026, 4, 22),
    )

    assert result.key == "not_communicated"
    assert result.tag == "deadline:not_communicated"


def test_missing_deadline_without_evidence_needs_review():
    result = classify_deadline(make_device(status="open"), today=date(2026, 4, 22))

    assert result.key == "needs_review"
    assert result.status == "standby"
    assert result.validation_status == "pending_review"
