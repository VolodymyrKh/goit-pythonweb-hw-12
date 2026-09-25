from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.schemas import MessageResponse, RequestEmail, Token, UserCreate, UserResponse
from src.services.auth import create_access_token, get_email_from_token, verify_password
from src.services.email import send_verification_email
from src.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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
    return Token(access_token=create_access_token(user.username))


@router.get("/confirmed_email/{token}", response_model=MessageResponse)
async def confirmed_email(token: str, db: AsyncSession = Depends(get_db)):
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
