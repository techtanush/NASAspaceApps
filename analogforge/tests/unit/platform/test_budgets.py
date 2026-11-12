"""Budget caps survive serialization and reject partial multi-counter charges."""

import pytest

from analogforge.domain.budgets import BudgetExceeded, BudgetLedger
from analogforge.ports.catalog import BUDGETS


@pytest.mark.parametrize("key", list(BUDGETS))
def test_every_budget_rejects_one_beyond_cap(key):
    ledger = BudgetLedger()
    ledger.charge(key, BUDGETS[key])
    restored = BudgetLedger.from_document(ledger.document())
    with pytest.raises(BudgetExceeded):
        restored.charge(key)
    assert restored.counters[key] == BUDGETS[key]


def test_route_and_candidate_replans_share_total_cap():
    ledger = BudgetLedger()
    ledger.replan("NEW_ROUTE")
    ledger.replan("NEW_ROUTE")
    with pytest.raises(BudgetExceeded):
        ledger.replan("NEW_ROUTE")
    assert ledger.counters["replans_total"] == 2
    ledger = BudgetLedger.from_document(ledger.document())
    ledger.replan("NEW_CANDIDATE")
    assert ledger.counters["replans_total"] == 3
    with pytest.raises(BudgetExceeded):
        ledger.replan("NEW_CANDIDATE")
    assert ledger.counters["candidate_switches"] == 1


def test_preparation_model_limit_is_separate():
    preparation = BudgetLedger()
    preparation.charge("preparation_model_requests", 4)
    with pytest.raises(BudgetExceeded):
        preparation.charge("preparation_model_requests")
    assert preparation.counters.get("model_requests_per_run", 0) == 0
