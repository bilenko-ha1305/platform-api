import os

import uvicorn

from api.settings import settings


def main() -> None:
    """Entrypoint of the application."""
    # Railway injects PORT; fall back to settings.port (which also reads PORT via AliasChoices)
    port = int(os.environ.get("PORT") or os.environ.get("API_PORT") or settings.port)
    uvicorn.run(
        "api.web.application:get_app",
        workers=settings.workers_count,
        host=settings.host,
        port=port,
        reload=settings.reload,
        log_level=settings.log_level.value.lower(),
        access_log=True,
        factory=True,
    )


if __name__ == "__main__":
    main()
