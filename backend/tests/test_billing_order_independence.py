"""Billing tests must give the same result whatever their execution order (per-test tenant isolation)."""
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BILLING_FILE = "tests/test_billing_lot4_postgres.py"

pytestmark = pytest.mark.skipif(
    os.getenv("KAFUNDO_BILLING_TESTS") != "1" or not os.getenv("TEST_POSTGRES_DATABASE_URL"),
    reason="Disposable PostgreSQL billing database required",
)


def _pytest(*args, verbose=False):
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-v" if verbose else "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=600,
    )


def _node_ids():
    result = _pytest(BILLING_FILE, "--collect-only")
    ids = [line.strip() for line in result.stdout.splitlines() if "::" in line]
    assert len(ids) >= 10, result.stdout + result.stderr
    return ids


def _order(kind, ids):
    if kind == "reversed":
        return list(reversed(ids))
    if kind == "rotated":
        return ids[len(ids) // 2:] + ids[: len(ids) // 2]
    shuffled = list(ids)
    random.Random(20240601).shuffle(shuffled)
    return shuffled


@pytest.mark.parametrize("kind", ["reversed", "rotated", "shuffled"])
def test_billing_results_do_not_depend_on_execution_order(kind):
    ids = _node_ids()
    ordered = _order(kind, ids)
    assert ordered != ids
    verbose = _pytest(*ordered, verbose=True)
    executed = [line.split(" ")[0] for line in verbose.stdout.splitlines() if " PASSED" in line or " FAILED" in line]
    assert executed == ordered, "pytest did not honour the requested order:\n" + verbose.stdout
    assert verbose.returncode == 0, verbose.stdout + verbose.stderr
    assert f"{len(ids)} passed" in verbose.stdout
