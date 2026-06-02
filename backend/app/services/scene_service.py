"""Scene generation service — delegates to a SceneProvider."""

from typing import Optional

from app.providers.factory import create_scene_provider
from app.services.image_service import ImageService
from app.storage.job_store import JobStoreBase
from app.utils.errors import SceneGenerationError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SceneService:
    def __init__(
        self,
        image_service: ImageService,
        job_store: JobStoreBase,
        prompt_template: str,
    ) -> None:
        self._image_service = image_service
        self._job_store = job_store
        self._prompt_template = prompt_template

    async def run_scene_generation(
        self, job_id: str, provider_override: Optional[str] = None
    ) -> None:
        """Generate an Indian wedding scene image and update job state."""
        job = self._job_store.get(job_id)
        try:
            logger.info(
                "scene_generate_start",
                job_id=job_id,
                provider=provider_override or "default",
            )

            tryon_image = await self._image_service.load_image(
                job.tryon_result_path  # type: ignore[arg-type]
            )

            provider = create_scene_provider(provider_override)
            scene_image = await provider.generate(self._prompt_template, tryon_image)

            saved_path = await self._image_service.save_output_image(
                job_id, "scene_result.png", scene_image
            )

            job.scene_result_path = saved_path
            job.status = "done"
            job.touch()
            self._job_store.save(job)
            logger.info("scene_generate_done", job_id=job_id)

        except Exception as exc:
            logger.exception("scene_generate_failed", job_id=job_id, error=str(exc))
            job.mark_failed(str(exc))
            self._job_store.save(job)
