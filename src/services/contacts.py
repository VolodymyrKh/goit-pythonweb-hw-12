from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactUpdate


class ContactService:
    def __init__(self, db: AsyncSession):
        self.repository = ContactRepository(db)

    async def create_contact(self, body: ContactCreate, user: User):
        await self._ensure_email_is_free(body.email, user)
        try:
            return await self.repository.create_contact(body, user)
        except IntegrityError:
            await self.repository.db.rollback()
            raise _email_conflict()

    async def get_contacts(
        self,
        user: User,
        skip: int,
        limit: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ):
        return await self.repository.get_contacts(
            user, skip, limit, first_name, last_name, email
        )

    async def get_contact(self, contact_id: int, user: User):
        return await self.repository.get_contact_by_id(contact_id, user)

    async def update_contact(self, contact_id: int, body: ContactUpdate, user: User):
        if body.email is not None:
            await self._ensure_email_is_free(body.email, user, exclude_id=contact_id)
        try:
            return await self.repository.update_contact(contact_id, body, user)
        except IntegrityError:
            await self.repository.db.rollback()
            raise _email_conflict()

    async def remove_contact(self, contact_id: int, user: User):
        return await self.repository.remove_contact(contact_id, user)

    async def get_upcoming_birthdays(self, user: User, days: int = 7):
        return await self.repository.get_upcoming_birthdays(days, user)

    async def _ensure_email_is_free(
        self, email: str, user: User, exclude_id: int | None = None
    ):
        existing = await self.repository.get_contact_by_email(email, user)
        if existing is not None and existing.id != exclude_id:
            raise _email_conflict()


def _email_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Contact with this email already exists",
    )
