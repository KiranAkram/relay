"""Task acknowledgement: the I-PASS "synthesis by receiver" step."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app import audit
from app.api.deps import CurrentUser, SessionDep
from app.models import Flag, FlagStatus, Task, TaskPublic, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/{id}/acknowledge", response_model=TaskPublic)
def acknowledge_task(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Accept a task; its alert flags go inactive.
    """
    task = session.get(Task, id)
    if task is None or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.requested:
        raise HTTPException(
            status_code=409, detail=f"Task is {task.status}, expected requested"
        )
    now = datetime.now(UTC)
    task.status = TaskStatus.accepted
    task.acknowledged_by_id = current_user.id
    task.acknowledged_at = now
    session.add(task)

    flags = session.exec(
        select(Flag).where(
            Flag.task_id == task.id,
            Flag.status == FlagStatus.active,
            col(Flag.deleted_at).is_(None),
        )
    ).all()
    for flag in flags:
        flag.status = FlagStatus.inactive
        flag.acknowledged_by_id = current_user.id
        flag.acknowledged_at = now
        session.add(flag)

    audit.record(
        session,
        "task.acknowledged",
        "task",
        actor_id=current_user.id,
        handover_id=task.handover_id,
        patient_id=task.patient_id,
        entity_id=task.id,
        details={"flags": len(flags)},
    )
    session.commit()
    session.refresh(task)
    return task
