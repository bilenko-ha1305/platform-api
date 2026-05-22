from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Checks the health of a project."""
    return {"status": "ok"}
