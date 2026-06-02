"""Job store implementations: in-memory and Redis."""

import json
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.models.job import Job
from app.utils.errors import JobNotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class JobStoreBase(ABC):
    @abstractmethod
    def create(self, job: Job) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> Job: ...

    @abstractmethod
    def save(self, job: Job) -> None: ...

    @abstractmethod
    def delete(self, job_id: str) -> None: ...


class InMemoryJobStore(JobStoreBase):
    def __init__(self) -> None:
        self._store: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job: Job) -> None:
        with self._lock:
            self._store[job.job_id] = job
        logger.debug("job_created", job_id=job.job_id)

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._store.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' not found.")
        return job

    def save(self, job: Job) -> None:
        with self._lock:
            if job.job_id not in self._store:
                raise JobNotFoundError(f"Job '{job.job_id}' not found.")
            self._store[job.job_id] = job
        logger.debug("job_saved", job_id=job.job_id, status=job.status)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._store.pop(job_id, None)


class RedisJobStore(JobStoreBase):
    _TTL = 86400  # 24 hours

    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def _serialise(self, job: Job) -> str:
        return json.dumps(
            {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "person_image_path": job.person_image_path,
                "dress_image_path": job.dress_image_path,
                "tryon_result_path": job.tryon_result_path,
                "scene_result_path": job.scene_result_path,
                "error_message": job.error_message,
            }
        )

    def _deserialise(self, raw: str) -> Job:
        data = json.loads(raw)
        job = Job(
            job_id=data["job_id"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            person_image_path=data.get("person_image_path"),
            dress_image_path=data.get("dress_image_path"),
            tryon_result_path=data.get("tryon_result_path"),
            scene_result_path=data.get("scene_result_path"),
            error_message=data.get("error_message"),
        )
        return job

    def create(self, job: Job) -> None:
        self._client.set(self._key(job.job_id), self._serialise(job), ex=self._TTL)
        logger.debug("job_created_redis", job_id=job.job_id)

    def get(self, job_id: str) -> Job:
        raw = self._client.get(self._key(job_id))
        if raw is None:
            raise JobNotFoundError(f"Job '{job_id}' not found.")
        return self._deserialise(raw)

    def save(self, job: Job) -> None:
        if not self._client.exists(self._key(job.job_id)):
            raise JobNotFoundError(f"Job '{job.job_id}' not found.")
        self._client.set(self._key(job.job_id), self._serialise(job), ex=self._TTL)

    def delete(self, job_id: str) -> None:
        self._client.delete(self._key(job_id))


def create_job_store(backend: str, redis_url: str = "") -> JobStoreBase:
    if backend == "redis":
        return RedisJobStore(redis_url)
    return InMemoryJobStore()
