"""Serializable budget accounting; callers persist charges in their transaction."""

from dataclasses import dataclass, field
from typing import Any

from analogforge.ports.catalog import BUDGETS


class BudgetExceeded(ValueError):
    code = "BUDGET_EXHAUSTED"


@dataclass
class BudgetLedger:
    counters: dict[str, float] = field(default_factory=dict)
    limits: dict[str, float] = field(default_factory=lambda: {k: float(v) for k, v in BUDGETS.items()})

    @classmethod
    def from_document(cls, document: dict[str, Any] | None) -> "BudgetLedger":
        document = document or {}
        return cls(
            dict(document.get("counters", {})),
            {**{k: float(v) for k, v in BUDGETS.items()}, **document.get("limits", {})},
        )

    def charge(self, key: str, amount: float = 1) -> None:
        if amount < 0 or key not in self.limits:
            raise ValueError("Budget charge must use a registered key and nonnegative amount")
        next_value = self.counters.get(key, 0) + amount
        if next_value > self.limits[key]:
            raise BudgetExceeded(key)
        self.counters[key] = next_value

    def remaining(self, key: str) -> float:
        return max(0, self.limits[key] - self.counters.get(key, 0))

    def replan(self, kind: str) -> None:
        key = "candidate_switches" if kind == "NEW_CANDIDATE" else "route_repairs_same_candidate"
        # Reserve both counters before changing either one.
        if self.remaining(key) < 1 or self.remaining("replans_total") < 1:
            raise BudgetExceeded(key)
        self.charge(key)
        self.charge("replans_total")

    def document(self) -> dict[str, Any]:
        return {"counters": dict(self.counters), "limits": dict(self.limits)}
