from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
import uuid
from sqlalchemy.orm import Session
from .database import get_db
from .models import RevokedToken, User
from config.setting import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class SecurityService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if len(plain_password.encode("utf-8")) > 72:
            return False
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    @staticmethod
    def create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire, "type": token_type, "jti": str(uuid.uuid4())})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def _decode_token(token: str, expected_type: str, db: Session | None = None) -> dict:
    token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if not payload.get("sub") or payload.get("type") != expected_type or not payload.get("jti"):
            raise token_exception
        if db is not None and db.query(RevokedToken).filter(RevokedToken.jti == payload["jti"]).first():
            raise token_exception
        return payload
    except JWTError:
        raise token_exception

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = _decode_token(token, "access", db)
    user_id = payload["sub"]
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_user_from_refresh_token(refresh_token: str, db: Session):
    payload = _decode_token(refresh_token, "refresh", db)
    user = db.query(User).filter(User.user_id == payload["sub"]).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user

def revoke_token(token: str, db: Session) -> None:
    payload = _decode_token(token, "refresh")
    if db.query(RevokedToken).filter(RevokedToken.jti == payload["jti"]).first() is None:
        db.add(RevokedToken(
            jti=payload["jti"],
            expires_at=datetime.utcfromtimestamp(payload["exp"]),
        ))