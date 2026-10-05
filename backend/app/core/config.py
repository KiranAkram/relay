import warnings
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    # Extraction (LLM). `fake` needs no key and is what CI runs with.
    LLM_PROVIDER: Literal["fake", "openai"] = "fake"
    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-5-nano"
    EXTRACTION_PROMPT_VERSION: str = "v1"
    HOSPITAL_TIMEZONE: str = "Asia/Karachi"

    # Speech-to-text. `fake` returns a canned transcript.
    STT_PROVIDER: Literal["fake", "openai"] = "fake"
    STT_MODEL: str = "gpt-transcribe"

    # Recordings. `local` keeps files under STORAGE_LOCAL_DIR (relative to the
    # backend working directory); S3/MinIO arrive with the AWS move.
    STORAGE_PROVIDER: Literal["local"] = "local"
    STORAGE_LOCAL_DIR: str = "data"
    # Where process_handover runs: after the HTTP response in the API process,
    # or inline in the request (tests).
    JOB_RUNNER: Literal["inprocess", "sync"] = "inprocess"
    # Confirm creates a `task_due_soon` flag this many minutes before a task is due.
    ALERT_LEAD_MINUTES: int = 15
    # INFO everywhere by default; set DEBUG by hand when needed (DEBUG may log
    # transcript text, which must not reach a shared log in production).
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("HOSPITAL_TIMEZONE")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        ZoneInfo(value)  # raises ZoneInfoNotFoundError for an unknown name
        return value

    @model_validator(mode="after")
    def _require_openai_key(self) -> Self:
        if (
            "openai" in (self.LLM_PROVIDER, self.STT_PROVIDER)
            and not self.OPENAI_API_KEY
        ):
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_PROVIDER or STT_PROVIDER is openai"
            )
        return self

    @property
    def hospital_tz(self) -> ZoneInfo:
        return ZoneInfo(self.HOSPITAL_TIMEZONE)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
