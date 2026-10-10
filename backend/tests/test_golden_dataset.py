"""Les 40 golden cases, un test par cas (aucun skip / xfail / suppression autorisé)."""
import pytest

from tests.fixtures.golden_dataset import GOLDEN_DATASET
from tests.fixtures.golden_harness import check_case


def test_golden_dataset_has_40_cases():
    assert len(GOLDEN_DATASET) == 40
    assert len({c["id"] for c in GOLDEN_DATASET}) == 40


@pytest.mark.parametrize("case", GOLDEN_DATASET, ids=[c["id"] for c in GOLDEN_DATASET])
def test_golden_case(case):
    errors = check_case(case)
    assert not errors, f"{case['id']}: " + " | ".join(errors)
