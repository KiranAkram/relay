"""Turn an extracted action item into the draft stored on `handover_patient`.

Shared by the dev CLI and the pipeline so both produce the same shape.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.extraction.schema import ActionItem
from app.extraction.timing import resolve_due


def resolve_action_item(
    item: ActionItem, recorded_at: datetime, tz: ZoneInfo
) -> dict[str, Any]:
    due = resolve_due(item.due, recorded_at, tz)
    return {
        "description": item.description,
        "priority": item.priority.value,
        "due_kind": item.due.kind.value,
        "due_phrase": item.due.phrase,
        "due_at": due.due_at.isoformat() if due.due_at else None,
        "needs_review": due.needs_review,
        "review_reason": due.reason,
        "verbatim": item.verbatim,
    }
