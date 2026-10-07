from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.db.session import get_db
from app.documents.contracts import DocumentFactsOut, DocumentListOut, DocumentOut, DocumentPageOut
from app.core.config import settings
from app.documents.jobs import enqueue_document_job, run_document_job
from app.documents.service import DocumentService

router = APIRouter()


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
) -> DocumentOut:
    data = await file.read()
    out = DocumentService(db).upload(
        user_id=principal.subject_id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        conversation_id=conversation_id,
    )
    enqueue_document_job(db, out.document_id, principal.subject_id)
    if not settings.document_workers_external():
        background_tasks.add_task(run_document_job, out.document_id, principal.subject_id)
    return out


@router.get("/documents", response_model=DocumentListOut)
def list_documents(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> DocumentListOut:
    docs = DocumentService(db).list_for_user(principal.subject_id)
    return DocumentListOut(documents=docs)


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> DocumentOut:
    return DocumentService(db).get(principal.subject_id, document_id)


@router.get("/documents/{document_id}/facts", response_model=DocumentFactsOut)
def get_document_facts(
    document_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> DocumentFactsOut:
    return DocumentService(db).facts(principal.subject_id, document_id)


@router.get("/documents/{document_id}/pages/{page}", response_model=DocumentPageOut)
def get_document_page(
    document_id: str,
    page: int,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> DocumentPageOut:
    return DocumentService(db).page(principal.subject_id, document_id, page)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    DocumentService(db).delete(principal.subject_id, document_id)
    return None
