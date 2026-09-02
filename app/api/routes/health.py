from datetime import datetime, timezone

from fastapi import APIRouter

from app.blockchain.eth import mode_status
from app.blockchain.ledger import get_ledger
from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health():
    from app.core.database import SessionLocal
    from app.models.entities import Batch, SensorReading, SupplyChainEvent, User

    valid, reason, failed = get_ledger().is_chain_valid()
    db = SessionLocal()
    try:
        stats = {
            "batches": db.query(Batch).count(),
            "verified": db.query(Batch).filter(Batch.verification_status == "VERIFIED").count(),
            "events": db.query(SupplyChainEvent).count(),
            "users": db.query(User).count(),
            "temp_alerts": db.query(SensorReading).filter_by(anomalous=True).count(),
        }
    finally:
        db.close()
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "chain_valid": valid,
        "reason": reason,
        "failed_block": failed,
        "block_height": get_ledger().get_latest_block().index,
        "blockchain": mode_status(),
        "frontend_url": settings.frontend_url,
        "stats": stats,
    }
