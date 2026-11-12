"""Forward schema stage 5: qualification."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 5)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
