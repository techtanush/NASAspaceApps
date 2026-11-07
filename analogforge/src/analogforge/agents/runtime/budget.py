"""Invocation budget is independent from the durable run budget."""

from analogforge.domain.budgets import BudgetLedger


def invocation_budget() -> BudgetLedger:
    return BudgetLedger()
