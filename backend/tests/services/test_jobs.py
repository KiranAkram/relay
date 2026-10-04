import uuid

from fastapi import BackgroundTasks

from app.core.config import settings
from app.services.jobs import InProcessRunner, SyncRunner, get_job_runner


def test_sync_runner_runs_job_immediately() -> None:
    ran: list[uuid.UUID] = []
    handover_id = uuid.uuid4()
    SyncRunner(job=ran.append).submit(handover_id)
    assert ran == [handover_id]


def test_inprocess_runner_defers_job_to_background_tasks() -> None:
    ran: list[uuid.UUID] = []
    background = BackgroundTasks()
    handover_id = uuid.uuid4()

    InProcessRunner(background, job=ran.append).submit(handover_id)

    assert ran == []  # nothing runs until the response has been sent
    (task,) = background.tasks
    assert task.args == (handover_id,)


def test_get_job_runner_picks_configured_runner() -> None:
    background = BackgroundTasks()
    sync = settings.model_copy(update={"JOB_RUNNER": "sync"})
    assert isinstance(get_job_runner(sync, background), SyncRunner)
    inprocess = settings.model_copy(update={"JOB_RUNNER": "inprocess"})
    assert isinstance(get_job_runner(inprocess, background), InProcessRunner)
