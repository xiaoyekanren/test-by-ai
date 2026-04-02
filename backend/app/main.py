# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="IoTDB Test Automation Platform",
    description="Backend API for IoTDB test automation",
    version="1.0.0"
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

# API routes will be registered here in later tasks
# from app.api import servers, workflows, executions, monitoring
# app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
# app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
# app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
# app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])