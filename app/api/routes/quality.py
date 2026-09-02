from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.engine import calculate_quality_score
from app.core.database import get_db
from app.core.deps import require_roles
from app.models.entities import Batch, QualityInspection, User
from app.qr.codes import sha256_obj
from app.schemas.dto import QualityCreate
from app.services.chain_service import record_event

router = APIRouter()


@router.post("/quality")
def inspect(body: QualityCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "QUALITY_INSPECTOR"))):
    batch = db.query(Batch).filter_by(batch_id=body.batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    score, grade, status = calculate_quality_score(body.moisture, body.foreign_matter)
    cert = sha256_obj(f"{body.batch_id}:{body.moisture}:{body.foreign_matter}:{score}")
    qi = QualityInspection(
        batch_id=body.batch_id,
        moisture=body.moisture,
        foreign_matter=body.foreign_matter,
        grade=grade,
        quality_score=score,
        status=status,
        inspector=user.email,
        location=body.location,
        inspection_date=body.inspection_date,
        certificate_hash=cert,
    )
    db.add(qi)
    batch.quality_grade = grade
    batch.quality_score = score
    receipt = record_event(
        db,
        batch=batch,
        event_type="QUALITY_CHECK",
        actor_email=user.email,
        actor_role=user.role,
        location=body.location,
        metadata={"moisture": body.moisture, "foreign_matter": body.foreign_matter, "grade": grade, "status": status},
        document_hash=cert,
    )
    return {
        "quality_score": score,
        "grade": grade,
        "status": status,
        "certificate_hash": cert,
        "blockchain": receipt,
    }
