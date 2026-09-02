from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import qrcode

from app.core.config import settings


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: str) -> str:
    return hashlib.sha256(obj.encode()).hexdigest()


def verify_url(batch_id: str) -> str:
    return f"{settings.frontend_url}/verify/{batch_id}"


def generate_qr_png(batch_id: str) -> Path:
    url = verify_url(batch_id)
    img = qrcode.make(url)
    path = Path(settings.qr_dir) / f"{batch_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def generate_qr_bytes(batch_id: str) -> bytes:
    buf = BytesIO()
    qrcode.make(verify_url(batch_id)).save(buf, format="PNG")
    return buf.getvalue()
