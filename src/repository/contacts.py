from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import and_, extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.schemas import ContactCreate, ContactUpdate


class ContactRepository:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_contacts(
        self,
        user: User,
        skip: int,
        limit: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> Sequence[Contact]:
        stmt = select(Contact).where(Contact.user_id == user.id)
        if first_name:
            stmt = stmt.where(Contact.first_name.ilike(f"%{first_name}%"))
        if last_name:
            stmt = stmt.where(Contact.last_name.ilike(f"%{last_name}%"))
        if email:
            stmt = stmt.where(Contact.email.ilike(f"%{email}%"))
        stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_contact_by_id(self, contact_id: int, user: User) -> Contact | None:
        stmt = select(Contact).where(
            Contact.id == contact_id, Contact.user_id == user.id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_contact_by_email(self, email: str, user: User) -> Contact | None:
        stmt = select(Contact).where(
            Contact.email == email, Contact.user_id == user.id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        contact = Contact(**body.model_dump(), user_id=user.id)
        self.db.add(contact)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def update_contact(
        self, contact_id: int, body: ContactUpdate, user: User
    ) -> Contact | None:
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(contact, key, value)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def remove_contact(self, contact_id: int, user: User) -> Contact | None:
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None
        await self.db.delete(contact)
        await self.db.commit()
        return contact

    async def get_upcoming_birthdays(
        self, days: int, user: User, today: date | None = None
    ) -> Sequence[Contact]:
        """Contacts whose birthday (month/day) falls within the next `days` days,
        today included: [today, today + days - 1].

        Compares month and day only, so the year wrap (late December -> early
        January) is handled naturally. Contacts born on Feb 29 are treated as
        having a birthday on Feb 28 in non-leap years.
        """
        today = today or date.today()
        dates = [today + timedelta(days=i) for i in range(days)]

        conditions = []
        for d in dates:
            conditions.append(
                and_(
                    extract("month", Contact.birthday) == d.month,
                    extract("day", Contact.birthday) == d.day,
                )
            )
            if d.month == 2 and d.day == 28 and not _is_leap(d.year):
                conditions.append(
                    and_(
                        extract("month", Contact.birthday) == 2,
                        extract("day", Contact.birthday) == 29,
                    )
                )

        stmt = select(Contact).where(Contact.user_id == user.id, or_(*conditions))
        result = await self.db.execute(stmt)
        contacts = result.scalars().all()

        # Sort by the upcoming birthday date, not by the birth year
        position = {(d.month, d.day): i for i, d in enumerate(dates)}
        return sorted(
            contacts,
            key=lambda c: position.get(
                (c.birthday.month, c.birthday.day), position.get((2, 28), 0)
            ),
        )


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
