from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.rbac import ROLES
from app.core.security import hash_password
from app.models.entities import AuditLog, User
from app.schemas.dto import UserCreate
from app.services.chain_service import audit

router = APIRouter()


@router.get("")
def list_users(db: Session = Depends(get_db), _=Depends(require_roles("ADMIN", "REGULATOR"))):
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "organization": u.organization,
            "location": u.location,
            "is_active": u.is_active,
        }
        for u in db.query(User).all()
    ]


@router.get("/roles")
def roles():
    return {"roles": ROLES}


@router.post("")
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles("ADMIN"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Email already exists")
    u = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        organization=body.organization,
        location=body.location,
    )
    db.add(u)
    audit(db, admin.email, "CREATE_USER", body.email)
    db.commit()
    return {"ok": True, "email": u.email}


@router.get("/audit")
def audit_logs(db: Session = Depends(get_db), _=Depends(require_roles("ADMIN", "REGULATOR"))):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()
    return [
        {"id": r.id, "actor": r.actor, "action": r.action, "detail": r.detail, "created_at": r.created_at.isoformat()}
        for r in rows
    ]
