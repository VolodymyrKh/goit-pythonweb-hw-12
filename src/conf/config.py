"""Application settings loaded from environment variables and the ``.env`` file."""

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration of the application.

    Values are read from environment variables first and then from ``.env``.
    Secrets (database password, JWT secret, SMTP and Cloudinary credentials)
    have no defaults, so the application refuses to start without them.
    """

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_SECONDS: int = 60 * 15
    JWT_REFRESH_EXPIRATION_SECONDS: int = 60 * 60 * 24 * 7
    EMAIL_TOKEN_EXPIRATION_SECONDS: int = 60 * 60 * 24
    RESET_TOKEN_EXPIRATION_SECONDS: int = 60 * 60

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    USER_CACHE_TTL_SECONDS: int = 60 * 15

    # Mail
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: EmailStr
    MAIL_FROM_NAME: str = "Contacts API"
    MAIL_SERVER: str
    MAIL_PORT: int = 465
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = True
    MAIL_USE_CREDENTIALS: bool = True
    MAIL_VALIDATE_CERTS: bool = True

    # Cloudinary
    CLOUDINARY_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # CORS: comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def DB_URL(self) -> str:
        """SQLAlchemy async connection URL for PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Allowed CORS origins parsed from the comma-separated ``CORS_ORIGINS``."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
