from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.extraction.schema import SpokenTime
from app.extraction.timing import resolve_due
from app.models import DueKind

TZ = ZoneInfo("Asia/Karachi")  # UTC+5, no DST


def _pkt(hour: int, minute: int = 0, day: int = 2) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


def test_unspecified_has_no_due_time() -> None:
    result = resolve_due(SpokenTime(), _pkt(7), TZ)
    assert result.due_at is None
    assert result.needs_review is False


def test_relative_adds_minutes_to_recorded_at() -> None:
    spoken = SpokenTime(kind=DueKind.relative, relative_minutes=60, phrase="in an hour")
    result = resolve_due(spoken, _pkt(7), TZ)
    assert result.due_at == _utc(_pkt(8))
    assert result.due_at is not None and result.due_at.tzinfo is UTC
    assert result.needs_review is False


def test_relative_without_minutes_needs_review() -> None:
    for minutes in (None, -30):
        spoken = SpokenTime(kind=DueKind.relative, relative_minutes=minutes)
        result = resolve_due(spoken, _pkt(7), TZ)
        assert result.due_at is None
        assert result.needs_review is True


def test_clock_with_meridiem_is_taken_literally() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="20:30", meridiem_stated=True)
    result = resolve_due(spoken, _pkt(7), TZ)
    assert result.due_at == _utc(_pkt(20, 30))
    assert result.needs_review is False


def test_clock_without_meridiem_picks_same_morning_when_still_ahead() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="8:30", phrase="by 8:30")
    result = resolve_due(spoken, _pkt(7), TZ)
    assert result.due_at == _utc(_pkt(8, 30))
    assert result.needs_review is False


def test_clock_without_meridiem_picks_evening_when_morning_has_passed() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="08:30")
    result = resolve_due(spoken, _pkt(9), TZ)
    assert result.due_at == _utc(_pkt(20, 30))
    assert result.needs_review is False


def test_clock_without_meridiem_crosses_midnight() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="01:00")
    result = resolve_due(spoken, _pkt(23), TZ)
    assert result.due_at == _utc(_pkt(1, day=3))
    assert result.needs_review is False


def test_clock_spoken_in_24h_has_single_reading() -> None:
    # "fourteen thirty" at 15:00 → tomorrow 14:30, never today 02:30.
    spoken = SpokenTime(kind=DueKind.clock, clock_time="14:30")
    result = resolve_due(spoken, _pkt(15), TZ)
    assert result.due_at == _utc(_pkt(14, 30, day=3))
    assert result.needs_review is True


def test_clock_more_than_18h_away_needs_review() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="20:30", meridiem_stated=True)
    result = resolve_due(spoken, _pkt(21), TZ)
    assert result.due_at == _utc(_pkt(20, 30, day=3))
    assert result.needs_review is True
    assert result.reason is not None


def test_clock_without_time_needs_review() -> None:
    result = resolve_due(SpokenTime(kind=DueKind.clock), _pkt(7), TZ)
    assert result.due_at is None
    assert result.needs_review is True


def test_naive_recorded_at_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_due(SpokenTime(), datetime(2026, 10, 2, 7), TZ)


def test_clock_time_is_normalised_and_validated() -> None:
    assert SpokenTime(clock_time="8:30").clock_time == "08:30"
    with pytest.raises(ValidationError):
        SpokenTime(clock_time="25:00")
    with pytest.raises(ValidationError):
        SpokenTime(clock_time="half eight")
