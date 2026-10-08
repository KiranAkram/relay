"""Demo limits: recordings per visitor and per address, audio minutes per day.

`reserve` locks the counter rows, checks every limit and increments them in
the caller's transaction, so a refused upload consumes nothing and two
concurrent uploads cannot both squeeze under the cap. `snapshot` is what the
Record page shows before the doctor presses Record.
"""

from datetime import UTC, datetime, time, timedelta

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import Settings
from app.models import QuotaPublic, UsageCounter

GLOBAL_KEY = "*"


def _today(settings: Settings) -> datetime:
    return datetime.now(settings.hospital_tz)


def _resets_at(settings: Settings) -> datetime:
    local = _today(settings)
    next_midnight = datetime.combine(
        local.date() + timedelta(days=1), time(0, 0), tzinfo=settings.hospital_tz
    )
    return next_midnight.astimezone(UTC)


def _counter(
    session: Session, day: datetime, scope: str, key: str, *, lock: bool
) -> UsageCounter:
    found = session.get(
        UsageCounter, (day.date(), scope, key), with_for_update=lock or None
    )
    if found is None:
        found = UsageCounter(day=day.date(), scope=scope, key=key)
        if lock:
            # Insert now so the row exists to lock on the next request.
            session.add(found)
            session.flush()
    return found


def reserve(
    session: Session,
    settings: Settings,
    *,
    visitor: str,
    ip: str,
    seconds: float,
) -> None:
    """Check all limits for one upload and count it. Raises 429 when exhausted."""
    day = _today(settings)
    resets = _resets_at(settings).astimezone(settings.hospital_tz)
    reset_text = f"Limits reset at {resets:%H:%M} ({settings.HOSPITAL_TIMEZONE})."
    rows = {
        scope: _counter(session, day, scope, key, lock=True)
        for scope, key in (("global", GLOBAL_KEY), ("visitor", visitor), ("ip", ip))
    }
    budget = settings.TRANSCRIPTION_MINUTES_PER_DAY * 60
    if rows["global"].seconds + seconds > budget:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Demo limit reached: {settings.TRANSCRIPTION_MINUTES_PER_DAY} "
                f"minutes of recording per day for everyone. {reset_text}"
            ),
        )
    for scope in ("visitor", "ip"):
        if rows[scope].recordings >= settings.VISITOR_RECORDINGS_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Demo limit reached: {settings.VISITOR_RECORDINGS_PER_DAY} "
                    f"recordings per day per visitor. {reset_text}"
                ),
            )
    for row in rows.values():
        row.recordings += 1
        row.seconds += seconds
        session.add(row)


def snapshot(
    session: Session, settings: Settings, *, visitor: str, ip: str
) -> QuotaPublic:
    day = _today(settings)
    used_global = _counter(session, day, "global", GLOBAL_KEY, lock=False).seconds
    used_visitor = max(
        _counter(session, day, "visitor", visitor, lock=False).recordings,
        _counter(session, day, "ip", ip, lock=False).recordings,
    )
    return QuotaPublic(
        recording_max_seconds=settings.RECORDING_MAX_SECONDS,
        visitor_recordings_left=max(
            settings.VISITOR_RECORDINGS_PER_DAY - used_visitor, 0
        ),
        global_seconds_left=max(
            int(settings.TRANSCRIPTION_MINUTES_PER_DAY * 60 - used_global), 0
        ),
        resets_at=_resets_at(settings),
    )
