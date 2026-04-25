"""
FormFlow - FastAPI Application

Main entry point for the FormFlow API.
Provides endpoints for form processing, extraction, and verification.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from copy import deepcopy

from app.config import settings
from app.routers import health, forms, extraction


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📡 Inference provider: {settings.inference_provider}")
    print(f"🔗 Inference URL: {settings.inference_base_url}")
    print(f"🤖 Model: {settings.inference_model}")
    yield
    # Shutdown
    print(f"👋 Shutting down {settings.app_name}")


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Generalized AI Form-Filling Platform - Transform any PDF form workflow",
    version=settings.app_version,
    lifespan=lifespan,
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    paths = schema.get("paths", {})
    process_post = paths.get("/api/extract/process", {}).get("post", {})
    content = (
        process_post.get("requestBody", {})
        .get("content", {})
        .get("multipart/form-data", {})
    )
    req_schema = content.get("schema", {})

    if "$ref" in req_schema:
        ref_name = req_schema["$ref"].split("/")[-1]
        body_schema = schema.get("components", {}).get("schemas", {}).get(ref_name, {})
        receipts_schema = body_schema.get("properties", {}).get("receipts", {})
        items = receipts_schema.get("items", {})

        if items.get("type") == "string" and "contentMediaType" in items:
            items["format"] = "binary"
            items.pop("contentMediaType", None)

    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(forms.router, prefix=settings.api_prefix, tags=["Forms"])
app.include_router(extraction.router, prefix=settings.api_prefix, tags=["Extraction"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
