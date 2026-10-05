"""Insert rows into the append-only `audit_log`.

`record` only adds the row to the session; the caller commits it together
with the change it describes, so an action and its audit entry land in one
transaction. The current request id is stamped on the row so an audit entry
can be matched to the log lines of the request that produced it.
"""

import uuid
from typing import Any

from sqlmodel import Session

from app.core.logging import request_id_var
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
        request_id=request_id_var.get(),
    )
    session.add(entry)
    return entry
