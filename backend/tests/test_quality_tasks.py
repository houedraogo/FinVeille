from app.tasks.quality_tasks import _audit_action_from_score


def test_audit_action_prioritizes_purge_for_inactive_or_unreachable_sources():
    assert _audit_action_from_score(90, ["inactive_never_collected"]) == "a_purger"
    assert _audit_action_from_score(90, ["expired_unreachable"]) == "a_purger"


def test_audit_action_routes_source_errors_to_source_review():
    assert _audit_action_from_score(80, ["source_errors"]) == "source_a_revoir"
    assert _audit_action_from_score(80, ["too_many_non_public_urls"]) == "source_a_revoir"


def test_audit_action_routes_content_quality_to_enrichment():
    assert _audit_action_from_score(40, ["weak_text"]) == "a_enrichir"
    assert _audit_action_from_score(40, ["english_text"]) == "a_enrichir"
    assert _audit_action_from_score(40, ["html_raw"]) == "a_enrichir"


def test_audit_action_routes_ambiguous_statuses_to_review():
    assert _audit_action_from_score(40, ["open_without_date"]) == "a_verifier"
    assert _audit_action_from_score(40, ["recurring_ambiguous"]) == "a_verifier"
    assert _audit_action_from_score(40, ["pending_review"]) == "a_verifier"

