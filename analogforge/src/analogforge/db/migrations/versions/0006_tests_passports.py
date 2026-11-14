"""Forward schema stage 6: tests_passports."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 6)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
