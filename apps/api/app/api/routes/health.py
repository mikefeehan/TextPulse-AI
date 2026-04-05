from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "app": settings.app_name,
    }
