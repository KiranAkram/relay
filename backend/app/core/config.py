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
    LLM_MODEL: str = "gpt-5-mini"
    EXTRACTION_PROMPT_VERSION: str = "v2"
    HOSPITAL_TIMEZONE: str = "Asia/Karachi"

    # Speech-to-text. `fake` returns a canned transcript.
    STT_PROVIDER: Literal["fake", "openai"] = "fake"
    STT_MODEL: str = "gpt-transcribe"

    # Intent gate between transcription and extraction: is this transcript a
    # spoken clinical shift handover at all? `jev` is TypeSafe AI's decision
    # model (typed yes/no with a probability, no prose). `fake` says yes.
    # Below INTENT_THRESHOLD the handover is `rejected`: no cards, no retry.
    INTENT_PROVIDER: Literal["fake", "jev"] = "fake"
    INTENT_MODEL: str = "jev-latest"
    INTENT_THRESHOLD: float = 0.8
    TYPESAFE_API_KEY: str | None = None

    # Recordings. `local` keeps files under STORAGE_LOCAL_DIR (relative to the
    # backend working directory); S3/MinIO arrive with the AWS move.
    STORAGE_PROVIDER: Literal["local"] = "local"
    STORAGE_LOCAL_DIR: str = "data"
    # Where process_handover runs: after the HTTP response in the API process,
    # or inline in the request (tests).
    JOB_RUNNER: Literal["inprocess", "sync"] = "inprocess"
    # Confirm creates a `task_due_soon` flag this many minutes before a task is due.
    ALERT_LEAD_MINUTES: int = 15
    # Demo abuse limits (owner's values, 8 Oct 2026). A recording is cut at
    # RECORDING_MAX_SECONDS in the browser and refused above it on the server;
    # each visitor (signed cookie, and separately the IP address) may send
    # VISITOR_RECORDINGS_PER_DAY recordings; TRANSCRIPTION_MINUTES_PER_DAY caps
    # the audio the whole deployment sends to transcription per day. Days roll
    # over at midnight in HOSPITAL_TIMEZONE.
    RECORDING_MAX_SECONDS: int = 120
    VISITOR_RECORDINGS_PER_DAY: int = 3
    TRANSCRIPTION_MINUTES_PER_DAY: int = 30
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
        if self.INTENT_PROVIDER == "jev" and not self.TYPESAFE_API_KEY:
            raise ValueError("TYPESAFE_API_KEY is required when INTENT_PROVIDER is jev")
        if not 0 < self.INTENT_THRESHOLD <= 1:
            raise ValueError("INTENT_THRESHOLD must be between 0 and 1")
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

    # Accounts are handed out by an admin; self-registration is off unless
    # explicitly enabled (never for a hospital deployment).
    USERS_OPEN_REGISTRATION: bool = False
    # Optional demo doctor account, created at start-up when both are set.
    # DEMO_ACCESS_BANNER=true shows its login on the sign-in page: demo
    # instances only, never where real patient data could appear.
    DEMO_DOCTOR_EMAIL: EmailStr | None = None
    DEMO_DOCTOR_PASSWORD: str | None = None
    DEMO_ACCESS_BANNER: bool = False

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
        self._check_default_secret("DEMO_DOCTOR_PASSWORD", self.DEMO_DOCTOR_PASSWORD)

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
