"""POST /api/scene — start scene generation background task."""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import get_job_store, get_scene_service
from app.schemas.job import JobStatus, SceneRequest, SceneResponse
from app.services.scene_service import SceneService
from app.storage.job_store import JobStoreBase
from app.utils.errors import JobStateError
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/scene", response_model=SceneResponse, status_code=202)
async def start_scene_generation(
    body: SceneRequest,
    background_tasks: BackgroundTasks,
    scene_service: SceneService = Depends(get_scene_service),
    job_store: JobStoreBase = Depends(get_job_store),
) -> SceneResponse:
    job = job_store.get(body.job_id)

    if job.status != "tryon_done":
        raise JobStateError(
            f"Cannot start scene generation: job is in state '{job.status}', "
            "expected 'tryon_done'."
        )

    job.status = "scene_processing"
    job.touch()
    job_store.save(job)

    provider_name = body.provider.value if body.provider else None
    background_tasks.add_task(
        scene_service.run_scene_generation, body.job_id, provider_name
    )
    logger.info("scene_queued", job_id=body.job_id, provider=provider_name)

    return SceneResponse(
        job_id=body.job_id,
        status=JobStatus.scene_processing,
        message="Scene generation started. Poll /api/status/{job_id} for updates.",
    )
