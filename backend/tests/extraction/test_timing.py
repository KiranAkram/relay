from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.extraction.schema import SpokenTime
from app.extraction.timing import resolve_due
from app.models import DueDay, DueKind

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


def test_tomorrow_without_meridiem_takes_the_morning() -> None:
    # 22:00, "tomorrow morning at eight" spoken as "at eight tomorrow".
    spoken = SpokenTime(kind=DueKind.clock, clock_time="08:00", day=DueDay.tomorrow)
    result = resolve_due(spoken, _pkt(22), TZ)
    assert result.due_at == _utc(_pkt(8, day=3))
    assert result.needs_review is False


def test_tomorrow_beyond_horizon_still_needs_review() -> None:
    # 22:00, "five tomorrow afternoon" is 19 h away.
    spoken = SpokenTime(
        kind=DueKind.clock,
        clock_time="17:00",
        meridiem_stated=True,
        day=DueDay.tomorrow,
    )
    result = resolve_due(spoken, _pkt(22), TZ)
    assert result.due_at == _utc(_pkt(17, day=3))
    assert result.needs_review is True


def test_tomorrow_said_after_midnight_is_literal_and_flagged() -> None:
    # 01:00 on a night shift, "tomorrow at eight" may mean this morning; the
    # literal date is 31 h away, so a person checks it instead of code guessing.
    spoken = SpokenTime(kind=DueKind.clock, clock_time="08:00", day=DueDay.tomorrow)
    result = resolve_due(spoken, _pkt(1, day=3), TZ)
    assert result.due_at == _utc(_pkt(8, day=4))
    assert result.needs_review is True


def test_today_without_meridiem_takes_the_reading_still_ahead() -> None:
    spoken = SpokenTime(kind=DueKind.clock, clock_time="04:00", day=DueDay.today)
    result = resolve_due(spoken, _pkt(14), TZ)
    assert result.due_at == _utc(_pkt(16))
    assert result.needs_review is False


def test_today_already_passed_keeps_time_and_needs_review() -> None:
    spoken = SpokenTime(
        kind=DueKind.clock, clock_time="18:00", meridiem_stated=True, day=DueDay.today
    )
    result = resolve_due(spoken, _pkt(22), TZ)
    assert result.due_at == _utc(_pkt(18))
    assert result.needs_review is True
    assert result.reason == "time already passed on the day stated"


def test_midnight_tonight_is_the_coming_midnight() -> None:
    spoken = SpokenTime(
        kind=DueKind.clock, clock_time="00:00", meridiem_stated=True, day=DueDay.today
    )
    result = resolve_due(spoken, _pkt(20), TZ)
    assert result.due_at == _utc(_pkt(0, day=3))
    assert result.needs_review is False


def test_day_is_ignored_without_a_clock_time() -> None:
    spoken = SpokenTime(day=DueDay.tomorrow, phrase="kal subah")
    result = resolve_due(spoken, _pkt(14), TZ)
    assert result.due_at is None
    assert result.needs_review is False


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
