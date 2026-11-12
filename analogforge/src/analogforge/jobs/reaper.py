"""Periodic recovery of expired leases, independent of any scientific handler."""

import time

from analogforge.db.store import Store
from analogforge.jobs.queue import REAPER_SECONDS


class Reaper:
    def __init__(self, store: Store, interval_seconds: float = REAPER_SECONDS) -> None:
        if interval_seconds <= 0:
            raise ValueError("Reaper interval must be positive")
        self.store, self.interval_seconds = store, interval_seconds
        self.last_run = float("-inf")

    def run_due(self) -> int:
        current = time.monotonic()
        if current - self.last_run < self.interval_seconds:
            return 0
        result = self.store.reap_expired_jobs()
        self.last_run = current
        return result
