"""SDXL img2img scene provider using local diffusers pipeline."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Optional

from PIL import Image

from app.providers.base import SceneProviderBase
from app.utils.errors import SceneGenerationError
from app.utils.image_utils import resize_for_model
from app.utils.logger import get_logger

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


class SDXLSceneProvider(SceneProviderBase):
    def __init__(self, model_id: str, device: str) -> None:
        self._model_id = model_id
        self._device = device
        self._pipeline: Optional[object] = None

    @property
    def name(self) -> str:
        return "sdxl"

    def _load_pipeline(self) -> object:
        if self._pipeline is None:
            try:
                from diffusers import AutoPipelineForImage2Image
                import torch

                logger.info("sdxl_loading_pipeline", model=self._model_id)
                self._pipeline = AutoPipelineForImage2Image.from_pretrained(
                    self._model_id,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    use_safetensors=True,
                    variant="fp16" if self._device == "cuda" else None,
                ).to(self._device)
                logger.info("sdxl_pipeline_loaded")
            except Exception as exc:
                raise SceneGenerationError(
                    f"Failed to load SDXL pipeline '{self._model_id}': {exc}"
                ) from exc
        return self._pipeline

    def _run_inference(self, prompt: str, image: Image.Image) -> Image.Image:
        pipe = self._load_pipeline()
        resized = resize_for_model(image, max_dim=1024)
        result = pipe(  # type: ignore[operator]
            prompt=prompt,
            image=resized,
            strength=0.75,
            guidance_scale=7.5,
            num_inference_steps=30,
        ).images[0]
        return result

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        logger.info("sdxl_generate_start", model=self._model_id)
        loop = asyncio.get_event_loop()
        try:
            scene = await loop.run_in_executor(
                _executor, self._run_inference, prompt, base_image
            )
        except Exception as exc:
            raise SceneGenerationError(f"SDXL inference failed: {exc}") from exc
        logger.info("sdxl_generate_done")
        return scene
