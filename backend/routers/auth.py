import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.database import get_session
from backend.limiter import limiter
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info("user registered: id=%s email=%r", user.id, email)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    logger.info("user login: id=%s email=%r", user.id, email)
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(id=current_user.id, email=current_user.email)
