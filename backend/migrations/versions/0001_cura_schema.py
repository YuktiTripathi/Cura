"""Create the deterministic Cura-owned persistence baseline.

Revision ID: 0001_cura_schema
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_cura_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("follow_up_topic", sa.String(128), nullable=True),
        sa.Column("follow_up_topic_name", sa.String(255), nullable=True),
        sa.Column("language_preference", sa.String(8), nullable=True),
        sa.Column("last_source_mode", sa.String(32), nullable=True),
        sa.Column("last_document_id", sa.String(36), nullable=True),
        sa.Column("current_report_id", sa.String(128), nullable=True),
        sa.Column("current_marker_code", sa.String(128), nullable=True),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("conversation_state_json", sa.Text(), nullable=True),
        sa.Column("suggestions_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_subject_id", "conversations", ["subject_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("rating", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("helpful", sa.Boolean(), nullable=True),
        sa.Column("interaction_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_conversation_id", "feedback", ["conversation_id"])
    op.create_index("ix_feedback_subject_id", "feedback", ["subject_id"])
    op.create_index("ix_feedback_interaction_id", "feedback", ["interaction_id"])

    op.create_table(
        "interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=True),
        sa.Column("assistant_response", sa.Text(), nullable=True),
        sa.Column("detected_intent", sa.String(64), nullable=True),
        sa.Column("routing_decision", sa.String(32), nullable=True),
        sa.Column("personal_data_required", sa.Boolean(), nullable=False),
        sa.Column("retrieval_used", sa.Boolean(), nullable=False),
        sa.Column("retrieval_sources", sa.Text(), nullable=True),
        sa.Column("retrieval_operation", sa.String(64), nullable=True),
        sa.Column("retrieval_status", sa.String(32), nullable=True),
        sa.Column("evidence_refs", sa.Text(), nullable=True),
        sa.Column("ihr_queried", sa.Boolean(), nullable=False),
        sa.Column("documents_queried", sa.Boolean(), nullable=False),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("grounding_result", sa.Text(), nullable=True),
        sa.Column("grounding_passed", sa.Boolean(), nullable=True),
        sa.Column("safety_result", sa.Text(), nullable=True),
        sa.Column("safety_passed", sa.Boolean(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("error_status", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("user_message_id", sa.String(36), nullable=True),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("conversation_id", "subject_id", "request_id", "created_at"):
        op.create_index(f"ix_interactions_{column}", "interactions", [column])

    op.create_table(
        "health_fact_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("interaction_id", sa.String(36), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("report_id", sa.String(128), nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("value", sa.String(64), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("observed_at", sa.String(32), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("subject_id", "conversation_id", "interaction_id"):
        op.create_index(f"ix_health_fact_refs_{column}", "health_fact_refs", [column])

    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("subject_id_hash", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_records_request_id", "audit_records", ["request_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("upload_status", sa.String(32), nullable=False),
        sa.Column("extraction_status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("extraction_error", sa.String(255), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_chars", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("user_id", "conversation_id", "created_at"):
        op.create_index(f"ix_documents_{column}", "documents", [column])

    op.create_table(
        "user_health_goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("goal_code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_health_goals_subject_id", "user_health_goals", ["subject_id"])
    op.create_index("ix_user_health_goals_goal_code", "user_health_goals", ["goal_code"])

    op.create_table(
        "user_profile_facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("fact_key", sa.String(128), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_profile_facts_subject_id", "user_profile_facts", ["subject_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_user_id", "document_chunks", ["user_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("document_id", "user_id", "status"):
        op.create_index(f"ix_processing_jobs_{column}", "processing_jobs", [column])


def downgrade() -> None:
    # Destructive downgrade is intentionally explicit rather than automatic for health conversations.
    raise RuntimeError("Cura's baseline schema downgrade requires an approved retention procedure")
