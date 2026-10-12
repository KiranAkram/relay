"""Spoken due time → absolute UTC instant.

Clock times are read in the hospital's timezone relative to when the handover
was recorded. A spoken day ("tomorrow", "this afternoon") pins the date;
otherwise the next occurrence is taken. Anything the code cannot resolve
confidently is returned with `needs_review=True` rather than guessed.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.extraction.schema import SpokenTime
from app.models import DueDay, DueKind

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

    # Without am/pm an hour of 1–12 has two readings; the earliest still ahead wins.
    hours = {hour}
    if not spoken.meridiem_stated and hour <= 12:
        hours = {hour % 12, hour % 12 + 12}

    local_now = recorded_at.astimezone(tz)
    if spoken.day is None:
        candidates = [_next_occurrence(local_now, h, minute) for h in hours]
    else:
        on_day = [_on_spoken_day(local_now, spoken.day, h, minute, tz) for h in hours]
        candidates = [c for c in on_day if c >= local_now]
        if not candidates:
            # "Today" at a time already gone: keep it, but a person decides.
            return ResolvedDue(
                due_at=max(on_day).astimezone(UTC),
                needs_review=True,
                reason="time already passed on the day stated",
            )

    due_at = min(candidates).astimezone(UTC)
    if due_at - recorded_at > REVIEW_HORIZON:
        horizon_hours = int(REVIEW_HORIZON.total_seconds() // 3600)
        return ResolvedDue(
            due_at=due_at,
            needs_review=True,
            reason=f"due more than {horizon_hours}h after recording",
        )
    return ResolvedDue(due_at=due_at)


def _next_occurrence(local_now: datetime, hour: int, minute: int) -> datetime:
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < local_now:
        candidate += timedelta(days=1)
    return candidate


def _on_spoken_day(
    local_now: datetime, day: DueDay, hour: int, minute: int, tz: ZoneInfo
) -> datetime:
    days = 1 if day == DueDay.tomorrow else 0
    # "Midnight tonight" is the coming midnight, which falls on the next date.
    if day == DueDay.today and hour == 0:
        days = 1
    date = local_now.date() + timedelta(days=days)
    return datetime.combine(date, time(hour, minute), tzinfo=tz)
