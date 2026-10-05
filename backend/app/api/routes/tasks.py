"""Task lifecycle for the incoming doctor.

requested → accepted (acknowledge: the I-PASS "synthesis by receiver" step)
→ completed | cancelled. Closing a task in any way makes its alert flags
inactive. A cancelled task keeps the reason, because a clinical task that
quietly disappears is worse than one that stays open.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app import audit
from app.api.deps import CurrentUser, SessionDep
from app.models import Flag, FlagStatus, Task, TaskCancel, TaskPublic, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])

OPEN = (TaskStatus.requested, TaskStatus.accepted)


@router.post("/{id}/acknowledge", response_model=TaskPublic)
def acknowledge_task(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Accept a task; its alert flags go inactive.
    """
    task = _get_task(session, id)
    _require_status(task, (TaskStatus.requested,))
    now = datetime.now(UTC)
    task.status = TaskStatus.accepted
    task.acknowledged_by_id = current_user.id
    task.acknowledged_at = now
    session.add(task)
    flags = _deactivate_flags(session, task, current_user.id, now)
    audit.record(
        session,
        "task.acknowledged",
        "task",
        actor_id=current_user.id,
        handover_id=task.handover_id,
        patient_id=task.patient_id,
        entity_id=task.id,
        details={"flags": flags},
    )
    session.commit()
    session.refresh(task)
    return task


@router.post("/{id}/complete", response_model=TaskPublic)
def complete_task(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Mark a task done. Allowed from requested or accepted.
    """
    task = _get_task(session, id)
    _require_status(task, OPEN)
    now = datetime.now(UTC)
    task.status = TaskStatus.completed
    task.completed_by_id = current_user.id
    task.completed_at = now
    session.add(task)
    flags = _deactivate_flags(session, task, current_user.id, now)
    audit.record(
        session,
        "task.completed",
        "task",
        actor_id=current_user.id,
        handover_id=task.handover_id,
        patient_id=task.patient_id,
        entity_id=task.id,
        details={"flags": flags, "was": task.status},
    )
    session.commit()
    session.refresh(task)
    return task


@router.post("/{id}/cancel", response_model=TaskPublic)
def cancel_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    body: TaskCancel,
) -> Any:
    """
    Drop a task with a reason. Allowed from requested or accepted.
    """
    task = _get_task(session, id)
    _require_status(task, OPEN)
    now = datetime.now(UTC)
    previous = task.status
    task.status = TaskStatus.cancelled
    task.completed_by_id = current_user.id
    task.completed_at = now
    task.cancel_reason = body.reason.strip()
    session.add(task)
    flags = _deactivate_flags(session, task, current_user.id, now)
    audit.record(
        session,
        "task.cancelled",
        "task",
        actor_id=current_user.id,
        handover_id=task.handover_id,
        patient_id=task.patient_id,
        entity_id=task.id,
        details={"flags": flags, "was": previous, "reason": task.cancel_reason},
    )
    session.commit()
    session.refresh(task)
    return task


# --- helpers ---------------------------------------------------------------


def _get_task(session: SessionDep, id: uuid.UUID) -> Task:
    task = session.get(Task, id)
    if task is None or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _require_status(task: Task, allowed: tuple[TaskStatus, ...]) -> None:
    if task.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Task is {task.status}, expected {' or '.join(allowed)}",
        )


def _deactivate_flags(
    session: SessionDep, task: Task, user_id: uuid.UUID, now: datetime
) -> int:
    flags = session.exec(
        select(Flag).where(
            Flag.task_id == task.id,
            Flag.status == FlagStatus.active,
            col(Flag.deleted_at).is_(None),
        )
    ).all()
    for flag in flags:
        flag.status = FlagStatus.inactive
        flag.acknowledged_by_id = user_id
        flag.acknowledged_at = now
        session.add(flag)
    return len(flags)
