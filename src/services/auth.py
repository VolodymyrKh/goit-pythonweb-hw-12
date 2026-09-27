"""Password hashing, JWT tokens and FastAPI dependencies for the current user.

Every token carries a ``scope`` claim, so a token issued for one purpose
(e.g. email confirmation) can never be used for another (e.g. API access).
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import Role, User
from src.repository.users import UserRepository
from src.services.cache import cache_user, get_cached_user

ACCESS_TOKEN_SCOPE = "access_token"
REFRESH_TOKEN_SCOPE = "refresh_token"
EMAIL_TOKEN_SCOPE = "email_token"
RESET_TOKEN_SCOPE = "reset_password_token"

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_password_hash(password: str) -> str:
    """Hash a password with Argon2.

    Args:
        password: Plain-text password.

    Returns:
        The password hash to store in the database.
    """
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored hash.

    Args:
        plain_password: Password provided by the user.
        hashed_password: Hash stored in the database.

    Returns:
        ``True`` if the password matches.
    """
    return password_hash.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token, used to store refresh tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def _password_fingerprint(hashed_password: str) -> str:
    """Short fingerprint of the current password hash.

    Embedded in password reset tokens: once the password changes, the
    fingerprint changes too and every previously issued reset token becomes
    invalid, which makes reset links single-use.
    """
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def _create_token(subject: str, scope: str, expires_in: int, **claims) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        **claims,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str, scope: str) -> dict | None:
    """Return the token payload if the token is valid and has the given scope."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("scope") != scope or not payload.get("sub"):
        return None
    return payload


def create_access_token(username: str) -> str:
    """Create a short-lived access token used to call the API.

    Args:
        username: Username stored in the ``sub`` claim.

    Returns:
        Encoded JWT.
    """
    return _create_token(username, ACCESS_TOKEN_SCOPE, settings.JWT_EXPIRATION_SECONDS)


def create_refresh_token(username: str) -> str:
    """Create a long-lived refresh token used to obtain a new token pair.

    A random ``jti`` claim makes every refresh token unique, even when two are
    issued within the same second.

    Args:
        username: Username stored in the ``sub`` claim.

    Returns:
        Encoded JWT.
    """
    return _create_token(
        username,
        REFRESH_TOKEN_SCOPE,
        settings.JWT_REFRESH_EXPIRATION_SECONDS,
        jti=secrets.token_hex(16),
    )


def get_username_from_refresh_token(token: str) -> str | None:
    """Return the username from a valid refresh token, otherwise ``None``."""
    payload = _decode_token(token, REFRESH_TOKEN_SCOPE)
    return payload["sub"] if payload else None


def create_email_token(email: str) -> str:
    """Create a token for the email confirmation link.

    Args:
        email: Email address to confirm.

    Returns:
        Encoded JWT.
    """
    return _create_token(email, EMAIL_TOKEN_SCOPE, settings.EMAIL_TOKEN_EXPIRATION_SECONDS)


def get_email_from_token(token: str) -> str:
    """Return the email from an email confirmation token.

    Args:
        token: Token from the confirmation link.

    Returns:
        The email address to confirm.

    Raises:
        HTTPException: 400 if the token is invalid, expired or has another scope.
    """
    payload = _decode_token(token, EMAIL_TOKEN_SCOPE)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    return payload["sub"]


def create_reset_password_token(user: User) -> str:
    """Create a single-use token for the password reset link.

    Args:
        user: User who requested the reset.

    Returns:
        Encoded JWT bound to the user's current password.
    """
    return _create_token(
        user.email,
        RESET_TOKEN_SCOPE,
        settings.RESET_TOKEN_EXPIRATION_SECONDS,
        pwd=_password_fingerprint(user.hashed_password),
    )


def decode_reset_password_token(token: str) -> tuple[str, str]:
    """Decode a password reset token.

    Args:
        token: Token from the reset link.

    Returns:
        A ``(email, password_fingerprint)`` pair.

    Raises:
        HTTPException: 400 if the token is invalid, expired or has another scope.
    """
    payload = _decode_token(token, RESET_TOKEN_SCOPE)
    if payload is None or "pwd" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    return payload["sub"], payload["pwd"]


def is_reset_token_current(user: User, fingerprint: str) -> bool:
    """Check that a reset token was issued for the user's current password."""
    return secrets.compare_digest(
        _password_fingerprint(user.hashed_password), fingerprint
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """FastAPI dependency that returns the user the access token belongs to.

    The user is taken from the Redis cache when possible; on a cache miss it
    is loaded from the database and cached.

    Args:
        token: Bearer access token from the ``Authorization`` header.
        db: Database session.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = _decode_token(token, ACCESS_TOKEN_SCOPE)
    if payload is None:
        raise credentials_exception
    username = payload["sub"]

    user = await get_cached_user(username)
    if user is not None:
        return user

    user = await UserRepository(db).get_user_by_username(username)
    if user is None:
        raise credentials_exception
    await cache_user(user)
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that allows only administrators.

    Args:
        user: The authenticated user.

    Returns:
        The same user if they have the ``admin`` role.

    Raises:
        HTTPException: 403 if the user is not an administrator.
    """
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action",
        )
    return user
