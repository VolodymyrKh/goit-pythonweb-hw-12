"""Authentication routes: registration, login, tokens, email confirmation and password reset."""

import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.database.models import User
from src.schemas import (
    MessageResponse,
    RefreshTokenRequest,
    RequestEmail,
    ResetPassword,
    Token,
    UserCreate,
    UserResponse,
)
from src.services.auth import (
    create_access_token,
    create_refresh_token,
    create_reset_password_token,
    decode_reset_password_token,
    get_current_user,
    get_email_from_token,
    get_username_from_refresh_token,
    hash_token,
    is_reset_token_current,
    verify_password,
)
from src.services.email import send_password_reset_email, send_verification_email
from src.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "services" / "templates")


async def _issue_tokens(user_service: UserService, user: User) -> Token:
    """Create a new access/refresh pair and remember the refresh token."""
    access_token = create_access_token(user.username)
    refresh_token = create_refresh_token(user.username)
    await user_service.save_refresh_token(user, refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and send an email confirmation link.

    Returns 409 if the username or email is already taken.
    """
    user_service = UserService(db)
    user = await user_service.create_user(body)
    background_tasks.add_task(
        send_verification_email, user.email, user.username, str(request.base_url)
    )
    return user


@router.post("/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Log in with username and password and get an access/refresh token pair.

    Returns 401 if the credentials are wrong or the email is not confirmed.
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email is not confirmed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _issue_tokens(user_service, user)


@router.post("/refresh", response_model=Token)
async def refresh_tokens(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access/refresh token pair.

    Refresh tokens are rotated: each one can be used only once. Reusing an old
    refresh token (or one revoked by logout or a password reset) returns 401.
    """
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = get_username_from_refresh_token(body.refresh_token)
    if username is None:
        raise invalid_token
    user_service = UserService(db)
    user = await user_service.get_user_by_username(username)
    if (
        user is None
        or user.refresh_token_hash is None
        or not secrets.compare_digest(user.refresh_token_hash, hash_token(body.refresh_token))
    ):
        raise invalid_token
    return await _issue_tokens(user_service, user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Revoke the current refresh token.

    The access token stays valid until it expires, so it should be short-lived.
    """
    user_service = UserService(db)
    db_user = await user_service.get_user_by_username(user.username)
    await user_service.revoke_refresh_token(db_user)
    return {"message": "Logged out"}


@router.get("/confirmed_email/{token}", response_model=MessageResponse)
async def confirmed_email(token: str, db: AsyncSession = Depends(get_db)):
    """Confirm the email address using the token from the confirmation link."""
    email = get_email_from_token(token)
    user_service = UserService(db)
    user = await user_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Verification error"
        )
    if user.confirmed:
        return {"message": "Your email is already confirmed"}
    await user_service.confirm_email(email)
    return {"message": "Email confirmed"}


@router.post("/request_email", response_model=MessageResponse)
async def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send the email confirmation link again."""
    user_service = UserService(db)
    user = await user_service.get_user_by_email(body.email)
    if user is not None and user.confirmed:
        return {"message": "Your email is already confirmed"}
    if user is not None:
        background_tasks.add_task(
            send_verification_email, user.email, user.username, str(request.base_url)
        )
    # Same answer whether or not the user exists, so emails cannot be enumerated
    return {"message": "Check your email for confirmation"}


@router.post("/request_password_reset", response_model=MessageResponse)
async def request_password_reset(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link to the given email.

    The response is the same whether or not the email is registered, so the
    endpoint cannot be used to find out which emails have accounts.
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_email(body.email)
    if user is not None:
        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            user.username,
            str(request.base_url),
            create_reset_password_token(user),
        )
    return {"message": "If this email is registered, a password reset link has been sent"}


@router.get("/reset_password/{token}", response_class=HTMLResponse, include_in_schema=False)
async def reset_password_form(token: str, request: Request):
    """HTML page with a form for a new password, opened from the reset email."""
    decode_reset_password_token(token)
    return templates.TemplateResponse(
        request,
        "reset_password_form.html",
        {"token": token, "action": str(request.url_for("reset_password"))},
    )


@router.post("/reset_password", response_model=MessageResponse)
async def reset_password(body: ResetPassword, db: AsyncSession = Depends(get_db)):
    """Set a new password using the token from the reset email.

    The token is single-use: after the password changes, the token no longer
    matches and returns 400. The refresh token is revoked as well.
    """
    email, fingerprint = decode_reset_password_token(body.token)
    user_service = UserService(db)
    user = await user_service.get_user_by_email(email)
    if user is None or not is_reset_token_current(user, fingerprint):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    await user_service.reset_password(user, body.new_password)
    return {"message": "Password has been reset"}
