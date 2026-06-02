"""Virtual try-on service wrapping CatVTON (or mock fallback)."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PIL import Image

from app.services.image_service import ImageService
from app.storage.job_store import JobStoreBase
from app.utils.errors import TryOnError
from app.utils.image_utils import resize_for_model
from app.utils.logger import get_logger

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


class TryOnService:
    def __init__(
        self,
        image_service: ImageService,
        job_store: JobStoreBase,
        model_id: str,
        device: str,
        hf_token: str,
    ) -> None:
        self._image_service = image_service
        self._job_store = job_store
        self._model_id = model_id
        self._device = device
        self._hf_token = hf_token
        self._pipeline: Optional[object] = None
        self._mock = model_id.lower() == "mock"

    # ── Pipeline loading ──────────────────────────────────────────────────────

    def _load_pipeline(self) -> object:
        if self._pipeline is not None:
            return self._pipeline

        logger.info("catvton_loading", model=self._model_id)
        try:
            import torch
            from diffusers import AutoencoderKL, UNet2DConditionModel
            from huggingface_hub import snapshot_download
            from diffusers import StableDiffusionInpaintPipeline

            # CatVTON uses a specialised pipeline; fall back to standard inpaint
            # if the specific class isn't importable.
            try:
                from diffusers import CatVTONPipeline  # type: ignore[attr-defined]

                pipe = CatVTONPipeline.from_pretrained(
                    self._model_id,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    token=self._hf_token or None,
                ).to(self._device)
            except (ImportError, AttributeError):
                # Fallback: standard inpaint pipeline for demonstration
                pipe = StableDiffusionInpaintPipeline.from_pretrained(
                    "runwayml/stable-diffusion-inpainting",
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    token=self._hf_token or None,
                ).to(self._device)

            self._pipeline = pipe
            logger.info("catvton_loaded")
        except Exception as exc:
            raise TryOnError(
                f"Failed to load CatVTON model '{self._model_id}': {exc}"
            ) from exc
        return self._pipeline

    # ── Inference ─────────────────────────────────────────────────────────────

    def _run_mock(self, person: Image.Image, dress: Image.Image) -> Image.Image:
        """Composite dress thumbnail over person image as a mock result."""
        result = person.copy().convert("RGB")
        thumb_w = person.width // 3
        thumb_h = int(dress.height * (thumb_w / dress.width))
        thumb = dress.resize((thumb_w, thumb_h), Image.LANCZOS)
        # Paste in the upper-centre area (approximate torso region)
        x = (person.width - thumb_w) // 2
        y = person.height // 6
        result.paste(thumb, (x, y))
        return result

    def _run_inference(self, person: Image.Image, dress: Image.Image) -> Image.Image:
        if self._mock:
            return self._run_mock(person, dress)

        pipe = self._load_pipeline()
        person_r = resize_for_model(person, 1024)
        dress_r = resize_for_model(dress, 1024)

        # Generic inpaint call — real CatVTON uses a cloth-agnostic mask.
        import torch

        mask = Image.new("L", person_r.size, 255)
        result = pipe(  # type: ignore[operator]
            prompt="person wearing the wedding dress, full body, photorealistic",
            image=person_r,
            mask_image=mask,
            num_inference_steps=20,
            guidance_scale=7.5,
        ).images[0]
        return result

    # ── Background task entry point ───────────────────────────────────────────

    async def run_tryon(self, job_id: str) -> None:
        """Run try-on inference as a background task and update job state."""
        job = self._job_store.get(job_id)
        try:
            logger.info("tryon_start", job_id=job_id)
            person = await self._image_service.load_image(job.person_image_path)  # type: ignore[arg-type]
            dress = await self._image_service.load_image(job.dress_image_path)  # type: ignore[arg-type]

            loop = asyncio.get_event_loop()
            result_image: Image.Image = await loop.run_in_executor(
                _executor, self._run_inference, person, dress
            )

            saved_path = await self._image_service.save_output_image(
                job_id, "tryon_result.png", result_image
            )

            job.tryon_result_path = saved_path
            job.status = "tryon_done"
            job.touch()
            self._job_store.save(job)
            logger.info("tryon_done", job_id=job_id)

        except Exception as exc:
            logger.exception("tryon_failed", job_id=job_id, error=str(exc))
            job.mark_failed(str(exc))
            self._job_store.save(job)
