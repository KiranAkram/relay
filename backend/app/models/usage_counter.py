"""Per-day usage counters behind the demo limits.

One row per (day, scope, key): `visitor` (signed cookie id), `ip` (client
address) and `global` (key "*"). Rows are written in the same transaction as
the handover they count, so a refused upload never consumes quota. The day is
the calendar day in the hospital timezone.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class UsageCounter(SQLModel, table=True):
    __tablename__ = "usage_counter"

    day: date = Field(primary_key=True)
    scope: str = Field(primary_key=True, max_length=16)
    key: str = Field(primary_key=True, max_length=64)
    recordings: int = 0
    seconds: float = 0.0


class QuotaPublic(SQLModel):
    """What the Record page needs to show before the doctor presses Record."""

    recording_max_seconds: int
    visitor_recordings_left: int
    global_seconds_left: int
    resets_at: datetime
