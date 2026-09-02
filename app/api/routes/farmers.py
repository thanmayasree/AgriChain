from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Farmer, User
from app.schemas.dto import FarmerCreate

router = APIRouter()


@router.get("")
def list_farmers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [
        {
            "id": f.id,
            "farmer_code": f.farmer_code,
            "farm_name": f.farm_name,
            "region": f.region,
            "village": f.village,
            "lat": f.lat,
            "lng": f.lng,
            "phone": f.phone,
        }
        for f in db.query(Farmer).all()
    ]


@router.post("")
def create_farmer(
    body: FarmerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "FARMER", "REGULATOR")),
):
    code = f"FARM-{body.region.upper().replace(' ', '')[:8]}-{db.query(Farmer).count() + 1:03d}"
    if db.query(Farmer).filter_by(user_id=user.id).first() and user.role == "FARMER":
        raise HTTPException(400, "Farmer profile already exists")
    f = Farmer(
        user_id=user.id,
        farmer_code=code,
        farm_name=body.farm_name,
        region=body.region,
        village=body.village,
        lat=body.lat,
        lng=body.lng,
        phone=body.phone,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return {"id": f.id, "farmer_code": f.farmer_code}
