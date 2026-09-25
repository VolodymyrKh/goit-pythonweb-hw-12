from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.repository.users import UserRepository

ACCESS_TOKEN_SCOPE = "access_token"
EMAIL_TOKEN_SCOPE = "email_token"

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def _create_token(subject: str, scope: str, expires_in: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str, scope: str) -> str | None:
    """Return the token subject if the token is valid and has the given scope."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("scope") != scope:
        return None
    return payload.get("sub")


def create_access_token(username: str) -> str:
    return _create_token(username, ACCESS_TOKEN_SCOPE, settings.JWT_EXPIRATION_SECONDS)


def create_email_token(email: str) -> str:
    return _create_token(email, EMAIL_TOKEN_SCOPE, settings.EMAIL_TOKEN_EXPIRATION_SECONDS)


def get_email_from_token(token: str) -> str:
    email = _decode_token(token, EMAIL_TOKEN_SCOPE)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    return email


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = _decode_token(token, ACCESS_TOKEN_SCOPE)
    if username is None:
        raise credentials_exception
    user = await UserRepository(db).get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user
