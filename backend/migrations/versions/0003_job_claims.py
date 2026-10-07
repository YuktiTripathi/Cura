"""Add processing_jobs.claimed_at for multi-worker claiming (readiness plan 5.2).

Revision ID: 0003_job_claims
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_job_claims"
down_revision = "0002_consent_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {col["name"] for col in sa.inspect(op.get_bind()).get_columns("processing_jobs")}
    if "claimed_at" not in columns:
        op.add_column("processing_jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "claimed_at")
