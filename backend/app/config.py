"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Storage
    storage_root: str = "."
    uploads_dir: str = "uploads"
    outputs_dir: str = "outputs"
    max_image_size_mb: float = 10.0
    allowed_image_types: str = "image/jpeg,image/png,image/webp"

    # Virtual Try-On
    # Options: mock | fal | replicate | <HuggingFace model ID>
    catvton_model_id: str = "mock"
    catvton_device: str = "cpu"
    hf_token: str = ""
    replicate_api_token: str = ""
    # fal.ai try-on model — fashn/tryon gives best results
    catvton_fal_model: str = "fashn/tryon"

    # Scene Generation
    scene_provider: str = "mock"
    flux_api_key: str = ""
    flux_model_id: str = "black-forest-labs/FLUX.1-schnell"
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1024x1024"
    sdxl_model_id: str = "stabilityai/stable-diffusion-xl-base-1.0"
    sdxl_device: str = "cpu"

    # Job Store
    job_store_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"

    # Prompt
    scene_prompt_template: str = (
        "A realistic Indian wedding scene. The bride is wearing the outfit shown in the image. "
        "Elegant mandap stage with marigold and rose floral arrangements, draped fabric canopy in "
        "gold and red, diyas and string lights, cinematic soft lighting, luxury wedding ambiance, "
        "photorealistic, 4k, professional wedding photography style."
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_image_types_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
