from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.iot.simulator import simulator
from app.models.entities import Batch, SensorReading, User
from app.schemas.dto import SensorIn
from app.api.routes.iot import _store
from app.services.seed import seed_if_empty

router = APIRouter()

DEMO_STEPS = [
    "Register farmer (demo account already seeded)",
    "Open batch RICE-KONASEEMA-2026-0001",
    "Show generated QR",
    "Review HARVEST event",
    "Review quality inspection (12.4% moisture, Grade A)",
    "Start / review transport (26°C, 65% humidity, 82 km)",
    "Open IoT monitoring",
    "Inject abnormal 89°C reading",
    "Inspect AI risk explanation",
    "Open blockchain explorer + consumer verify + tamper demo",
]


@router.post("/demo/prepare")
def prepare(db: Session = Depends(get_db), _=Depends(require_roles("ADMIN", "REGULATOR"))):
    seed_if_empty(db)
    return {"ready": True, "steps": DEMO_STEPS, "hero_batch": "RICE-KONASEEMA-2026-0001"}


@router.get("/demo/steps")
def steps():
    return {"steps": DEMO_STEPS}


@router.post("/demo/spike/{batch_id}")
def spike(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "REGULATOR", "TRANSPORTER"))):
    if not db.query(Batch).filter_by(batch_id=batch_id).first():
        return {"ok": False}
    row = _store(db, SensorIn(batch_id=batch_id, temperature=89.0, humidity=65, spike=True))
    return {
        "temperature": row.temperature,
        "humidity": row.humidity,
        "anomalous": row.anomalous,
        "batch_id": batch_id,
    }
