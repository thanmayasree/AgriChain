from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Batch, Farmer, QualityInspection, SensorReading, SupplyChainEvent, Transport, User
from app.qr.codes import generate_qr_bytes, generate_qr_png
from app.schemas.dto import BatchCreate
from app.services.chain_service import next_batch_id, record_event

router = APIRouter()


def serialize_batch(b: Batch) -> dict:
    return {
        "batch_id": b.batch_id,
        "crop": b.crop,
        "variety": b.variety,
        "quantity_kg": b.quantity_kg,
        "harvest_date": b.harvest_date,
        "origin": b.origin,
        "farmer_name": b.farmer_name,
        "expected_destination": b.expected_destination,
        "current_location": b.current_location,
        "current_stakeholder": b.current_stakeholder,
        "quality_grade": b.quality_grade,
        "quality_score": b.quality_score,
        "risk_score": b.risk_score,
        "risk_level": b.risk_level,
        "trust_score": b.trust_score,
        "sustainability_score": b.sustainability_score,
        "verification_status": b.verification_status,
        "contaminated": b.contaminated,
        "recall_status": b.recall_status,
        "farmer_price": b.farmer_price,
        "processor_price": b.processor_price,
        "distributor_price": b.distributor_price,
        "retail_price": b.retail_price,
        "payment_status": b.payment_status,
        "image_url": b.image_url,
    }


@router.get("")
def list_batches(
    q: str | None = None,
    crop: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Batch)
    if user.role == "FARMER":
        query = query.filter(Batch.farmer_name == user.full_name)
    if crop:
        query = query.filter(Batch.crop == crop)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Batch.batch_id.ilike(like)
            | Batch.farmer_name.ilike(like)
            | Batch.crop.ilike(like)
            | Batch.origin.ilike(like)
        )
    rows = query.order_by(Batch.id.desc()).offset(skip).limit(limit).all()
    return {"items": [serialize_batch(b) for b in rows], "total": query.count()}


@router.post("")
def create_batch(body: BatchCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "FARMER"))):
    farmer = db.query(Farmer).filter_by(user_id=user.id).first()
    bid = next_batch_id(db, body.crop, body.origin)
    batch = Batch(
        batch_id=bid,
        crop=body.crop,
        variety=body.variety,
        quantity_kg=body.quantity_kg,
        harvest_date=body.harvest_date,
        origin=body.origin,
        farmer_id=farmer.id if farmer else None,
        farmer_name=user.full_name,
        expected_destination=body.expected_destination,
        current_location=body.origin,
        image_url=body.image_url,
        farmer_price=body.farmer_price,
        verification_status="REGISTERED",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    generate_qr_png(bid)
    record_event(
        db,
        batch=batch,
        event_type="HARVEST",
        actor_email=user.email,
        actor_role=user.role,
        location=body.origin,
        metadata={"quantity_kg": body.quantity_kg, "crop": body.crop},
        lat=farmer.lat if farmer else 0,
        lng=farmer.lng if farmer else 0,
    )
    db.refresh(batch)
    return serialize_batch(batch)


@router.get("/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    b = db.query(Batch).filter_by(batch_id=batch_id).first()
    if not b:
        raise HTTPException(404, "Unknown batch")
    events = db.query(SupplyChainEvent).filter_by(batch_id=batch_id).order_by(SupplyChainEvent.id).all()
    qi = db.query(QualityInspection).filter_by(batch_id=batch_id).order_by(QualityInspection.id.desc()).first()
    tr = db.query(Transport).filter_by(batch_id=batch_id).order_by(Transport.id.desc()).first()
    sensors = db.query(SensorReading).filter_by(batch_id=batch_id).order_by(SensorReading.id.desc()).limit(40).all()
    return {
        **serialize_batch(b),
        "timeline": [
            {
                "event_type": e.event_type,
                "actor": e.actor_email,
                "location": e.location,
                "timestamp": e.created_at.isoformat(),
                "tx_id": e.tx_id,
                "block_index": e.block_index,
                "block_hash": e.block_hash,
                "data_hash": e.data_hash,
            }
            for e in events
        ],
        "quality": None
        if not qi
        else {
            "moisture": qi.moisture,
            "foreign_matter": qi.foreign_matter,
            "grade": qi.grade,
            "quality_score": qi.quality_score,
            "status": qi.status,
        },
        "transport": None
        if not tr
        else {
            "vehicle_id": tr.vehicle_id,
            "origin": tr.origin,
            "destination": tr.destination,
            "origin_lat": tr.origin_lat,
            "origin_lng": tr.origin_lng,
            "dest_lat": tr.dest_lat,
            "dest_lng": tr.dest_lng,
            "current_lat": tr.current_lat,
            "current_lng": tr.current_lng,
            "distance_km": tr.distance_km,
            "delay_hours": tr.delay_hours,
            "progress": tr.progress,
            "status": tr.status,
        },
        "sensors": [
            {
                "temperature": s.temperature,
                "humidity": s.humidity,
                "lat": s.lat,
                "lng": s.lng,
                "speed_kmh": s.speed_kmh,
                "anomalous": s.anomalous,
                "created_at": s.created_at.isoformat(),
            }
            for s in reversed(sensors)
        ],
        "qr_url": f"/api/batches/{batch_id}/qr",
        "verify_url": f"/verify/{batch_id}",
    }


@router.get("/{batch_id}/history")
def history(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.blockchain.ledger import get_ledger

    if not db.query(Batch).filter_by(batch_id=batch_id).first():
        raise HTTPException(404, "Unknown batch")
    return get_ledger().get_batch_history(batch_id)


@router.get("/{batch_id}/qr")
def qr(batch_id: str, db: Session = Depends(get_db)):
    if not db.query(Batch).filter_by(batch_id=batch_id).first():
        raise HTTPException(404, "Unknown batch")
    return Response(content=generate_qr_bytes(batch_id), media_type="image/png")


@router.get("/{batch_id}/passport")
def passport(batch_id: str, db: Session = Depends(get_db)):
    from app.api.routes.verify import public_verify

    return public_verify(batch_id, db)
