"""Liveness health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Returns 200 when the service is alive and ready to accept requests.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}
