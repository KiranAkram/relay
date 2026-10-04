"""Flag acknowledgement for patient-level alerts (`unstable_patient`), which
have no task to acknowledge through."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from app import audit
from app.api.deps import CurrentUser, SessionDep
from app.models import Flag, FlagPublic, FlagStatus

router = APIRouter(prefix="/flags", tags=["flags"])


@router.post("/{id}/acknowledge", response_model=FlagPublic)
def acknowledge_flag(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Mark an active flag inactive.
    """
    flag = session.get(Flag, id)
    if flag is None or flag.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Flag not found")
    if flag.status != FlagStatus.active:
        raise HTTPException(status_code=409, detail="Flag is already inactive")
    now = datetime.now(UTC)
    flag.status = FlagStatus.inactive
    flag.acknowledged_by_id = current_user.id
    flag.acknowledged_at = now
    session.add(flag)
    audit.record(
        session,
        "flag.acknowledged",
        "flag",
        actor_id=current_user.id,
        handover_id=flag.handover_id,
        patient_id=flag.patient_id,
        entity_id=flag.id,
        details={"category": flag.category},
    )
    session.commit()
    session.refresh(flag)
    return flag
