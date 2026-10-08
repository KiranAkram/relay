"""Demo limits on the upload route: recording cap, per-visitor and per-address
counts, global minutes per day. Counters are keyed by day, so each test
clears them first."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.visitor import COOKIE_NAME
from app.models import UsageCounter
from tests.utils.handover import URL, upload


@pytest.fixture
def real_limits(db: Session) -> Generator[None]:
    db.execute(delete(UsageCounter))
    db.commit()
    saved = (
        settings.VISITOR_RECORDINGS_PER_DAY,
        settings.TRANSCRIPTION_MINUTES_PER_DAY,
    )
    settings.VISITOR_RECORDINGS_PER_DAY = 3
    settings.TRANSCRIPTION_MINUTES_PER_DAY = 30
    yield
    settings.VISITOR_RECORDINGS_PER_DAY, settings.TRANSCRIPTION_MINUTES_PER_DAY = saved
    db.execute(delete(UsageCounter))
    db.commit()


@pytest.mark.usefixtures("fake_pipeline", "real_limits")
def test_recording_longer_than_the_cap_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = upload(
        client,
        normal_user_token_headers,
        duration_s=settings.RECORDING_MAX_SECONDS + 1,
    )
    assert response.status_code == 413
    assert "longer than" in response.json()["detail"]
    # A refused upload consumes nothing.
    left = client.get(f"{URL}/quota", headers=normal_user_token_headers).json()
    assert left["visitor_recordings_left"] == 3


@pytest.mark.usefixtures("fake_pipeline", "real_limits")
def test_visitor_gets_three_recordings_a_day_then_429(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    before = client.get(f"{URL}/quota", headers=normal_user_token_headers).json()
    assert before["recording_max_seconds"] == settings.RECORDING_MAX_SECONDS
    assert before["visitor_recordings_left"] == 3
    assert COOKIE_NAME in client.cookies

    for _ in range(3):
        assert upload(client, normal_user_token_headers).status_code == 202
    after = client.get(f"{URL}/quota", headers=normal_user_token_headers).json()
    assert after["visitor_recordings_left"] == 0

    fourth = upload(client, normal_user_token_headers)
    assert fourth.status_code == 429
    assert "3 recordings per day" in fourth.json()["detail"]

    # Clearing the cookie does not help: the address is counted as well.
    client.cookies.clear()
    fifth = upload(client, normal_user_token_headers)
    assert fifth.status_code == 429


@pytest.mark.usefixtures("fake_pipeline", "real_limits")
def test_global_minutes_budget_applies_to_everyone(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    settings.TRANSCRIPTION_MINUTES_PER_DAY = 2  # 120 seconds for the whole day
    first = upload(client, normal_user_token_headers, duration_s=100)
    assert first.status_code == 202
    second = upload(client, normal_user_token_headers, duration_s=30)
    assert second.status_code == 429
    assert "minutes of recording per day for everyone" in second.json()["detail"]
    left = client.get(f"{URL}/quota", headers=normal_user_token_headers).json()
    assert left["global_seconds_left"] == 20
