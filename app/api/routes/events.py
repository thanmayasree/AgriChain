import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import EVENT_PERMISSIONS
from app.models.entities import Batch, SupplyChainEvent, User
from app.schemas.dto import EventCreate
from app.services.chain_service import record_event

router = APIRouter()


@router.post("/events")
def create_event(body: EventCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    allowed = EVENT_PERMISSIONS.get(body.event_type)
    if not allowed:
        raise HTTPException(400, "Unknown event type")
    if user.role != "ADMIN" and user.role not in allowed:
        raise HTTPException(403, "This role cannot record that event type")
    batch = db.query(Batch).filter_by(batch_id=body.batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    receipt = record_event(
        db,
        batch=batch,
        event_type=body.event_type,
        actor_email=user.email,
        actor_role=user.role,
        location=body.location,
        metadata=body.metadata,
        lat=body.lat,
        lng=body.lng,
    )
    return {
        "message": "Event Anchored to Blockchain",
        "transaction_id": receipt["tx_id"],
        "block_number": receipt["block_index"],
        "timestamp": receipt["timestamp"],
        "hash": receipt["block_hash"],
        "data_hash": receipt["data_hash"],
        "verification_status": receipt["verification_status"],
    }


@router.get("/events")
def list_events(batch_id: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(SupplyChainEvent)
    if batch_id:
        q = q.filter_by(batch_id=batch_id)
    rows = q.order_by(SupplyChainEvent.id.desc()).limit(200).all()
    return [
        {
            "batch_id": e.batch_id,
            "event_type": e.event_type,
            "actor": e.actor_email,
            "location": e.location,
            "tx_id": e.tx_id,
            "block_index": e.block_index,
            "hash": e.block_hash,
            "metadata": json.loads(e.metadata_json or "{}"),
            "created_at": e.created_at.isoformat(),
        }
        for e in rows
    ]
