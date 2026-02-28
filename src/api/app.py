"""FastAPI application — entry point for the legislative research API."""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.analysis import router as analysis_router
from src.api.bills import router as bills_router
from src.api.deps import limiter, require_api_key
from src.api.people import router as people_router
from src.api.search import router as search_router
from src.api.status import router as status_router
from src.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Legislative Research API",
    description=(
        "AI-native legislative research and analysis platform. "
        "Search, analyze, and compare bills across all 50 states and Congress."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — configurable via CORS_ORIGINS env var
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount routers — all require API key auth except status (health check is public)
auth_deps = [Depends(require_api_key)]
app.include_router(bills_router, prefix="/api/v1", tags=["Bills"], dependencies=auth_deps)
app.include_router(people_router, prefix="/api/v1", tags=["People"], dependencies=auth_deps)
app.include_router(search_router, prefix="/api/v1", tags=["Search"], dependencies=auth_deps)
app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"], dependencies=auth_deps)
app.include_router(status_router, prefix="/api/v1", tags=["Status"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
