"""Local filesystem storage service."""

import os
from pathlib import Path

import aiofiles

from app.utils.errors import StorageError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LocalStorageService:
    def __init__(self, storage_root: str, uploads_dir: str, outputs_dir: str) -> None:
        self._root = Path(storage_root).resolve()
        self._uploads = self._root / uploads_dir
        self._outputs = self._root / outputs_dir
        self._uploads.mkdir(parents=True, exist_ok=True)
        self._outputs.mkdir(parents=True, exist_ok=True)

    # ── Path helpers ──────────────────────────────────────────────────────────

    def upload_dir(self, job_id: str) -> Path:
        p = self._uploads / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def output_dir(self, job_id: str) -> Path:
        p = self._outputs / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def person_image_path(self, job_id: str) -> str:
        return str(self.upload_dir(job_id) / "person.png")

    def dress_image_path(self, job_id: str) -> str:
        return str(self.upload_dir(job_id) / "dress.png")

    def tryon_result_path(self, job_id: str) -> str:
        return str(self.output_dir(job_id) / "tryon_result.png")

    def scene_result_path(self, job_id: str) -> str:
        return str(self.output_dir(job_id) / "scene_result.png")

    def outputs_root(self) -> Path:
        return self._outputs

    # ── I/O ──────────────────────────────────────────────────────────────────

    async def save_upload(self, job_id: str, filename: str, data: bytes) -> str:
        """Save uploaded bytes and return the absolute path."""
        path = str(self.upload_dir(job_id) / filename)
        try:
            async with aiofiles.open(path, "wb") as f:
                await f.write(data)
            logger.debug("upload_saved", job_id=job_id, path=path)
            return path
        except OSError as exc:
            raise StorageError(f"Failed to save upload: {exc}") from exc

    async def save_output(self, job_id: str, filename: str, data: bytes) -> str:
        """Save generated output bytes and return the absolute path."""
        path = str(self.output_dir(job_id) / filename)
        try:
            async with aiofiles.open(path, "wb") as f:
                await f.write(data)
            logger.debug("output_saved", job_id=job_id, path=path)
            return path
        except OSError as exc:
            raise StorageError(f"Failed to save output: {exc}") from exc

    async def read_file(self, path: str) -> bytes:
        """Read a file at the given absolute path."""
        try:
            async with aiofiles.open(path, "rb") as f:
                return await f.read()
        except OSError as exc:
            raise StorageError(f"Failed to read file {path}: {exc}") from exc

    def delete_job_files(self, job_id: str) -> None:
        """Remove all files associated with a job (uploads + outputs)."""
        import shutil

        for d in [self._uploads / job_id, self._outputs / job_id]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        logger.info("job_files_deleted", job_id=job_id)
