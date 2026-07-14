"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    from app.utils.helpers import logger
    logger.info(f"Starting Resume Analyzer API (LLM: {settings.LLM_PROVIDER})")
    yield
    logger.info("Shutting down Resume Analyzer API")


app = FastAPI(
    title="AI Resume Analyzer",
    description="AI-powered intelligent resume analysis system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1")

# Root redirect
@app.get("/")
async def root():
    return {"message": "AI Resume Analyzer API", "docs": "/docs"}
