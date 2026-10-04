"""Where `process_handover` runs.

`InProcessRunner` schedules it on FastAPI's BackgroundTasks, so it executes in
the API process after the HTTP response is sent (`JOB_RUNNER=inprocess`).
`SyncRunner` runs it inline, for tests. A Lambda runner replaces these on AWS;
the API only ever calls `submit`.
"""

import uuid
from collections.abc import Callable
from typing import Protocol

from fastapi import BackgroundTasks

from app.core.config import Settings
from app.pipeline import process_handover

Job = Callable[[uuid.UUID], None]


class JobRunner(Protocol):
    def submit(self, handover_id: uuid.UUID) -> None: ...


class SyncRunner:
    def __init__(self, job: Job = process_handover) -> None:
        self._job = job

    def submit(self, handover_id: uuid.UUID) -> None:
        self._job(handover_id)


class InProcessRunner:
    def __init__(
        self, background_tasks: BackgroundTasks, job: Job = process_handover
    ) -> None:
        self._background_tasks = background_tasks
        self._job = job

    def submit(self, handover_id: uuid.UUID) -> None:
        self._background_tasks.add_task(self._job, handover_id)


def get_job_runner(settings: Settings, background_tasks: BackgroundTasks) -> JobRunner:
    if settings.JOB_RUNNER == "sync":
        return SyncRunner()
    return InProcessRunner(background_tasks)
