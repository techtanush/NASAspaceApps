"""Create a non-superuser runtime owner after privileged migrations; never logs DSNs."""
import os
from urllib.parse import unquote, urlsplit

import psycopg
from psycopg import sql

from analogforge.db.schema import TABLES
from analogforge.settings import Settings

settings = Settings()
runtime = urlsplit(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
admin = os.environ["DATABASE_ADMIN_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
role_name = unquote(runtime.username or "")
password = unquote(runtime.password or "")
if role_name != "analogforge" or not password or runtime.path != "/analogforge":
    raise SystemExit("The deployment runtime database role is invalid")
role = sql.Identifier(role_name)
with psycopg.connect(admin) as connection:
    exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role_name,)).fetchone()
    if not exists:
        connection.execute(sql.SQL("CREATE ROLE {} LOGIN").format(role))
    connection.execute(sql.SQL(
        "ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
    ).format(role, sql.Literal(password)))
    connection.execute(sql.SQL("GRANT CONNECT ON DATABASE analogforge TO {}").format(role))
    connection.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(role))
    # The current worker performs global queue scans. Runtime owns only application
    # tables, so existing owner RLS behavior is preserved without SUPERUSER privilege.
    for name in [*TABLES, "alembic_version"]:
        connection.execute(sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(sql.Identifier(name), role))
    connection.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
print("Provisioned the non-superuser runtime table owner; migration credentials remain separate.")
