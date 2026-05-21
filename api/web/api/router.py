from fastapi.routing import APIRouter

from api.web.api import dummy, echo, integrations, investigate, monitoring, redis, users

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(echo.router, prefix="/echo", tags=["echo"])
api_router.include_router(dummy.router, prefix="/dummy", tags=["dummy"])
api_router.include_router(redis.router, prefix="/redis", tags=["redis"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(
    integrations.router, prefix="/integrations", tags=["integrations"]
)
api_router.include_router(
    investigate.router, prefix="/investigate", tags=["investigate"]
)
