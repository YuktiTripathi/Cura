"""Add consent_records (readiness plan 1.4).

Revision ID: 0002_consent_records
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_consent_records"
down_revision = "0001_cura_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "consent_records" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("notice_sha256", sa.String(64), nullable=False),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_consent_records_subject_id", "consent_records", ["subject_id"])


def downgrade() -> None:
    raise RuntimeError("Consent records are an audit trail; drop them only under an approved retention procedure")
