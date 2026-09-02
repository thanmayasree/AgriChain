import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.engine import engine
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Batch, RiskAssessment, SensorReading, Transport

router = APIRouter()


@router.get("/risk/{batch_id}")
def risk_for_batch(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    batch = db.query(Batch).filter_by(batch_id=batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    last = db.query(SensorReading).filter_by(batch_id=batch_id).order_by(SensorReading.id.desc()).first()
    tr = db.query(Transport).filter_by(batch_id=batch_id).order_by(Transport.id.desc()).first()
    result = engine.assess(
        temperature=last.temperature if last else 25,
        humidity=last.humidity if last else 60,
        delay_hours=tr.delay_hours if tr else 0,
        distance_km=tr.distance_km if tr else 40,
        quality_score=batch.quality_score or 80,
        quantity_kg=batch.quantity_kg,
    )
    latest = db.query(RiskAssessment).filter_by(batch_id=batch_id).order_by(RiskAssessment.id.desc()).first()
    return {
        **result.as_dict(),
        "stored_score": batch.risk_score,
        "stored_level": batch.risk_level,
        "last_assessment": None
        if not latest
        else {
            "score": latest.score,
            "level": latest.level,
            "reasons": json.loads(latest.reasons_json),
            "importance": json.loads(latest.importance_json),
        },
    }


@router.get("/risk-center")
def risk_center(
    level: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_roles("ADMIN", "REGULATOR", "QUALITY_INSPECTOR")),
):
    q = db.query(Batch)
    if level:
        q = q.filter(Batch.risk_level == level.upper())
    batches = q.order_by(Batch.risk_score.desc()).all()
    return {
        "items": [
            {
                "batch_id": b.batch_id,
                "crop": b.crop,
                "risk_score": b.risk_score,
                "risk_level": b.risk_level,
                "origin": b.origin,
                "quality_grade": b.quality_grade,
            }
            for b in batches
        ]
    }


@router.get("/sustainability/{batch_id}")
def sustainability(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.ai.engine import sustainability_score
    from app.models.entities import SensorReading, Transport

    batch = db.query(Batch).filter_by(batch_id=batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    last = db.query(SensorReading).filter_by(batch_id=batch_id).order_by(SensorReading.id.desc()).first()
    tr = db.query(Transport).filter_by(batch_id=batch_id).order_by(Transport.id.desc()).first()
    return sustainability_score(
        distance_km=tr.distance_km if tr else 40,
        delay_hours=tr.delay_hours if tr else 0,
        temp_deviation=abs((last.temperature if last else 25) - 25),
        wastage=0,
    )
