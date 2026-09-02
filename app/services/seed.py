from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.engine import calculate_quality_score
from app.core.rbac import ROLES
from app.core.security import hash_password
from app.iot.simulator import simulator
from app.models.entities import (
    Batch,
    Document,
    Farmer,
    QualityInspection,
    SensorReading,
    Transport,
    User,
)
from app.qr.codes import generate_qr_png, sha256_obj
from app.services.chain_service import next_batch_id, record_event, refresh_scores

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")

ACCOUNTS = [
    ("admin@agrichain.local", "Administrator", "ADMIN", "AgriChain HQ", "Amaravati"),
    ("farmer@agrichain.local", "Ravi Kumar", "FARMER", "Konaseema Farms", "Konaseema"),
    ("collection@agrichain.local", "Sita Collection", "COLLECTION_CENTER", "East Godavari CC", "Amalapuram"),
    ("inspector@agrichain.local", "Dr. Prasad", "QUALITY_INSPECTOR", "AP Quality Lab", "Kakinada"),
    ("transporter@agrichain.local", "Naveen Logistics", "TRANSPORTER", "Delta Cold Chain", "Rajahmundry"),
    ("warehouse@agrichain.local", "Lakshmi Warehouse", "WAREHOUSE_MANAGER", "Eluru Cold Store", "Eluru"),
    ("processor@agrichain.local", "Godavari Mills", "PROCESSOR", "Premium Rice Mill", "Bhimavaram"),
    ("distributor@agrichain.local", "Coastal Distro", "DISTRIBUTOR", "AP Distribution", "Vijayawada"),
    ("retailer@agrichain.local", "GreenMart", "RETAILER", "GreenMart Retail", "Visakhapatnam"),
    ("regulator@agrichain.local", "FSSAI Observer", "REGULATOR", "Food Safety Authority", "Vijayawada"),
    ("consumer@agrichain.local", "Priya Consumer", "CONSUMER", "Public", "Hyderabad"),
]


def seed_if_empty(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    if not DEMO_PASSWORD:
        raise RuntimeError("DEMO_PASSWORD must be configured before initial database seeding")
    users: dict[str, User] = {}
    for email, name, role, org, loc in ACCOUNTS:
        u = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(DEMO_PASSWORD),
            role=role,
            organization=org,
            location=loc,
        )
        db.add(u)
        users[role] = u
    db.flush()

    farmer = Farmer(
        user_id=users["FARMER"].id,
        farmer_code="FARM-KONA-001",
        farm_name="Konaseema Farms",
        region="Konaseema",
        village="Amalapuram Rural",
        lat=16.578,
        lng=82.006,
        phone="9000000001",
    )
    db.add(farmer)
    db.flush()

    specs = [
        {
            "crop": "Rice",
            "variety": "Sona Masuri",
            "qty": 2500,
            "origin": "Konaseema",
            "dest": "Visakhapatnam",
            "grade_path": "good",
            "harvest": "2026-08-10",
            "prices": (42, 58, 72, 85),
            "force_id": "RICE-KONASEEMA-2026-0001",
        },
        {
            "crop": "Rice",
            "variety": "MTU-1010",
            "qty": 1800,
            "origin": "Amalapuram",
            "dest": "Vijayawada",
            "grade_path": "mid",
            "harvest": "2026-08-12",
            "prices": (38, 52, 66, 78),
            "force_id": "RICE-AMALAPURAM-2026-0002",
        },
        {
            "crop": "Chilli",
            "variety": "Guntur Sannam",
            "qty": 640,
            "origin": "Guntur",
            "dest": "Hyderabad",
            "grade_path": "failed",
            "harvest": "2026-08-08",
            "prices": (120, 150, 190, 240),
            "force_id": "CHILLI-GUNTUR-2026-0003",
        },
        {
            "crop": "Maize",
            "variety": "DHM-117",
            "qty": 3200,
            "origin": "Eluru",
            "dest": "Vijayawada",
            "grade_path": "risk",
            "harvest": "2026-08-14",
            "prices": (18, 24, 31, 38),
            "force_id": "MAIZE-ELURU-2026-0004",
        },
    ]

    actor_map = {
        "HARVEST": (users["FARMER"], "Konaseema"),
        "COLLECTION": (users["COLLECTION_CENTER"], "Amalapuram Collection Center"),
        "QUALITY_CHECK": (users["QUALITY_INSPECTOR"], "Kakinada Quality Lab"),
        "TRANSPORT": (users["TRANSPORTER"], "NH-16 corridor"),
        "WAREHOUSE_ENTRY": (users["WAREHOUSE_MANAGER"], "Eluru Cold Store"),
        "WAREHOUSE_EXIT": (users["WAREHOUSE_MANAGER"], "Eluru Cold Store"),
        "PROCESSING": (users["PROCESSOR"], "Bhimavaram Mill"),
        "DISTRIBUTION": (users["DISTRIBUTOR"], "Vijayawada Hub"),
        "RETAIL": (users["RETAILER"], "GreenMart Visakhapatnam"),
    }

    for spec in specs:
        bid = spec["force_id"]
        existing_count = db.query(Batch).filter(Batch.batch_id == bid).first()
        if existing_count:
            continue
        # keep generator in sync for later user-created batches
        _ = next_batch_id(db, spec["crop"], spec["origin"], 2026)
        fp, pp, dp, rp = spec["prices"]
        batch = Batch(
            batch_id=bid,
            crop=spec["crop"],
            variety=spec["variety"],
            quantity_kg=spec["qty"],
            harvest_date=spec["harvest"],
            origin=spec["origin"],
            farmer_id=farmer.id,
            farmer_name=users["FARMER"].full_name,
            expected_destination=spec["dest"],
            current_location=spec["origin"],
            farmer_price=fp,
            processor_price=pp,
            distributor_price=dp,
            retail_price=rp,
            payment_status="PAID" if spec["grade_path"] == "good" else "PENDING",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        generate_qr_png(bid)

        path = spec["grade_path"]
        events = ["HARVEST", "COLLECTION", "QUALITY_CHECK"]
        if path != "failed":
            events += ["TRANSPORT", "WAREHOUSE_ENTRY", "WAREHOUSE_EXIT", "PROCESSING", "DISTRIBUTION"]
        if path == "good":
            events.append("RETAIL")

        for et in events:
            actor, loc = actor_map[et]
            meta = {"note": f"{et} recorded for demo"}
            if et == "TRANSPORT":
                meta.update({"distance_km": 82 if path != "risk" else 210, "delay_hours": 3 if path != "risk" else 31})
            record_event(
                db,
                batch=batch,
                event_type=et,
                actor_email=actor.email,
                actor_role=actor.role,
                location=loc,
                metadata=meta,
                lat=16.5,
                lng=82.0,
            )
            db.refresh(batch)

        moisture = 12.4 if path == "good" else 14.8 if path == "mid" else 19.5 if path == "failed" else 13.1
        fm = 0.6 if path == "good" else 1.4 if path == "mid" else 4.8 if path == "failed" else 1.1
        qscore, grade, status = calculate_quality_score(moisture, fm)
        qi = QualityInspection(
            batch_id=bid,
            moisture=moisture,
            foreign_matter=fm,
            grade=grade,
            quality_score=qscore,
            status=status,
            inspector=users["QUALITY_INSPECTOR"].email,
            location="Kakinada Quality Lab",
            inspection_date="2026-08-11",
            certificate_hash=sha256_obj(f"{bid}-cert"),
        )
        db.add(qi)
        batch.quality_grade = grade
        batch.quality_score = qscore
        db.add(
            Document(
                batch_id=bid,
                filename=f"{bid}-quality.txt",
                doc_type="QUALITY_CERTIFICATE",
                sha256=qi.certificate_hash,
                stored_path="",
                uploaded_by=users["QUALITY_INSPECTOR"].email,
            )
        )

        dist = 82 if path != "risk" else 210
        delay = 3 if path != "risk" else 31
        db.add(
            Transport(
                batch_id=bid,
                vehicle_id="AP-39-CC-8821",
                origin=spec["origin"],
                destination=spec["dest"],
                origin_lat=16.578,
                origin_lng=82.006,
                dest_lat=17.6868,
                dest_lng=83.2185,
                current_lat=16.9,
                current_lng=82.4,
                distance_km=dist,
                delay_hours=delay,
                progress=0.82 if path == "good" else 0.45,
                status="ARRIVED" if path == "good" else "IN_TRANSIT",
            )
        )

        for i in range(12):
            spike = path == "risk" and i == 10
            r = simulator.reading(batch_id=bid, lat=16.6 + i * 0.02, lng=82.05 + i * 0.03, spike=spike)
            anomalous = r["temperature"] > 40
            db.add(
                SensorReading(
                    batch_id=bid,
                    temperature=r["temperature"],
                    humidity=r["humidity"],
                    lat=r["lat"],
                    lng=r["lng"],
                    speed_kmh=r["speed_kmh"],
                    vibration=r["vibration"],
                    anomalous=anomalous,
                )
            )
        refresh_scores(db, batch)
        db.commit()

    # unused roles list kept for documentation
    assert set(r for _, _, r, _, _ in ACCOUNTS) <= set(ROLES)
