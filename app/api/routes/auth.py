from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import NAV_SECTIONS
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.dto import LoginRequest, TokenResponse

router = APIRouter()


def _token(user: User) -> dict:
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        role=user.role,
        full_name=user.full_name,
        email=user.email,
    ).model_dump()


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _token(user)


@router.post("/login-form")
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _token(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "organization": user.organization,
        "location": user.location,
        "nav": NAV_SECTIONS.get(user.role, []),
    }
