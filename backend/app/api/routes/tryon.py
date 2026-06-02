"""POST /api/tryon — start virtual try-on background task."""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import get_job_store, get_tryon_service
from app.schemas.job import JobStatus, TryOnRequest, TryOnResponse
from app.services.tryon_service import TryOnService
from app.storage.job_store import JobStoreBase
from app.utils.errors import JobStateError
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/tryon", response_model=TryOnResponse, status_code=202)
async def start_tryon(
    body: TryOnRequest,
    background_tasks: BackgroundTasks,
    tryon_service: TryOnService = Depends(get_tryon_service),
    job_store: JobStoreBase = Depends(get_job_store),
) -> TryOnResponse:
    job = job_store.get(body.job_id)

    if job.status != "queued":
        raise JobStateError(
            f"Cannot start try-on: job is in state '{job.status}', expected 'queued'."
        )

    job.status = "tryon_processing"
    job.touch()
    job_store.save(job)

    background_tasks.add_task(tryon_service.run_tryon, body.job_id)
    logger.info("tryon_queued", job_id=body.job_id)

    return TryOnResponse(
        job_id=body.job_id,
        status=JobStatus.tryon_processing,
        message="Virtual try-on started. Poll /api/status/{job_id} for updates.",
    )
