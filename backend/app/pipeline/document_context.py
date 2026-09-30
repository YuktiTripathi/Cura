"""Resolve which uploaded document(s) are in scope. Explicit ids always win."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.context_ref import ContextRef


@dataclass
class AttachedDocuments:
    document_ids: list[str]
    active_document_id: str | None
    status: str = "ok"


def resolve_attached_documents(
    *,
    explicit_ids: list[str] | None,
    context_ref: ContextRef | None = None,
    last_document_id: str | None = None,
    completed_docs: list | None = None,
) -> AttachedDocuments:
    ids = list(explicit_ids or [])
    if context_ref and context_ref.document_id and context_ref.document_id not in ids:
        ids.append(context_ref.document_id)
    if ids:
        active = ids[0] if len(ids) == 1 else None
        return AttachedDocuments(document_ids=ids, active_document_id=active, status="ok")
    if last_document_id:
        return AttachedDocuments(
            document_ids=[last_document_id],
            active_document_id=last_document_id,
            status="ok",
        )
    completed = list(completed_docs or [])
    if len(completed) == 1:
        did = getattr(completed[0], "document_id", None) or getattr(completed[0], "id", None)
        if did:
            return AttachedDocuments(document_ids=[str(did)], active_document_id=str(did), status="ok")
    if len(completed) > 1:
        return AttachedDocuments(document_ids=[], active_document_id=None, status="ambiguous")
    return AttachedDocuments(document_ids=[], active_document_id=None, status="missing")
