from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.schemas import UserCreate


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username_or_email(
        self, username: str, email: str
    ) -> User | None:
        stmt = select(User).where(or_(User.username == username, User.email == email))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_user(
        self, body: UserCreate, hashed_password: str, avatar: str | None = None
    ) -> User:
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
        user = await self.get_user_by_email(email)
        if user is not None:
            user.confirmed = True
            await self.db.commit()

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        user = await self.get_user_by_email(email)
        if user is None:
            return None
        user.avatar = url
        await self.db.commit()
        await self.db.refresh(user)
        return user
