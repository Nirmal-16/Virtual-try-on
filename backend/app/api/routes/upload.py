"""POST /api/upload — accept person + dress images and create a Job."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies import get_image_service, get_job_store
from app.models.job import Job
from app.schemas.job import JobStatus, UploadResponse
from app.services.image_service import ImageService
from app.storage.job_store import JobStoreBase
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_images(
    person_image: UploadFile = File(..., description="Customer's full-body photo"),
    dress_image: UploadFile = File(..., description="Wedding dress image"),
    image_service: ImageService = Depends(get_image_service),
    job_store: JobStoreBase = Depends(get_job_store),
) -> UploadResponse:
    job = Job()
    logger.info("upload_start", job_id=job.job_id)

    person_data = await person_image.read()
    dress_data = await dress_image.read()

    job.person_image_path = await image_service.validate_and_save_person(
        job.job_id, person_data
    )
    job.dress_image_path = await image_service.validate_and_save_dress(
        job.job_id, dress_data
    )

    job_store.create(job)
    logger.info("upload_done", job_id=job.job_id)

    return UploadResponse(
        job_id=job.job_id,
        status=JobStatus.queued,
        message="Files uploaded successfully. Call /api/tryon to start processing.",
    )
