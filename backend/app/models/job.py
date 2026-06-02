"""Job dataclass representing a single try-on pipeline run."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    person_image_path: Optional[str] = None
    dress_image_path: Optional[str] = None
    tryon_result_path: Optional[str] = None
    scene_result_path: Optional[str] = None

    error_message: Optional[str] = None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, reason: str) -> None:
        """Transition job to failed state with an error message."""
        self.status = "failed"
        self.error_message = reason
        self.touch()
