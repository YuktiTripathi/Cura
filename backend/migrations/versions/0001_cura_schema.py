"""Create Cura-owned persistence schema.

Revision ID: 0001_cura_schema
"""

from alembic import op

from app.db.models import Base

revision = "0001_cura_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This metadata contains Cura-owned tables only. SuperShyft models are not imported.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Destructive downgrade is intentionally explicit rather than automatic for health conversations.
    raise RuntimeError("Cura's baseline schema downgrade requires an approved retention procedure")
