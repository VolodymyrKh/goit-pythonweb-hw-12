"""Pydantic schemas for request validation and response serialization."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.database.models import Role

PHONE_PATTERN = r"^\+?[\d\s\-()]{7,20}$"


class ContactBase(BaseModel):
    """Fields shared by contact requests and responses."""

    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=100)
    phone: str = Field(min_length=7, max_length=20, pattern=PHONE_PATTERN)
    birthday: date
    additional_data: str | None = Field(default=None, max_length=1000)


class ContactCreate(ContactBase):
    """Request body for creating a contact."""


class ContactUpdate(BaseModel):
    """Request body for updating a contact.

    All fields are optional: only the provided ones are updated.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)
    phone: str | None = Field(
        default=None, min_length=7, max_length=20, pattern=PHONE_PATTERN
    )
    birthday: date | None = None
    additional_data: str | None = Field(default=None, max_length=1000)


class ContactResponse(ContactBase):
    """Contact returned by the API."""

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Request body for registration."""

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    """Public user data returned by the API (never includes the password)."""

    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    confirmed: bool
    role: Role
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Access and refresh token pair returned after login or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request body for refreshing the token pair."""

    refresh_token: str


class RequestEmail(BaseModel):
    """Request body that only contains an email address."""

    email: EmailStr


class ResetPassword(BaseModel):
    """Request body for setting a new password with a reset token."""

    token: str
    new_password: str = Field(min_length=6, max_length=128)


class RoleUpdate(BaseModel):
    """Request body for changing a user's role."""

    role: Role


class MessageResponse(BaseModel):
    """Simple response with a human-readable message."""

    message: str
