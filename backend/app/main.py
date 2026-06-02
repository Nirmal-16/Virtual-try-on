"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.middleware import setup_cors, setup_exception_handlers
from app.api.routes import scene, status, tryon, upload
from app.config import get_settings
from app.dependencies import get_local_storage
from app.utils.logger import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level, settings.app_env)
    log = get_logger(__name__)
    log.info("startup", env=settings.app_env, port=settings.app_port)

    # Ensure output directories exist and wire up static file serving
    storage = get_local_storage()
    outputs_path = storage.outputs_root()
    outputs_path.mkdir(parents=True, exist_ok=True)

    yield

    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Wedding Virtual Try-On API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    setup_cors(app, settings.cors_origins_list)
    setup_exception_handlers(app)

    # API routes
    prefix = "/api"
    app.include_router(upload.router, prefix=prefix, tags=["upload"])
    app.include_router(tryon.router, prefix=prefix, tags=["tryon"])
    app.include_router(scene.router, prefix=prefix, tags=["scene"])
    app.include_router(status.router, prefix=prefix, tags=["status"])

    # Static file serving for generated images
    # Mount after output dir is guaranteed to exist
    storage = get_local_storage()
    app.mount(
        "/api/images",
        StaticFiles(directory=str(storage.outputs_root())),
        name="images",
    )

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
