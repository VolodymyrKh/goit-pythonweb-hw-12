"""Database access for users."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Role, User
from src.schemas import UserCreate


class UserRepository:
    """CRUD operations on the ``users`` table.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return the user with the given id or ``None``."""
        return await self.db.get(User, user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Return the user with the given username or ``None``."""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Return the user with the given email or ``None``."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username_or_email(
        self, username: str, email: str
    ) -> User | None:
        """Return a user that has either the given username or email.

        Used during registration to detect conflicts.
        """
        stmt = select(User).where(or_(User.username == username, User.email == email))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_user(
        self, body: UserCreate, hashed_password: str, avatar: str | None = None
    ) -> User:
        """Create a new user.

        Args:
            body: Registration data.
            hashed_password: Already hashed password.
            avatar: Default avatar URL.

        Returns:
            The created user.
        """
        user = User(
            username=body.username,
            email=body.email,
            hashed_password=hashed_password,
            avatar=avatar,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def confirm_email(self, email: str) -> None:
        """Mark the user's email as confirmed."""
        user = await self.get_user_by_email(email)
        if user is not None:
            user.confirmed = True
            await self.db.commit()

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        """Set a new avatar URL.

        Returns:
            The updated user or ``None`` if the user does not exist.
        """
        user = await self.get_user_by_email(email)
        if user is None:
            return None
        user.avatar = url
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_password(self, user: User, hashed_password: str) -> User:
        """Replace the password hash and revoke the refresh token.

        Args:
            user: User loaded in the current session.
            hashed_password: New password hash.

        Returns:
            The updated user.
        """
        user.hashed_password = hashed_password
        user.refresh_token_hash = None
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_refresh_token(self, user: User, token_hash: str | None) -> None:
        """Store the hash of the current refresh token, or ``None`` to revoke it.

        Args:
            user: User loaded in the current session.
            token_hash: SHA-256 hash of the refresh token.
        """
        user.refresh_token_hash = token_hash
        await self.db.commit()

    async def update_role(self, user_id: int, role: Role) -> User | None:
        """Change the user's role.

        Returns:
            The updated user or ``None`` if the user does not exist.
        """
        user = await self.get_user_by_id(user_id)
        if user is None:
            return None
        user.role = role
        await self.db.commit()
        await self.db.refresh(user)
        return user
