import hashlib

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.auth import get_password_hash


class UserService:
    def __init__(self, db: AsyncSession):
        self.repository = UserRepository(db)

    async def create_user(self, body: UserCreate):
        existing = await self.repository.get_user_by_username_or_email(
            body.username, body.email
        )
        if existing is not None:
            raise _user_conflict()
        try:
            return await self.repository.create_user(
                body, get_password_hash(body.password), _gravatar_url(body.email)
            )
        except IntegrityError:
            await self.repository.db.rollback()
            raise _user_conflict()

    async def get_user_by_username(self, username: str):
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str):
        return await self.repository.get_user_by_email(email)

    async def confirm_email(self, email: str):
        return await self.repository.confirm_email(email)

    async def update_avatar_url(self, email: str, url: str):
        return await self.repository.update_avatar_url(email, url)


def _gravatar_url(email: str) -> str:
    """Default avatar for a new user (identicon if the email has no Gravatar)."""
    digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=identicon"


def _user_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="User with this email or username already exists",
    )
