import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Batch, Document, User
from app.qr.codes import sha256_bytes
from app.services.chain_service import record_event

router = APIRouter()
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


@router.post("/documents/hash")
async def upload_document(
    batch_id: str = Form(...),
    doc_type: str = Form("CERTIFICATE"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "QUALITY_INSPECTOR", "REGULATOR", "FARMER")),
):
    batch = db.query(Batch).filter_by(batch_id=batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    suffix = Path(file.filename or "file.bin").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "File type not allowed")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(400, "File too large")
    digest = sha256_bytes(data)
    dest = Path(settings.uploads_dir) / f"{digest}{suffix}"
    dest.write_bytes(data)
    rec = Document(
        batch_id=batch_id,
        filename=file.filename or dest.name,
        doc_type=doc_type,
        sha256=digest,
        stored_path=str(dest),
        uploaded_by=user.email,
    )
    db.add(rec)
    receipt = record_event(
        db,
        batch=batch,
        event_type="DOCUMENT",
        actor_email=user.email,
        actor_role=user.role,
        location=batch.current_location,
        metadata={"filename": rec.filename, "doc_type": doc_type},
        document_hash=digest,
    )
    rec.tx_id = receipt["tx_id"]
    db.commit()
    return {"sha256": digest, "tx_id": receipt["tx_id"], "block": receipt["block_index"]}


@router.post("/documents/verify")
async def verify_document(
    batch_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    data = await file.read()
    digest = hashlib.sha256(data).hexdigest()
    docs = db.query(Document).filter_by(batch_id=batch_id).all()
    if not docs:
        raise HTTPException(404, "No documents stored for this batch")
    match = next((d for d in docs if d.sha256 == digest), None)
    if match:
        return {"status": "DOCUMENT_VERIFIED", "sha256": digest, "filename": match.filename}
    return {
        "status": "DOCUMENT_MODIFIED",
        "message": "DOCUMENT MODIFIED — INTEGRITY COMPROMISED",
        "uploaded_sha256": digest,
        "known_hashes": [d.sha256 for d in docs],
    }


@router.get("/documents")
def list_docs(batch_id: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Document)
    if batch_id:
        q = q.filter_by(batch_id=batch_id)
    return [
        {
            "batch_id": d.batch_id,
            "filename": d.filename,
            "doc_type": d.doc_type,
            "sha256": d.sha256,
            "tx_id": d.tx_id,
            "uploaded_by": d.uploaded_by,
        }
        for d in q.order_by(Document.id.desc()).limit(100)
    ]
