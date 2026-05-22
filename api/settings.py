import enum
from pathlib import Path
from tempfile import gettempdir

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(enum.StrEnum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    # Bind to 0.0.0.0 so Railway (and Docker) can reach the process
    host: str = "0.0.0.0"  # noqa: S104
    # Railway injects PORT; also accept API_PORT for explicit override
    port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT", "PORT"))
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO

    # Database — individual fields (local/docker) or DATABASE_URL (Railway)
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "api"
    db_pass: str = "api"  # noqa: S105
    db_base: str = "api"
    db_echo: bool = False
    # Railway/Supabase connection string — takes precedence when set
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_DATABASE_URL", "DATABASE_URL"),
    )

    # Redis — individual fields (local/docker) or REDIS_URL (Railway)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_user: str | None = None
    redis_pass: str | None = None
    redis_base: int | None = None
    # Railway Redis connection string — takes precedence when set
    redis_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_REDIS_URL", "REDIS_URL"),
    )

    # Allowed CORS origins — space-separated list in env var
    cors_origins: list[str] = ["http://localhost:3000", "https://platform-web-eta-one.vercel.app"]

    # Auth0 configuration
    auth0_domain: str = ""
    auth0_audience: str = ""

    # AI model configuration (OpenAI-compatible)
    ai_model: str = "openai/gpt-5-nano"
    ai_api_key: str = ""  # GitHub token or provider API key
    ai_base_url: str = "https://models.github.ai/inference"

    # Fernet key for encrypting integration credentials
    encryption_key: str = ""

    # Stripe billing (Revelio's own subscriptions)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_solo: str = ""  # price_xxx from Stripe dashboard
    stripe_price_studio: str = ""  # price_xxx from Stripe dashboard
    app_base_url: str = "http://localhost:3000"  # for Stripe redirect URLs

    # Sentry's configuration.
    sentry_dsn: str | None = None
    sentry_sample_rate: float = 1.0

    @property
    def db_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        if self.database_url:
            # Railway/Supabase provide postgres:// or postgresql:// — asyncpg needs the +asyncpg scheme
            raw = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
            return URL(raw)
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    @property
    def redis_url(self) -> URL:
        """
        Assemble REDIS URL from settings.

        :return: redis URL.
        """
        if self.redis_url_override:
            return URL(self.redis_url_override)
        path = ""
        if self.redis_base is not None:
            path = f"/{self.redis_base}"
        return URL.build(
            scheme="redis",
            host=self.redis_host,
            port=self.redis_port,
            user=self.redis_user,
            password=self.redis_pass,
            path=path,
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_",
        env_file_encoding="utf-8",
    )


settings = Settings()
