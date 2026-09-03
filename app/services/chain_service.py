from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.engine import engine, sustainability_score, trust_score
from app.blockchain.eth import commit_event
from app.blockchain.ledger import get_ledger, rebuild_from_transactions
from app.models.entities import (
    AuditLog,
    Batch,
    BlockchainBlock,
    ChainTransaction,
    Notification,
    RiskAssessment,
    SupplyChainEvent,
)
from app.qr.codes import sha256_obj


def notify(db: Session, title: str, message: str, kind: str, batch_id: str = "") -> None:
    db.add(Notification(title=title, message=message, kind=kind, batch_id=batch_id))


def audit(db: Session, actor: str, action: str, detail: str = "") -> None:
    db.add(AuditLog(actor=actor, action=action, detail=detail))


def next_batch_id(db: Session, crop: str, origin: str, year: int | None = None) -> str:
    year = year or datetime.now(timezone.utc).year
    region = origin.upper().replace(" ", "")[:12]
    crop_code = crop.upper().replace(" ", "")
    prefix = f"{crop_code}-{region}-{year}-"
    existing = db.query(Batch).filter(Batch.batch_id.like(f"{prefix}%")).count()
    return f"{prefix}{existing + 1:04d}"


def required_events() -> list[str]:
    return [
        "HARVEST",
        "COLLECTION",
        "QUALITY_CHECK",
        "TRANSPORT",
        "WAREHOUSE_ENTRY",
        "PROCESSING",
        "DISTRIBUTION",
        "RETAIL",
    ]


def completeness(db: Session, batch_id: str) -> float:
    types = {e.event_type for e in db.query(SupplyChainEvent).filter_by(batch_id=batch_id)}
    need = set(required_events())
    return len(types & need) / len(need)


def refresh_scores(db: Session, batch: Batch, extra: dict | None = None) -> None:
    extra = extra or {}
    from app.models.entities import SensorReading, Transport, QualityInspection, Document

    last = (
        db.query(SensorReading)
        .filter_by(batch_id=batch.batch_id)
        .order_by(SensorReading.id.desc())
        .first()
    )
    tr = db.query(Transport).filter_by(batch_id=batch.batch_id).order_by(Transport.id.desc()).first()
    qi = (
        db.query(QualityInspection)
        .filter_by(batch_id=batch.batch_id)
        .order_by(QualityInspection.id.desc())
        .first()
    )
    docs = db.query(Document).filter_by(batch_id=batch.batch_id).count()
    anomalies = (
        db.query(SensorReading)
        .filter_by(batch_id=batch.batch_id, anomalous=True)
        .count()
    )
    valid, _, _ = get_ledger().is_chain_valid()
    events = {e.event_type for e in db.query(SupplyChainEvent).filter_by(batch_id=batch.batch_id)}
    missing = len(set(required_events()) - events)

    risk = engine.assess(
        temperature=extra.get("temperature", last.temperature if last else 25),
        humidity=extra.get("humidity", last.humidity if last else 60),
        delay_hours=extra.get("delay_hours", tr.delay_hours if tr else 0),
        distance_km=extra.get("distance_km", tr.distance_km if tr else 40),
        quality_score=qi.quality_score if qi else batch.quality_score or 85,
        quantity_kg=batch.quantity_kg,
        missing_events=missing,
    )
    batch.risk_score = risk.score
    batch.risk_level = risk.level
    db.add(
        RiskAssessment(
            batch_id=batch.batch_id,
            score=risk.score,
            level=risk.level,
            reasons_json=json.dumps(risk.reasons),
            importance_json=json.dumps(risk.importance),
        )
    )
    t, parts = trust_score(
        origin_ok=bool(batch.origin),
        quality_ok=batch.quality_grade in {"A", "B"} and batch.quality_score >= 70,
        chain_ok=valid,
        docs_ok=docs > 0 or batch.quality_grade in {"A", "B"},
        sensors_ok=anomalies == 0,
        completeness=completeness(db, batch.batch_id),
        ai_risk=risk.score,
        delivery_ok=not tr or tr.delay_hours < 12,
    )
    batch.trust_score = t
    sus = sustainability_score(
        distance_km=tr.distance_km if tr else 40,
        delay_hours=tr.delay_hours if tr else 0,
        temp_deviation=abs((last.temperature if last else 25) - 25),
        wastage=0,
    )
    batch.sustainability_score = sus["score"]
    if risk.score >= 61:
        notify(
            db,
            "High-risk batch",
            f"{batch.batch_id} scored {risk.score} ({risk.level})",
            "HIGH_RISK",
            batch.batch_id,
        )
    if last and last.anomalous:
        notify(db, "Temperature anomaly", f"{batch.batch_id} sensor flagged", "TEMP_ANOMALY", batch.batch_id)
    if qi and qi.status == "FAILED":
        notify(db, "Quality failure", f"{batch.batch_id} failed inspection", "QUALITY_FAIL", batch.batch_id)


def reconcile_ledger(db: Session) -> dict:
    """Restore the volatile PoW chain from validated durable transaction rows."""
    rows = db.query(ChainTransaction).order_by(ChainTransaction.id.asc()).all()
    ledger = get_ledger()
    valid, _, _ = ledger.is_chain_valid()
    represented = sum(len(block.transactions) for block in ledger.chain)
    if valid and represented == len(rows):
        return {"rebuilt": False, "blocks": len(ledger.chain), "transactions": len(rows)}

    payloads: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot reconcile malformed transaction {row.tx_id}") from exc
        if not isinstance(payload, dict) or payload.get("tx_id") != row.tx_id:
            raise RuntimeError(f"Cannot reconcile invalid transaction {row.tx_id}")
        payloads.append(payload)

    rebuilt = rebuild_from_transactions(payloads)
    for block in rebuilt.chain:
        stored = db.query(BlockchainBlock).filter_by(index=block.index).first()
        if stored is None:
            stored = BlockchainBlock(index=block.index)
            db.add(stored)
        stored.timestamp = block.timestamp
        stored.previous_hash = block.previous_hash
        stored.nonce = block.nonce
        stored.hash = block.hash
        stored.tx_count = len(block.transactions)

    for index, row in enumerate(rows, start=1):
        block = rebuilt.chain[index]
        row.block_index = block.index
        event = db.query(SupplyChainEvent).filter_by(tx_id=row.tx_id).first()
        if event:
            event.block_index = block.index
            event.block_hash = block.hash
    db.commit()
    return {"rebuilt": True, "blocks": len(rebuilt.chain), "transactions": len(rows)}


def record_event(
    db: Session,
    *,
    batch: Batch,
    event_type: str,
    actor_email: str,
    actor_role: str,
    location: str,
    metadata: dict,
    document_hash: str = "",
    lat: float = 0,
    lng: float = 0,
) -> dict:
    tx_id = uuid.uuid4().hex[:16]
    payload = {
        "tx_id": tx_id,
        "batch_id": batch.batch_id,
        "event_type": event_type,
        "actor": actor_email,
        "actor_role": actor_role,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": location,
        "document_hash": document_hash,
        "metadata": metadata,
    }
    data_hash = sha256_obj(json.dumps(payload, sort_keys=True, default=str))
    payload["data_hash"] = data_hash
    receipt = commit_event(payload)

    db.add(
        SupplyChainEvent(
            batch_id=batch.batch_id,
            event_type=event_type,
            actor_email=actor_email,
            actor_role=actor_role,
            location=location,
            lat=lat,
            lng=lng,
            metadata_json=json.dumps(metadata),
            document_hash=document_hash,
            tx_id=tx_id,
            block_index=receipt["block_index"],
            block_hash=receipt["block_hash"],
            data_hash=data_hash,
        )
    )
    db.add(
        ChainTransaction(
            tx_id=tx_id,
            block_index=receipt["block_index"],
            batch_id=batch.batch_id,
            event_type=event_type,
            actor=actor_email,
            payload_json=json.dumps(payload),
        )
    )
    block = get_ledger().chain[receipt["block_index"]]
    existing = db.query(BlockchainBlock).filter_by(index=block.index).first()
    if not existing:
        db.add(
            BlockchainBlock(
                index=block.index,
                timestamp=block.timestamp,
                previous_hash=block.previous_hash,
                nonce=block.nonce,
                hash=block.hash,
                tx_count=len(block.transactions),
            )
        )
    batch.current_location = location
    batch.current_stakeholder = actor_role
    refresh_scores(db, batch, extra=metadata)
    if completeness(db, batch.batch_id) >= 0.75:
        batch.verification_status = "VERIFIED"
    audit(db, actor_email, "EVENT", f"{event_type} {batch.batch_id} {tx_id}")
    db.commit()
    db.refresh(batch)
    return {**receipt, "data_hash": data_hash, "verification_status": "ANCHORED"}
