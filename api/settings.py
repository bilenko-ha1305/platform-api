import enum
from pathlib import Path
from tempfile import gettempdir

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

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO
    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "api"
    db_pass: str = "api"  # noqa: S105
    db_base: str = "api"
    db_echo: bool = False

    # Variables for Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_user: str | None = None
    redis_pass: str | None = None
    redis_base: int | None = None

    # Auth0 configuration
    auth0_domain: str = ""
    auth0_audience: str = ""

    # AI model configuration (LiteLLM format, e.g. "anthropic/claude-sonnet-4-6")
    ai_model: str = "anthropic/claude-sonnet-4-6"
    ai_api_key: str = ""

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
