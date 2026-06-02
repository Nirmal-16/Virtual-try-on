"""GPT Image (OpenAI gpt-image-1) scene provider."""

import base64
import io

from PIL import Image

from app.providers.base import SceneProviderBase
from app.utils.errors import ProviderNotConfiguredError, SceneGenerationError
from app.utils.image_utils import pil_to_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GPTImageSceneProvider(SceneProviderBase):
    def __init__(self, api_key: str, model: str, image_size: str) -> None:
        self._api_key = api_key
        self._model = model
        self._image_size = image_size
        self.validate_config()

    @property
    def name(self) -> str:
        return "gpt_image"

    def validate_config(self) -> None:
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "OPENAI_API_KEY is required for the gpt_image provider."
            )

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        import asyncio

        from openai import AsyncOpenAI

        logger.info("gpt_image_generate_start", model=self._model)

        client = AsyncOpenAI(api_key=self._api_key)

        img_bytes = pil_to_bytes(base_image, fmt="PNG")
        b64_input = base64.b64encode(img_bytes).decode()

        try:
            response = await client.images.edit(
                model=self._model,
                image=io.BytesIO(img_bytes),
                prompt=prompt,
                size=self._image_size,  # type: ignore[arg-type]
                response_format="b64_json",
                n=1,
            )
        except Exception as exc:
            raise SceneGenerationError(f"OpenAI image edit failed: {exc}") from exc

        try:
            b64_result = response.data[0].b64_json
            if b64_result is None:
                raise SceneGenerationError("OpenAI returned empty b64_json.")
            raw = base64.b64decode(b64_result)
        except (AttributeError, IndexError) as exc:
            raise SceneGenerationError(
                f"Unexpected OpenAI response shape: {exc}"
            ) from exc

        scene = Image.open(io.BytesIO(raw)).convert("RGB")
        logger.info("gpt_image_generate_done")
        return scene
