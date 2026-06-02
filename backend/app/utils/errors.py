"""Custom exception hierarchy for the application."""


class AppError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class StorageError(AppError):
    """File I/O or storage backend failure."""


class ValidationError(AppError):
    """Input validation failure (image type, size, etc.)."""


class JobNotFoundError(AppError):
    """Requested job_id does not exist in the store."""


class JobStateError(AppError):
    """Job is in an invalid state for the requested transition."""


class TryOnError(AppError):
    """CatVTON inference failure."""


class SceneGenerationError(AppError):
    """Scene generation failure (any provider)."""


class ProviderNotConfiguredError(AppError):
    """Required API key or model configuration is missing for the chosen provider."""


class UnsupportedProviderError(AppError):
    """The requested provider name is not registered in the factory."""
