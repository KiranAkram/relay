"""Duration probe degrades to "unknown" when ffmpeg is not installed."""

import pytest

from app.services import audio


def test_without_ffmpeg_duration_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio.shutil, "which", lambda _name: None)
    assert audio.ffmpeg_available() is False
    assert audio.measure_duration_s(b"\x1aE\xdf\xa3 not really webm") is None


def test_ffmpeg_decode_time_is_parsed() -> None:
    stderr = b"size=N/A time=00:01:57.48 bitrate=N/A speed= 300x\nsize=N/A time=00:02:03.20 bitrate=N/A"
    hours, minutes, seconds = audio._FFMPEG_TIME.findall(stderr)[-1]
    assert int(hours) * 3600 + int(minutes) * 60 + float(seconds) == pytest.approx(
        123.2
    )
