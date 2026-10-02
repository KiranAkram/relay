"""Spoken due time → absolute UTC instant.

Clock times are read in the hospital's timezone relative to when the handover
was recorded. Anything the code cannot resolve confidently is returned with
`needs_review=True` rather than guessed.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.extraction.schema import SpokenTime
from app.models import DueKind

# A due time further out than this within a shift handover is probably a
# mis-heard clock time (e.g. 8:30 read as 20:30).
REVIEW_HORIZON = timedelta(hours=18)


class ResolvedDue(BaseModel):
    due_at: datetime | None = None  # UTC
    needs_review: bool = False
    reason: str | None = None


def resolve_due(spoken: SpokenTime, recorded_at: datetime, tz: ZoneInfo) -> ResolvedDue:
    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at must be timezone-aware")
    if spoken.kind == DueKind.unspecified:
        return ResolvedDue()
    if spoken.kind == DueKind.relative:
        return _resolve_relative(spoken, recorded_at)
    return _resolve_clock(spoken, recorded_at, tz)


def _resolve_relative(spoken: SpokenTime, recorded_at: datetime) -> ResolvedDue:
    minutes = spoken.relative_minutes
    if minutes is None or minutes < 0:
        return ResolvedDue(
            needs_review=True, reason="relative time has no usable minutes"
        )
    return ResolvedDue(
        due_at=(recorded_at + timedelta(minutes=minutes)).astimezone(UTC)
    )


def _resolve_clock(
    spoken: SpokenTime, recorded_at: datetime, tz: ZoneInfo
) -> ResolvedDue:
    if spoken.clock_time is None:
        return ResolvedDue(needs_review=True, reason="clock time not understood")
    hour, minute = (int(part) for part in spoken.clock_time.split(":"))

    # Without am/pm an hour of 1–12 has two readings; take whichever comes next.
    hours = {hour}
    if not spoken.meridiem_stated and hour <= 12:
        hours = {hour % 12, hour % 12 + 12}

    local_now = recorded_at.astimezone(tz)
    candidates: list[datetime] = []
    for h in hours:
        candidate = local_now.replace(hour=h, minute=minute, second=0, microsecond=0)
        if candidate < local_now:
            candidate += timedelta(days=1)
        candidates.append(candidate)

    due_at = min(candidates).astimezone(UTC)
    if due_at - recorded_at > REVIEW_HORIZON:
        horizon_hours = int(REVIEW_HORIZON.total_seconds() // 3600)
        return ResolvedDue(
            due_at=due_at,
            needs_review=True,
            reason=f"due more than {horizon_hours}h after recording",
        )
    return ResolvedDue(due_at=due_at)
