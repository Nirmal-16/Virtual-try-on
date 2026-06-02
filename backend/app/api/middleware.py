"""CORS setup and global exception handlers."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.utils.errors import (
    JobNotFoundError,
    JobStateError,
    ProviderNotConfiguredError,
    StorageError,
    UnsupportedProviderError,
    ValidationError,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def setup_cors(app: FastAPI, origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, exc: JobNotFoundError):
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(JobStateError)
    async def job_state_handler(request: Request, exc: JobStateError):
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError):
        logger.error("storage_error", detail=exc.message)
        return JSONResponse(status_code=500, content={"detail": exc.message})

    @app.exception_handler(ProviderNotConfiguredError)
    async def provider_not_configured_handler(
        request: Request, exc: ProviderNotConfiguredError
    ):
        return JSONResponse(status_code=503, content={"detail": exc.message})

    @app.exception_handler(UnsupportedProviderError)
    async def unsupported_provider_handler(
        request: Request, exc: UnsupportedProviderError
    ):
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(Exception)
    async def catch_all_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", path=str(request.url))
        return JSONResponse(
            status_code=500, content={"detail": "An unexpected error occurred."}
        )
