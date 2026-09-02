from __future__ import annotations

ROLES = [
    "ADMIN",
    "FARMER",
    "COLLECTION_CENTER",
    "QUALITY_INSPECTOR",
    "TRANSPORTER",
    "WAREHOUSE_MANAGER",
    "PROCESSOR",
    "DISTRIBUTOR",
    "RETAILER",
    "REGULATOR",
    "CONSUMER",
]

EVENT_PERMISSIONS = {
    "HARVEST": {"ADMIN", "FARMER"},
    "COLLECTION": {"ADMIN", "COLLECTION_CENTER"},
    "QUALITY_CHECK": {"ADMIN", "QUALITY_INSPECTOR"},
    "TRANSPORT": {"ADMIN", "TRANSPORTER"},
    "WAREHOUSE_ENTRY": {"ADMIN", "WAREHOUSE_MANAGER"},
    "WAREHOUSE_EXIT": {"ADMIN", "WAREHOUSE_MANAGER"},
    "PROCESSING": {"ADMIN", "PROCESSOR"},
    "DISTRIBUTION": {"ADMIN", "DISTRIBUTOR"},
    "RETAIL": {"ADMIN", "RETAILER"},
    "SENSOR_ANCHOR": {"ADMIN", "TRANSPORTER", "WAREHOUSE_MANAGER"},
    "DOCUMENT": {"ADMIN", "QUALITY_INSPECTOR", "REGULATOR"},
}

NAV_SECTIONS = {
    "ADMIN": "all",
    "REGULATOR": [
        "dashboard",
        "analytics",
        "batches",
        "risk",
        "iot",
        "documents",
        "blockchain",
        "recall",
        "verify",
        "users",
        "audit",
    ],
    "FARMER": ["dashboard", "batches", "create-batch", "events", "verify", "passport"],
    "COLLECTION_CENTER": ["dashboard", "batches", "events", "tracking"],
    "QUALITY_INSPECTOR": ["dashboard", "batches", "quality", "documents", "risk"],
    "TRANSPORTER": ["dashboard", "batches", "events", "tracking", "iot"],
    "WAREHOUSE_MANAGER": ["dashboard", "batches", "events", "iot"],
    "PROCESSOR": ["dashboard", "batches", "events", "sustainability"],
    "DISTRIBUTOR": ["dashboard", "batches", "events", "tracking"],
    "RETAILER": ["dashboard", "batches", "events", "verify"],
    "CONSUMER": ["verify", "scanner", "passport"],
}
