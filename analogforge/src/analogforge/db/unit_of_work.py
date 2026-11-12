"""Transaction boundary used by services; implementation lives with Store to share fencing."""

from analogforge.db.store import UnitOfWork

__all__ = ["UnitOfWork"]
