"""Flux scene provider via fal.ai async API."""

import asyncio
import base64
import io
from typing import Optional

import httpx
from PIL import Image

from app.providers.base import SceneProviderBase
from app.utils.errors import ProviderNotConfiguredError, SceneGenerationError
from app.utils.image_utils import pil_to_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

FAL_API_URL = "https://fal.run/{model_id}"
FAL_QUEUE_URL = "https://queue.fal.run/{model_id}"


class FluxSceneProvider(SceneProviderBase):
    def __init__(self, api_key: str, model_id: str) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self.validate_config()

    @property
    def name(self) -> str:
        return "flux"

    def validate_config(self) -> None:
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "FLUX_API_KEY is required for the flux provider."
            )

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        logger.info("flux_generate_start", model=self._model_id)

        img_bytes = pil_to_bytes(base_image, fmt="PNG")
        b64_image = base64.b64encode(img_bytes).decode()

        payload = {
            "prompt": prompt,
            "image_url": f"data:image/png;base64,{b64_image}",
            "num_inference_steps": 4,
            "guidance_scale": 3.5,
        }

        headers = {
            "Authorization": f"Key {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                FAL_API_URL.format(model_id=self._model_id),
                json=payload,
                headers=headers,
            )
            if resp.status_code != 200:
                raise SceneGenerationError(
                    f"Flux API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()

        try:
            image_url: str = data["images"][0]["url"]
        except (KeyError, IndexError) as exc:
            raise SceneGenerationError(f"Unexpected Flux response shape: {data}") from exc

        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()

        scene = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        logger.info("flux_generate_done")
        return scene
