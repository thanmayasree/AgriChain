import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.entities import Batch, Recall, SupplyChainEvent, User
from app.schemas.dto import RecallIn
from app.services.chain_service import notify, record_event

router = APIRouter()


@router.post("/recalls")
def start_recall(body: RecallIn, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "REGULATOR"))):
    batch = db.query(Batch).filter_by(batch_id=body.batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    batch.contaminated = True
    batch.recall_status = "ACTIVE"
    events = db.query(SupplyChainEvent).filter_by(batch_id=body.batch_id).all()
    locations = sorted({e.location for e in events})
    rec = Recall(
        batch_id=body.batch_id,
        reason=body.reason,
        status="ACTIVE",
        affected_locations_json=json.dumps(locations),
        affected_units=batch.quantity_kg,
    )
    db.add(rec)
    notify(db, "Recall started", f"{body.batch_id}: {body.reason}", "RECALL", body.batch_id)
    record_event(
        db,
        batch=batch,
        event_type="DOCUMENT",
        actor_email=user.email,
        actor_role=user.role,
        location=batch.current_location,
        metadata={"recall": True, "reason": body.reason},
    )
    return {
        "recall_id": rec.id,
        "affected_units": batch.quantity_kg,
        "affected_locations": locations,
        "downstream": [
            {"event_type": e.event_type, "location": e.location, "actor": e.actor_email}
            for e in events
        ],
        "status": "ACTIVE",
    }


@router.get("/recalls")
def list_recalls(db: Session = Depends(get_db), _=Depends(require_roles("ADMIN", "REGULATOR"))):
    rows = db.query(Recall).order_by(Recall.id.desc()).all()
    return [
        {
            "id": r.id,
            "batch_id": r.batch_id,
            "reason": r.reason,
            "status": r.status,
            "affected_units": r.affected_units,
            "locations": json.loads(r.affected_locations_json or "[]"),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
