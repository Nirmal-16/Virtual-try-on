"""FastAPI dependency injection — all singletons via @lru_cache."""

from functools import lru_cache

from app.config import get_settings
from app.services.image_service import ImageService
from app.services.scene_service import SceneService
from app.services.tryon_service import TryOnService
from app.storage.job_store import JobStoreBase, create_job_store
from app.storage.local_storage import LocalStorageService


@lru_cache(maxsize=1)
def get_local_storage() -> LocalStorageService:
    s = get_settings()
    return LocalStorageService(s.storage_root, s.uploads_dir, s.outputs_dir)


@lru_cache(maxsize=1)
def get_job_store() -> JobStoreBase:
    s = get_settings()
    return create_job_store(s.job_store_backend, s.redis_url)


@lru_cache(maxsize=1)
def get_image_service() -> ImageService:
    s = get_settings()
    return ImageService(
        storage=get_local_storage(),
        allowed_types=s.allowed_image_types_list,
        max_size_mb=s.max_image_size_mb,
    )


@lru_cache(maxsize=1)
def get_tryon_service() -> TryOnService:
    s = get_settings()
    return TryOnService(
        image_service=get_image_service(),
        job_store=get_job_store(),
        model_id=s.catvton_model_id,
        device=s.catvton_device,
        hf_token=s.hf_token,
        fal_api_key=s.flux_api_key,
        fal_model=s.catvton_fal_model,
        replicate_api_token=s.replicate_api_token,
    )


@lru_cache(maxsize=1)
def get_scene_service() -> SceneService:
    s = get_settings()
    return SceneService(
        image_service=get_image_service(),
        job_store=get_job_store(),
        prompt_template=s.scene_prompt_template,
    )
