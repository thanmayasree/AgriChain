from __future__ import annotations

import json
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.entities import Batch, SupplyChainEvent

router = APIRouter()
STAGES = ["HARVEST", "COLLECTION", "PROCESSING", "QUALITY_CHECK", "PACKAGING", "WAREHOUSE_ENTRY", "TRANSPORT", "RETAIL"]
CATEGORIES = {
    "Rice":"Cereals","Basmati Rice":"Cereals","Sona Masuri Rice":"Cereals","Wheat":"Cereals","Maize":"Cereals",
    "Cotton":"Fibre Crops","Groundnut":"Oilseeds","Sugarcane":"Cash Crops","Red Chilli":"Spices","Green Chilli":"Vegetables",
    "Turmeric":"Spices","Black Pepper":"Spices","Cardamom":"Spices","Cumin":"Spices","Coriander":"Spices","Tomato":"Vegetables",
    "Onion":"Vegetables","Potato":"Vegetables","Mango":"Fruits","Banana":"Fruits","Coconut":"Plantation Crops","Cashew":"Plantation Crops",
    "Coffee":"Beverages","Tea":"Beverages","Soybean":"Oilseeds","Green Gram":"Pulses","Black Gram":"Pulses","Chickpea":"Pulses","Lentils":"Pulses","Pigeon Pea":"Pulses",
}

def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def batch_payload(db: Session, b: Batch) -> dict:
    events = db.query(SupplyChainEvent).filter_by(batch_id=b.batch_id).order_by(SupplyChainEvent.id).all()
    by_type = {e.event_type: e for e in events if e.event_type in STAGES}
    stages, abnormalities = [], []
    for index, name in enumerate(STAGES, 1):
        e = by_type.get(name)
        meta = json.loads(e.metadata_json or "{}") if e else {}
        abnormal = meta.get("abnormality")
        if abnormal:
            abnormalities.append({**abnormal, "stage": name, "stage_index": index})
        stages.append({
            "index": index, "name": name, "registered": bool(e),
            "location": e.location if e else None, "timestamp": e.created_at.isoformat() if e else None,
            "actor": e.actor_email if e else None, "block_index": e.block_index if e else None,
            "block_hash": e.block_hash if e else None, "data_hash": e.data_hash if e else None,
            "evidence": meta.get("evidence") or (abnormal or {}).get("evidence"),
        })
    completed = sum(1 for s in stages if s["registered"])
    if completed < 8 and not abnormalities and b.verification_status == "UNABLE_TO_VERIFY":
        missing = stages[completed]
        abnormalities.append({"type":"INACCESSIBLE_MISSING_DATA","stage":missing["name"],"stage_index":missing["index"],"what":"Required stage data is unavailable.","why":"The responsible operator did not complete synchronization before handover.","how":"The stage has no signed event, timestamp or ledger hash.","where":b.current_location or b.origin,"when":"Not recorded","expected":"Signed stage record and evidence","actual":"No accessible record","difference":"One required stage record missing","impact":"End-to-end verification cannot be completed.","current_status":"Awaiting operator resubmission","risk":"HIGH","evidence":None})
    status = abnormalities[0]["type"] if abnormalities else ("FULLY_REGISTERED" if completed == 8 else "PARTIALLY_REGISTERED")
    traceability = max(0, round(completed / 8 * 100 - (8 if abnormalities else 0)))
    return {"batch_id":b.batch_id,"product":b.crop,"product_slug":slugify(b.crop),"origin":b.origin,"current_location":b.current_location,"quantity_kg":b.quantity_kg,"registration_progress":completed,"total_stages":8,"status":status,"risk_score":round(b.risk_score),"risk_level":b.risk_level,"traceability_score":traceability,"verification_status":b.verification_status,"stages":stages,"abnormalities":abnormalities,"qr_url":f"/api/batches/{b.batch_id}/qr","verification_url":f"{settings.frontend_url}/verify/{b.batch_id}"}

@router.get("")
def products(db: Session = Depends(get_db)):
    rows = db.query(Batch).order_by(Batch.crop, Batch.id).all()
    grouped = defaultdict(list)
    for b in rows:
        grouped[b.crop].append(batch_payload(db, b))
    items = []
    for crop, batches in grouped.items():
        items.append({"slug":slugify(crop),"name":crop,"category":CATEGORIES.get(crop,"Agricultural Produce"),"origin":batches[0]["origin"],"total_batches":len(batches),"fully_registered":sum(x["registration_progress"] == 8 and not x["abnormalities"] for x in batches),"partially_registered":sum(x["registration_progress"] < 8 for x in batches),"abnormal_batches":sum(bool(x["abnormalities"]) for x in batches),"average_traceability":round(sum(x["traceability_score"] for x in batches)/len(batches))})
    return {"items":sorted(items,key=lambda x:x["name"]),"total":len(items)}

@router.get("/{slug}")
def product(slug: str, db: Session = Depends(get_db)):
    batches = [batch_payload(db,b) for b in db.query(Batch).order_by(Batch.id).all() if slugify(b.crop)==slug]
    if not batches: raise HTTPException(404,"Unknown product")
    crop=batches[0]["product"]
    return {"slug":slug,"name":crop,"category":CATEGORIES.get(crop,"Agricultural Produce"),"origin":batches[0]["origin"],"total_batches":len(batches),"fully_registered":sum(x["registration_progress"]==8 and not x["abnormalities"] for x in batches),"partially_registered":sum(x["registration_progress"]<8 for x in batches),"abnormal_batches":sum(bool(x["abnormalities"]) for x in batches),"batches":batches}

@router.get("/{slug}/batches/{batch_id}")
def passport(slug: str, batch_id: str, db: Session = Depends(get_db)):
    b=db.query(Batch).filter_by(batch_id=batch_id).first()
    if not b or slugify(b.crop)!=slug: raise HTTPException(404,"Unknown product batch")
    return batch_payload(db,b)
