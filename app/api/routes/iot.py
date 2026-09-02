from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.ai.engine import engine
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.iot.simulator import simulator
from app.models.entities import Batch, SensorReading, Transport
from app.schemas.dto import SensorIn
from app.services.chain_service import record_event, refresh_scores

router = APIRouter()


def _store(db: Session, body: SensorIn) -> SensorReading:
    batch = db.query(Batch).filter_by(batch_id=body.batch_id).first()
    if not batch:
        raise HTTPException(404, "Unknown batch")
    generated = simulator.reading(batch_id=body.batch_id, spike=body.spike)
    temp = body.temperature if body.temperature is not None else generated["temperature"]
    hum = body.humidity if body.humidity is not None else generated["humidity"]
    lat = body.lat if body.lat is not None else generated["lat"]
    lng = body.lng if body.lng is not None else generated["lng"]
    speed = body.speed_kmh if body.speed_kmh is not None else generated["speed_kmh"]
    vib = body.vibration if body.vibration is not None else generated["vibration"]
    risk = engine.assess(
        temperature=temp,
        humidity=hum,
        delay_hours=0,
        distance_km=80,
        quality_score=batch.quality_score or 85,
        quantity_kg=batch.quantity_kg,
    )
    anomalous = temp > 40 or temp < 10 or risk.score >= 61
    row = SensorReading(
        batch_id=body.batch_id,
        temperature=temp,
        humidity=hum,
        lat=lat,
        lng=lng,
        speed_kmh=speed,
        vibration=vib,
        anomalous=anomalous,
    )
    db.add(row)
    tr = db.query(Transport).filter_by(batch_id=body.batch_id).order_by(Transport.id.desc()).first()
    if tr:
        tr.current_lat = lat
        tr.current_lng = lng
    refresh_scores(db, batch, extra={"temperature": temp, "humidity": hum})
    db.commit()
    db.refresh(row)
    return row


@router.post("/sensor-data")
def sensor_data(body: SensorIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = _store(db, body)
    return {
        "id": row.id,
        "temperature": row.temperature,
        "humidity": row.humidity,
        "lat": row.lat,
        "lng": row.lng,
        "speed_kmh": row.speed_kmh,
        "anomalous": row.anomalous,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/sensor-data/anchor")
def anchor(body: SensorIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = _store(db, body)
    batch = db.query(Batch).filter_by(batch_id=body.batch_id).first()
    from app.qr.codes import sha256_obj
    import json

    payload = {
        "temperature": row.temperature,
        "humidity": row.humidity,
        "lat": row.lat,
        "lng": row.lng,
        "id": row.id,
    }
    h = sha256_obj(json.dumps(payload, sort_keys=True))
    receipt = record_event(
        db,
        batch=batch,
        event_type="SENSOR_ANCHOR",
        actor_email=user.email,
        actor_role=user.role,
        location=batch.current_location,
        metadata=payload,
        document_hash=h,
        lat=row.lat,
        lng=row.lng,
    )
    row.anchored = True
    db.commit()
    return {"anchored": True, "hash": h, "blockchain": receipt, "anomalous": row.anomalous}


@router.get("/sensor-data/{batch_id}")
def list_sensors(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(SensorReading).filter_by(batch_id=batch_id).order_by(SensorReading.id).all()
    return [
        {
            "temperature": r.temperature,
            "humidity": r.humidity,
            "lat": r.lat,
            "lng": r.lng,
            "speed_kmh": r.speed_kmh,
            "anomalous": r.anomalous,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/tracking/{batch_id}")
def tracking(batch_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.models.entities import Transport

    tr = db.query(Transport).filter_by(batch_id=batch_id).order_by(Transport.id.desc()).first()
    if not tr:
        raise HTTPException(404, "No transport record")
    last = db.query(SensorReading).filter_by(batch_id=batch_id).order_by(SensorReading.id.desc()).first()
    return {
        "vehicle_id": tr.vehicle_id,
        "origin": tr.origin,
        "destination": tr.destination,
        "route": [
            {"lat": tr.origin_lat, "lng": tr.origin_lng, "label": "Origin"},
            {"lat": tr.current_lat, "lng": tr.current_lng, "label": "Current"},
            {"lat": tr.dest_lat, "lng": tr.dest_lng, "label": "Destination"},
        ],
        "distance_km": tr.distance_km,
        "progress": tr.progress,
        "delay_hours": tr.delay_hours,
        "temperature": last.temperature if last else None,
        "humidity": last.humidity if last else None,
        "status": tr.status,
    }


@router.websocket("/ws/iot/{batch_id}")
async def iot_ws(websocket: WebSocket, batch_id: str):
    await websocket.accept()
    db = SessionLocal()
    try:
        while True:
            await websocket.receive_text()
            row = _store(db, SensorIn(batch_id=batch_id))
            await websocket.send_json(
                {
                    "temperature": row.temperature,
                    "humidity": row.humidity,
                    "lat": row.lat,
                    "lng": row.lng,
                    "anomalous": row.anomalous,
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
