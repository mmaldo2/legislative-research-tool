"""FastAPI application — entry point for the legislative research API."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.analysis import router as analysis_router
from src.api.bills import router as bills_router
from src.api.people import router as people_router
from src.api.search import router as search_router
from src.api.status import router as status_router

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

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(bills_router, prefix="/api/v1", tags=["Bills"])
app.include_router(people_router, prefix="/api/v1", tags=["People"])
app.include_router(search_router, prefix="/api/v1", tags=["Search"])
app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"])
app.include_router(status_router, prefix="/api/v1", tags=["Status"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
