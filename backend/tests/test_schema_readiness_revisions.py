"""/api/ready : la revision precedente reste acceptee (deploiement des images et migration c8e1f4a7b2d9 independants)."""
from app import schema_readiness as sr


def test_head_and_previous_revisions_are_accepted():
    assert sr.HEAD_REVISION == "c8e1f4a7b2d9"
    assert sr.HEAD_REVISION in sr.COMPATIBLE_REVISIONS
    assert sr.PREVIOUS_COMPATIBLE_REVISION == "b7d3a91c5e24" in sr.COMPATIBLE_REVISIONS


def test_unknown_or_missing_revisions_are_refused():
    for bad in (None, "", "3f8e2d1c9a05", "deadbeef"):
        assert bad not in sr.COMPATIBLE_REVISIONS


def test_only_the_two_documented_revisions_are_compatible():
    assert sr.COMPATIBLE_REVISIONS == {"b7d3a91c5e24", "c8e1f4a7b2d9"}
