"""Image validation, normalisation, and persistence helpers."""

from PIL import Image

from app.storage.local_storage import LocalStorageService
from app.utils.errors import ValidationError
from app.utils.image_utils import (
    bytes_to_pil,
    pil_to_bytes,
    resize_for_model,
    validate_image_bytes,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ImageService:
    def __init__(
        self,
        storage: LocalStorageService,
        allowed_types: list[str],
        max_size_mb: float,
    ) -> None:
        self._storage = storage
        self._allowed_types = allowed_types
        self._max_size_mb = max_size_mb

    async def validate_and_save_person(self, job_id: str, data: bytes) -> str:
        """Validate, normalise, and save the person image. Returns saved path."""
        return await self._process_and_save(job_id, data, "person.png")

    async def validate_and_save_dress(self, job_id: str, data: bytes) -> str:
        """Validate, normalise, and save the dress image. Returns saved path."""
        return await self._process_and_save(job_id, data, "dress.png")

    async def _process_and_save(
        self, job_id: str, data: bytes, filename: str
    ) -> str:
        validate_image_bytes(data, self._allowed_types, self._max_size_mb)
        image = bytes_to_pil(data)
        png_bytes = pil_to_bytes(image, fmt="PNG")
        path = await self._storage.save_upload(job_id, filename, png_bytes)
        logger.debug("image_saved", job_id=job_id, filename=filename)
        return path

    async def load_image(self, path: str) -> Image.Image:
        """Load an image from disk and return as PIL Image."""
        data = await self._storage.read_file(path)
        return bytes_to_pil(data)

    async def save_output_image(
        self, job_id: str, filename: str, image: Image.Image
    ) -> str:
        """Save a PIL Image to the outputs directory. Returns saved path."""
        png_bytes = pil_to_bytes(image, fmt="PNG")
        path = await self._storage.save_output(job_id, filename, png_bytes)
        logger.debug("output_image_saved", job_id=job_id, filename=filename)
        return path
