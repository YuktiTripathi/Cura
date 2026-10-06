"""Add consent_records (readiness plan 1.4).

Revision ID: 0002_consent_records
"""

from alembic import op

from app.db.models import ConsentRecord

revision = "0002_consent_records"
down_revision = "0001_cura_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ConsentRecord.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("Consent records are an audit trail; drop them only under an approved retention procedure")
