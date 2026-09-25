from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=100)
    phone: str = Field(
        min_length=7, max_length=20, pattern=r"^\+?[\d\s\-()]{7,20}$"
    )
    birthday: date
    additional_data: str | None = Field(default=None, max_length=1000)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    """All fields optional: only the provided ones are updated."""

    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)
    phone: str | None = Field(
        default=None, min_length=7, max_length=20, pattern=r"^\+?[\d\s\-()]{7,20}$"
    )
    birthday: date | None = None
    additional_data: str | None = Field(default=None, max_length=1000)


class ContactResponse(ContactBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    confirmed: bool
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestEmail(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str
