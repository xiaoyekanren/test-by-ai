# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.setup import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: Add cleanup logic here if needed


app = FastAPI(
    title="IoTDB Test Automation Platform",
    description="Backend API for IoTDB test automation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# API routes
from app.api.servers import router as servers_router
from app.api.workflows import router as workflows_router
from app.api.executions import router as executions_router
from app.api.monitoring import router as monitoring_router
app.include_router(servers_router, prefix="/api/servers", tags=["servers"])
app.include_router(workflows_router, prefix="/api/workflows", tags=["workflows"])
app.include_router(executions_router, prefix="/api/executions", tags=["executions"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])