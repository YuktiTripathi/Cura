from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # Never run DDL against SuperShyft Postgres. Cura conversations stay in SQLite.
    if not settings.cura_database_is_sqlite():
        return
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(conversations)")).fetchall()}
        if "language_preference" not in cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN language_preference VARCHAR(8)"))
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "documents" in tables:
            doc_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(documents)")).fetchall()}
            if "extraction_error" not in doc_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN extraction_error VARCHAR(255)"))
            if "page_count" not in doc_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN page_count INTEGER"))
            if "extracted_chars" not in doc_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN extracted_chars INTEGER"))
        conv_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(conversations)")).fetchall()}
        if "last_source_mode" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN last_source_mode VARCHAR(32)"))
        if "last_document_id" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN last_document_id VARCHAR(36)"))
        if "current_report_id" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN current_report_id VARCHAR(128)"))
        if "current_marker_code" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN current_marker_code VARCHAR(128)"))
        if "conversation_summary" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN conversation_summary TEXT"))
        if "conversation_state_json" not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN conversation_state_json TEXT"))
        if "feedback" in tables:
            fb_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(feedback)")).fetchall()}
            if "helpful" not in fb_cols:
                conn.execute(text("ALTER TABLE feedback ADD COLUMN helpful BOOLEAN"))
            if "interaction_id" not in fb_cols:
                conn.execute(text("ALTER TABLE feedback ADD COLUMN interaction_id VARCHAR(36)"))
        if "interactions" in tables:
            ix_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(interactions)")).fetchall()}
            if "grounding_passed" not in ix_cols:
                conn.execute(text("ALTER TABLE interactions ADD COLUMN grounding_passed BOOLEAN"))
            if "safety_passed" not in ix_cols:
                conn.execute(text("ALTER TABLE interactions ADD COLUMN safety_passed BOOLEAN"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
