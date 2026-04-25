"""
FormFlow - Health Check Router

Provides health check endpoints for monitoring and orchestration.
"""

from fastapi import APIRouter
import httpx
from fastapi.responses import JSONResponse

from app.config import settings


router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of the application and its dependencies.
    """
    # Check inference provider connectivity
    inference_healthy = False
    inference_error = None
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if settings.inference_provider == "ollama":
                response = await client.get(f"{settings.inference_base_url}/api/tags")
            else:  # vllm
                response = await client.get(f"{settings.inference_base_url}/health")
            inference_healthy = response.status_code == 200
    except Exception as e:
        inference_error = str(e)
    
    return {
        "status": "healthy" if inference_healthy else "degraded",
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
        },
        "inference": {
            "provider": settings.inference_provider,
            "model": settings.inference_model,
            "healthy": inference_healthy,
            "error": inference_error,
        },
    }


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - is the app running?"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if settings.inference_provider == "ollama":
                response = await client.get(f"{settings.inference_base_url}/api/tags")
            else:
                response = await client.get(f"{settings.inference_base_url}/health")

            if response.status_code == 200:
                return {"status": "ready"}
    except Exception:
        pass

    return JSONResponse(status_code=503, content={"status": "not_ready"})