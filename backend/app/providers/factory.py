"""Factory function for scene providers — lazy imports, reads env config."""

from typing import Optional

from app.providers.base import SceneProviderBase
from app.utils.errors import UnsupportedProviderError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_scene_provider(
    override: Optional[str] = None,
) -> SceneProviderBase:
    """Instantiate and return the appropriate SceneProvider.

    Args:
        override: Optional provider name that takes precedence over SCENE_PROVIDER env var.
    """
    from app.config import get_settings

    settings = get_settings()
    provider_name = (override or settings.scene_provider).lower()

    logger.info("creating_scene_provider", provider=provider_name)

    if provider_name == "mock":
        from app.providers.mock_provider import MockSceneProvider

        return MockSceneProvider()

    if provider_name == "flux":
        from app.providers.flux_provider import FluxSceneProvider

        return FluxSceneProvider(
            api_key=settings.flux_api_key,
            model_id=settings.flux_model_id,
        )

    if provider_name == "gpt_image":
        from app.providers.gpt_image_provider import GPTImageSceneProvider

        return GPTImageSceneProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_image_model,
            image_size=settings.openai_image_size,
        )

    if provider_name == "sdxl":
        from app.providers.sdxl_provider import SDXLSceneProvider

        return SDXLSceneProvider(
            model_id=settings.sdxl_model_id,
            device=settings.sdxl_device,
        )

    raise UnsupportedProviderError(
        f"Unknown scene provider '{provider_name}'. "
        "Valid options: mock, flux, gpt_image, sdxl."
    )
