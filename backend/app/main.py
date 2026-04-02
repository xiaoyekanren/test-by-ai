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

# API routes
from app.api.servers import router as servers_router
from app.api.workflows import router as workflows_router
from app.api.executions import router as executions_router
app.include_router(servers_router, prefix="/api/servers", tags=["servers"])
app.include_router(workflows_router, prefix="/api/workflows", tags=["workflows"])
app.include_router(executions_router, prefix="/api/executions", tags=["executions"])