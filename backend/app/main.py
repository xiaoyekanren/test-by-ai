# backend/app/main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.models.setup import init_db


APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_CANDIDATES = (
    APP_DIR / "frontend_dist",
)


def resolve_frontend_dist_dir() -> Path | None:
    """返回第一个可用的前端构建目录。"""
    for candidate in FRONTEND_DIST_CANDIDATES:
        if (candidate / "index.html").exists():
            return candidate
    return None


FRONTEND_DIST_DIR = resolve_frontend_dist_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期处理器，用于启动和关闭事件。"""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: Add cleanup logic here if needed


app = FastAPI(
    title="TestFlow",
    description="IoTDB 测试自动化后端 API",
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
    """健康检查接口"""
    return {"status": "ok"}

# API routes
from app.api.servers import router as servers_router
from app.api.workflows import router as workflows_router
from app.api.executions import router as executions_router
from app.api.monitoring import router as monitoring_router
from app.api.settings import router as settings_router
from app.api.iotdb import router as iotdb_router
from app.api.test_suites import router as test_suites_router
app.include_router(servers_router, prefix="/api/servers", tags=["servers"])
app.include_router(workflows_router, prefix="/api/workflows", tags=["workflows"])
app.include_router(executions_router, prefix="/api/executions", tags=["executions"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(iotdb_router, prefix="/api/iotdb", tags=["iotdb"])
app.include_router(test_suites_router, prefix="/api/test-suites", tags=["test-suites"])


def serve_frontend_path(full_path: str = ""):
    """提供前端构建文件，或回退到 SPA 入口页面。"""
    if FRONTEND_DIST_DIR is None:
        raise HTTPException(status_code=404, detail="前端构建产物未找到")

    dist_root = FRONTEND_DIST_DIR.resolve()
    requested_path = Path(full_path)
    candidate = (dist_root / requested_path).resolve()

    try:
        candidate.relative_to(dist_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="前端路径无效") from exc

    if full_path:
        if candidate.is_file():
            return FileResponse(candidate)
        if requested_path.suffix:
            raise HTTPException(status_code=404, detail="前端资源文件不存在")

    index_file = dist_root / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="前端入口文件不存在")
    return FileResponse(index_file)


@app.get("/", include_in_schema=False)
async def serve_frontend_root():
    """当前端构建产物可用时，提供前端应用根页面。"""
    return serve_frontend_path("")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_catch_all(full_path: str):
    """在 API 路由匹配之后，提供前端构建的路由页面。"""
    return serve_frontend_path(full_path)
