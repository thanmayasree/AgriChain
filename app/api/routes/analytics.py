from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.blockchain.ledger import get_ledger
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Batch, Notification, QualityInspection, SensorReading, SupplyChainEvent, User

router = APIRouter()


@router.get("/analytics")
def analytics(crop: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Batch)
    if crop:
        q = q.filter(Batch.crop == crop)
    batches = q.all()
    crops = Counter(b.crop for b in batches)
    grades = Counter(b.quality_grade for b in batches)
    risks = Counter(b.risk_level for b in batches)
    events = db.query(SupplyChainEvent).all()
    event_types = Counter(e.event_type for e in events)
    sensors = db.query(SensorReading).order_by(SensorReading.id.desc()).limit(80).all()
    return {
        "totals": {
            "batches": len(batches),
            "verified": sum(1 for b in batches if b.verification_status == "VERIFIED"),
            "flagged": sum(1 for b in batches if b.risk_level in {"HIGH", "CRITICAL"}),
            "high_risk": sum(1 for b in batches if b.risk_level == "HIGH"),
            "critical": sum(1 for b in batches if b.risk_level == "CRITICAL"),
            "blocks": get_ledger().get_latest_block().index,
            "events": len(events),
            "users": db.query(User).count(),
            "quality_failures": db.query(QualityInspection).filter_by(status="FAILED").count(),
            "temp_alerts": db.query(SensorReading).filter_by(anomalous=True).count(),
        },
        "crop_distribution": crops,
        "quality_distribution": grades,
        "risk_distribution": risks,
        "event_activity": event_types,
        "regional": Counter(b.origin for b in batches),
        "volume": {b.crop: sum(x.quantity_kg for x in batches if x.crop == b.crop) for b in batches},
        "temperature_trend": [{"t": s.temperature, "h": s.humidity, "at": s.created_at.isoformat()} for s in reversed(sensors)],
        "avg_transport_km": (
            sum((b.expected_destination and 80) or 0 for b in batches) / max(1, len(batches))
        ),
    }


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Notification).order_by(Notification.id.desc()).limit(50).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "kind": n.kind,
            "batch_id": n.batch_id,
            "read": n.read,
            "created_at": n.created_at.isoformat(),
        }
        for n in rows
    ]


@router.post("/notifications/{nid}/read")
def read_note(nid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    n = db.query(Notification).filter_by(id=nid).first()
    if n:
        n.read = True
        db.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = analytics(db=db, _=user)
    from app.blockchain.ledger import get_ledger

    ledger = get_ledger()
    valid, reason, failed = ledger.is_chain_valid()
    latest = ledger.get_latest_block()
    data["blockchain_live"] = {
        "chain_status": "VALID" if valid else "COMPROMISED",
        "latest_block": latest.index,
        "block_height": latest.index,
        "latest_hash": latest.hash,
        "network_status": "ONLINE",
        "integrity": "OK" if valid else "COMPROMISED",
        "reason": reason,
        "failed_block": failed,
    }
    data["role"] = user.role
    return data
