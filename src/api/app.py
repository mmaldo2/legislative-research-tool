"""FastAPI application — entry point for the legislative research API."""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.analysis import router as analysis_router
from src.api.api_keys import router as api_keys_router
from src.api.bills import router as bills_router
from src.api.chat import router as chat_router
from src.api.collections import router as collections_router
from src.api.compare import router as compare_router
from src.api.crs import router as crs_router
from src.api.deps import limiter, require_api_key, require_tier
from src.api.export import router as export_router
from src.api.hearings import router as hearings_router
from src.api.jurisdictions import router as jurisdictions_router
from src.api.organizations import router as organizations_router
from src.api.people import router as people_router
from src.api.regulatory import router as regulatory_router
from src.api.reports import router as reports_router
from src.api.saved_searches import router as saved_searches_router
from src.api.search import router as search_router
from src.api.status import router as status_router
from src.api.votes import router as votes_router
from src.api.webhooks import router as webhooks_router
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
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return JSON (not HTML) for rate limit errors so agents/clients can parse them."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# CORS — configurable via CORS_ORIGINS env var
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Mount routers — all require API key auth except status and org creation
auth_deps = [Depends(require_api_key)]
pro_deps = [Depends(require_tier("pro", "enterprise"))]

# Public routes
app.include_router(status_router, prefix="/api/v1", tags=["Status"])
app.include_router(organizations_router, prefix="/api/v1", tags=["Organizations"])

# Authenticated routes (all tiers)
app.include_router(bills_router, prefix="/api/v1", tags=["Bills"], dependencies=auth_deps)
app.include_router(people_router, prefix="/api/v1", tags=["People"], dependencies=auth_deps)
app.include_router(search_router, prefix="/api/v1", tags=["Search"], dependencies=auth_deps)
app.include_router(votes_router, prefix="/api/v1", tags=["Votes"], dependencies=auth_deps)
app.include_router(
    jurisdictions_router, prefix="/api/v1", tags=["Reference Data"], dependencies=auth_deps
)
app.include_router(
    collections_router, prefix="/api/v1", tags=["Collections"], dependencies=auth_deps
)
app.include_router(export_router, prefix="/api/v1", tags=["Export"], dependencies=auth_deps)
app.include_router(regulatory_router, prefix="/api/v1", tags=["Regulatory"], dependencies=auth_deps)
app.include_router(hearings_router, prefix="/api/v1", tags=["Hearings"], dependencies=auth_deps)
app.include_router(crs_router, prefix="/api/v1", tags=["CRS Reports"], dependencies=auth_deps)
app.include_router(api_keys_router, prefix="/api/v1", tags=["API Keys"], dependencies=auth_deps)
app.include_router(
    saved_searches_router, prefix="/api/v1", tags=["Saved Searches"], dependencies=auth_deps
)
app.include_router(webhooks_router, prefix="/api/v1", tags=["Webhooks"], dependencies=auth_deps)

# Pro+ tier routes (LLM-powered endpoints)
app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"], dependencies=pro_deps)
app.include_router(compare_router, prefix="/api/v1", tags=["Compare"], dependencies=pro_deps)
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"], dependencies=pro_deps)
app.include_router(reports_router, prefix="/api/v1", tags=["Reports"], dependencies=pro_deps)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
