"""Insert rows into the append-only `audit_log`.

`record` only adds the row to the session; the caller commits it together
with the change it describes, so an action and its audit entry land in one
transaction.
"""

import uuid
from typing import Any

from sqlmodel import Session

from app.models import AuditLog


def record(
    session: Session,
    action: str,
    entity_type: str,
    *,
    actor_id: uuid.UUID | None,
    handover_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        handover_id=handover_id,
        patient_id=patient_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    session.add(entry)
    return entry
