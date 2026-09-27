"""User routes: current user profile, avatar and roles."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.schemas import RoleUpdate, UserResponse
from src.services.auth import get_current_admin_user, get_current_user
from src.services.limiter import limiter
from src.services.upload_file import UploadFileService
from src.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


@router.get(
    "/me",
    response_model=UserResponse,
    description="Return the current user. No more than 10 requests per minute.",
)
@limiter.limit("10/minute")
async def me(request: Request, user: User = Depends(get_current_user)):
    """Return the authenticated user (served from the Redis cache when possible)."""
    return user


@router.patch("/avatar", response_model=UserResponse)
async def update_avatar_user(
    file: UploadFile = File(),
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the default avatar with an uploaded image. Administrators only.

    The image is uploaded to Cloudinary and cropped to 250x250.
    Returns 403 for regular users, 415 for non-images and 413 for files over 5 MB.
    """
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be an image",
        )
    if file.size is not None and file.size > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Avatar must be smaller than 5 MB",
        )

    upload_service = UploadFileService(
        settings.CLOUDINARY_NAME,
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    )
    avatar_url = await run_in_threadpool(
        upload_service.upload_file, file, user.username
    )

    user_service = UserService(db)
    return await user_service.update_avatar_url(user.email, avatar_url)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    body: RoleUpdate,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role. Administrators only.

    An administrator cannot remove their own admin role, so the application
    cannot be left without administrators by accident.
    """
    if user_id == admin.id and body.role != admin.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )
    user_service = UserService(db)
    return await user_service.update_role(user_id, body.role)
