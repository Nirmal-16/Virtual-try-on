"""Pydantic v2 request/response schemas."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    tryon_processing = "tryon_processing"
    tryon_done = "tryon_done"
    scene_processing = "scene_processing"
    done = "done"
    failed = "failed"


class SceneProvider(str, Enum):
    mock = "mock"
    flux = "flux"
    gpt_image = "gpt_image"
    sdxl = "sdxl"


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class TryOnRequest(BaseModel):
    job_id: str


class TryOnResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class SceneRequest(BaseModel):
    job_id: str
    provider: Optional[SceneProvider] = None


class SceneResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    tryon_url: Optional[str] = None
    scene_url: Optional[str] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
