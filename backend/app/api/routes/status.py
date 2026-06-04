"""GET /api/status/{job_id} — poll job state and image URLs."""

from fastapi import APIRouter, Depends

from app.dependencies import get_job_store
from app.schemas.job import JobStatus, JobStatusResponse
from app.storage.job_store import JobStoreBase
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _image_url(job_id: str, filename: str) -> str:
    return f"/api/images/{job_id}/{filename}"


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(
    job_id: str,
    job_store: JobStoreBase = Depends(get_job_store),
) -> JobStatusResponse:
    from fastapi import HTTPException
    from app.utils.errors import JobNotFoundError
    try:
        job = job_store.get(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"job_id": job_id, "error": "Job not found — server may have restarted."},
        )

    tryon_url = (
        _image_url(job_id, "tryon_result.png") if job.tryon_result_path else None
    )
    scene_url = (
        _image_url(job_id, "scene_result.png") if job.scene_result_path else None
    )

    return JobStatusResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        tryon_url=tryon_url,
        scene_url=scene_url,
        error=job.error_message,
    )
