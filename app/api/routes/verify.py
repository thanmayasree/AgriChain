import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.blockchain.ledger import get_ledger
from app.core.database import get_db
from app.models.entities import Batch, QualityInspection, SupplyChainEvent, Transport
from app.services.chain_service import completeness, required_events

router = APIRouter()


def public_verify(batch_id: str, db: Session) -> dict:
    batch = db.query(Batch).filter_by(batch_id=batch_id).first()
    if not batch:
        return {
            "ok": False,
            "status": "VERIFICATION_FAILED",
            "reasons": ["Unknown batch"],
            "authentic": False,
        }
    ledger = get_ledger()
    valid, reason, failed = ledger.is_chain_valid()
    history = ledger.get_batch_history(batch_id)
    events = db.query(SupplyChainEvent).filter_by(batch_id=batch_id).order_by(SupplyChainEvent.id).all()
    present = {e.event_type for e in events}
    missing = [e for e in required_events() if e not in present]
    qi = db.query(QualityInspection).filter_by(batch_id=batch_id).order_by(QualityInspection.id.desc()).first()
    tr = db.query(Transport).filter_by(batch_id=batch_id).order_by(Transport.id.desc()).first()

    flags = []
    if not history:
        flags.append("Missing blockchain history")
    if not valid:
        flags.append("Broken chain")
        if failed is not None:
            flags.append(f"Failed at block {failed}: {reason}")
    if missing and batch.verification_status != "REGISTERED":
        flags.append("Missing required events: " + ", ".join(missing[:4]))
    if batch.contaminated:
        flags.append("Batch marked contaminated")

    authentic = bool(history) and valid and not batch.contaminated
    origin_ok = bool(batch.origin)
    quality_ok = bool(qi) and qi.status == "PASSED"
    chain_ok = valid and bool(history)
    supply_ok = completeness(db, batch_id) >= 0.5

    return {
        "ok": authentic,
        "authentic": authentic,
        "status": "AUTHENTIC" if authentic and not flags else "VERIFICATION_FAILED",
        "reasons": flags,
        "product": batch.crop,
        "batch_id": batch.batch_id,
        "origin": batch.origin,
        "harvest": batch.harvest_date,
        "farmer": batch.farmer_name,
        "quality": batch.quality_grade,
        "quality_score": batch.quality_score,
        "transport_km": tr.distance_km if tr else None,
        "processing": "Premium" if batch.quality_grade == "A" else batch.current_stakeholder,
        "retail": f"₹{int(batch.retail_price)}/kg" if batch.retail_price else None,
        "trust_score": batch.trust_score,
        "sustainability_score": batch.sustainability_score,
        "risk_score": batch.risk_score,
        "risk_level": batch.risk_level,
        "checks": {
            "origin": origin_ok,
            "quality": quality_ok,
            "supply_chain": supply_ok,
            "blockchain": chain_ok,
        },
        "timeline": [
            {
                "event_type": e.event_type,
                "location": e.location,
                "timestamp": e.created_at.isoformat(),
                "verified": True,
            }
            for e in events
        ],
        "prices": {
            "farmer": batch.farmer_price,
            "processor": batch.processor_price,
            "distributor": batch.distributor_price,
            "retail": batch.retail_price,
        },
        "trust_breakdown": {
            "origin": 15 if origin_ok else 0,
            "quality": 15 if quality_ok else 4,
            "blockchain": 20 if chain_ok else 0,
            "documents": 10,
            "sensors": 10,
            "completeness": int(15 * completeness(db, batch_id)),
            "ai": int(10 * (1 - (batch.risk_score or 0) / 100)),
            "delivery": 5,
        },
        "digital_passport": True,
    }


@router.get("/verify/{batch_id}")
def verify(batch_id: str, db: Session = Depends(get_db)):
    result = public_verify(batch_id, db)
    if result.get("status") == "VERIFICATION_FAILED" and not result.get("batch_id"):
        raise HTTPException(404, result)
    return result


@router.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    like = f"%{q}%"
    batches = db.query(Batch).filter(
        Batch.batch_id.ilike(like)
        | Batch.farmer_name.ilike(like)
        | Batch.crop.ilike(like)
        | Batch.origin.ilike(like)
    ).limit(20).all()
    from app.blockchain.ledger import get_ledger
    from app.models.entities import ChainTransaction, Transport

    txs = db.query(ChainTransaction).filter(ChainTransaction.tx_id.ilike(like)).limit(10).all()
    vehicles = db.query(Transport).filter(Transport.vehicle_id.ilike(like)).limit(10).all()
    block = None
    if q.isdigit():
        ledger = get_ledger()
        idx = int(q)
        if 0 <= idx < len(ledger.chain):
            block = ledger.chain[idx].to_dict()
    return {
        "batches": [{"batch_id": b.batch_id, "crop": b.crop, "origin": b.origin} for b in batches],
        "transactions": [{"tx_id": t.tx_id, "batch_id": t.batch_id} for t in txs],
        "vehicles": [{"vehicle_id": v.vehicle_id, "batch_id": v.batch_id} for v in vehicles],
        "block": block,
    }
