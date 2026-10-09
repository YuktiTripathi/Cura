"""Converge Cura schema, remove the unused prompt table, and add query indexes.

Revision ID: 0004_schema_cleanup
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_schema_cleanup"
down_revision = "0003_job_claims"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(table)
        if index.get("name")
    }


def _add_missing_columns() -> None:
    additions: dict[str, list[sa.Column]] = {
        "conversations": [
            sa.Column("language_preference", sa.String(8), nullable=True),
            sa.Column("last_source_mode", sa.String(32), nullable=True),
            sa.Column("last_document_id", sa.String(36), nullable=True),
            sa.Column("current_report_id", sa.String(128), nullable=True),
            sa.Column("current_marker_code", sa.String(128), nullable=True),
            sa.Column("conversation_summary", sa.Text(), nullable=True),
            sa.Column("conversation_state_json", sa.Text(), nullable=True),
            sa.Column("suggestions_json", sa.Text(), nullable=True),
        ],
        "documents": [
            sa.Column("extraction_error", sa.String(255), nullable=True),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("extracted_chars", sa.Integer(), nullable=True),
        ],
        "feedback": [
            sa.Column("helpful", sa.Boolean(), nullable=True),
            sa.Column("interaction_id", sa.String(36), nullable=True),
        ],
        "interactions": [
            sa.Column("grounding_passed", sa.Boolean(), nullable=True),
            sa.Column("safety_passed", sa.Boolean(), nullable=True),
            sa.Column("user_message_id", sa.String(36), nullable=True),
        ],
    }
    existing_tables = _tables()
    for table, candidates in additions.items():
        if table not in existing_tables:
            raise RuntimeError(f"Required Cura table is missing: {table}")
        existing = _columns(table)
        for column in candidates:
            if column.name not in existing:
                op.add_column(table, column)


def _make_interaction_text_legacy() -> None:
    if "interactions" not in _tables():
        raise RuntimeError("Required Cura table is missing: interactions")
    columns = _columns("interactions")
    with op.batch_alter_table("interactions") as batch:
        if "user_query" in columns:
            batch.alter_column(
                "user_query",
                existing_type=sa.Text(),
                nullable=True,
            )
        if "assistant_response" in columns:
            batch.alter_column(
                "assistant_response",
                existing_type=sa.Text(),
                nullable=True,
            )


def _drop_empty_prompt_versions() -> None:
    if "prompt_versions" not in _tables():
        return
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM prompt_versions")).scalar_one()
    if count:
        raise RuntimeError(
            "prompt_versions is not empty; export/review its rows before applying 0004_schema_cleanup"
        )
    op.drop_table("prompt_versions")


def _create_indexes() -> None:
    definitions = {
        "conversations": (
            "ix_conversations_subject_updated",
            ["subject_id", "updated_at"],
        ),
        "messages": (
            "ix_messages_conversation_created",
            ["conversation_id", "created_at", "id"],
        ),
        "interactions": (
            "ix_interactions_conversation_subject_created",
            ["conversation_id", "subject_id", "created_at"],
        ),
        "documents": (
            "ix_documents_user_created",
            ["user_id", "created_at"],
        ),
        "document_chunks": (
            "ix_document_chunks_user_document_page",
            ["user_id", "document_id", "page_start"],
        ),
        "processing_jobs": (
            "ix_processing_jobs_kind_status_created",
            ["kind", "status", "created_at"],
        ),
        "consent_records": (
            "ix_consent_records_subject_created",
            ["subject_id", "created_at", "id"],
        ),
        "audit_records": (
            "ix_audit_records_created",
            ["created_at"],
        ),
    }
    existing_tables = _tables()
    for table, (name, columns) in definitions.items():
        if table not in existing_tables:
            raise RuntimeError(f"Required Cura table is missing: {table}")
        if name not in _indexes(table):
            op.create_index(name, table, columns, unique=False)
    if "feedback" not in existing_tables:
        raise RuntimeError("Required Cura table is missing: feedback")
    if "ix_feedback_interaction_id" not in _indexes("feedback"):
        op.create_index(
            "ix_feedback_interaction_id",
            "feedback",
            ["interaction_id"],
            unique=False,
        )


def upgrade() -> None:
    _add_missing_columns()
    _make_interaction_text_legacy()
    _drop_empty_prompt_versions()
    _create_indexes()


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading schema cleanup requires an approved data-preservation procedure"
    )
