"""Business logic for users.

Every method that changes a user also removes them from the Redis cache, so
``get_current_user`` never keeps serving outdated data.
"""

import hashlib

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Role, User
from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.auth import get_password_hash, hash_token
from src.services.cache import invalidate_user


class UserService:
    """User operations on top of :class:`~src.repository.users.UserRepository`.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession):
        self.repository = UserRepository(db)

    async def create_user(self, body: UserCreate) -> User:
        """Register a new user with a hashed password and a Gravatar avatar.

        Args:
            body: Registration data.

        Returns:
            The created user.

        Raises:
            HTTPException: 409 if the username or email is already taken.
        """
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

    async def get_user_by_username(self, username: str) -> User | None:
        """Return the user with the given username or ``None``."""
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """Return the user with the given email or ``None``."""
        return await self.repository.get_user_by_email(email)

    async def confirm_email(self, email: str) -> None:
        """Mark the email as confirmed and drop the cached user."""
        user = await self.repository.get_user_by_email(email)
        if user is None:
            return
        # Read before commit: attributes of committed objects are expired
        username = user.username
        await self.repository.confirm_email(email)
        await invalidate_user(username)

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        """Save a new avatar URL and drop the cached user."""
        user = await self.repository.update_avatar_url(email, url)
        if user is not None:
            await invalidate_user(user.username)
        return user

    async def reset_password(self, user: User, new_password: str) -> User:
        """Set a new password.

        The refresh token is revoked and the cached user is dropped, so the
        old sessions cannot be extended with the old credentials.
        """
        user = await self.repository.update_password(user, get_password_hash(new_password))
        await invalidate_user(user.username)
        return user

    async def save_refresh_token(self, user: User, token: str) -> None:
        """Remember the user's current refresh token (only its hash is stored)."""
        await self.repository.update_refresh_token(user, hash_token(token))

    async def revoke_refresh_token(self, user: User) -> None:
        """Forget the refresh token (logout) and drop the cached user."""
        username = user.username
        await self.repository.update_refresh_token(user, None)
        await invalidate_user(username)

    async def update_role(self, user_id: int, role: Role) -> User:
        """Change a user's role.

        Raises:
            HTTPException: 404 if the user does not exist.
        """
        user = await self.repository.update_role(user_id, role)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        await invalidate_user(user.username)
        return user


def _gravatar_url(email: str) -> str:
    """Default avatar for a new user (identicon if the email has no Gravatar)."""
    digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=identicon"


def _user_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="User with this email or username already exists",
    )
