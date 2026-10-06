from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    follow_up_topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    follow_up_topic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_preference: Mapped[str | None] = mapped_column(String(8), nullable=True)
    last_source_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_marker_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    rating: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    interaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interaction(Base):
    """One completed chat turn for evaluation. References reports; does not store IHR blobs."""

    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    user_query: Mapped[str] = mapped_column(Text)
    assistant_response: Mapped[str] = mapped_column(Text)
    detected_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    routing_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    personal_data_required: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieval_used: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieval_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_operation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_refs: Mapped[str | None] = mapped_column(Text, nullable=True)
    ihr_queried: Mapped[bool] = mapped_column(Boolean, default=False)
    documents_queried: Mapped[bool] = mapped_column(Boolean, default=False)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    grounding_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    grounding_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safety_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class HealthFactRef(Base):
    """Provenanced health fact pointer discovered in a turn. Not an authoritative live value."""

    __tablename__ = "health_fact_refs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    interaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32))
    report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metric: Mapped[str] = mapped_column(String(128))
    value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    subject_id_hash: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """User-uploaded medical document metadata. Stored in Cura SQLite only."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512))
    upload_status: Mapped[str] = mapped_column(String(32), default="uploaded")
    extraction_status: Mapped[str] = mapped_column(String(32), default="not_started")
    source: Mapped[str] = mapped_column(String(32), default="user_uploaded")
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class UserHealthGoal(Base):
    """User-stated health goal stored in Cura SQLite. Not a SuperShyft write."""

    __tablename__ = "user_health_goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    goal_code: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserProfileFact(Base):
    """User-provided profile fact (medications, extra allergies). Not live IHR values."""

    __tablename__ = "user_profile_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    fact_key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), default="preference")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="user_uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document: Mapped["Document"] = relationship(back_populates="chunks")


class ProcessingJob(Base):
    """Durable document/work item. Survives process restart; workers claim by status."""

    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="document_extract")
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsentRecord(Base):
    """Versioned member consent before health data reaches third party model providers."""

    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    notice_sha256: Mapped[str] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
