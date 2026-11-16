"""Container-only probes: no anonymous visitor sessions and no model calls."""
import sys
import urllib.request

if sys.argv[1] == "api":
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health/ready", timeout=3) as response:
        if response.status != 200:
            raise SystemExit(1)
else:
    from analogforge.db.store import Store
    from analogforge.settings import Settings

    store = Store(Settings().database_url)
    try:
        if not store.worker_healthy():
            raise SystemExit(1)
    finally:
        store.close()
