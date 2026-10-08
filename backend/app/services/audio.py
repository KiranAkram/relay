"""Measure a recording's real length when ffprobe/ffmpeg is installed.

The browser reports a duration, but the client is not trusted for a limit
that costs money. ffmpeg is not available on every machine (not on the
owner's, and nothing may be installed in a session), so this returns None
when it is absent and the caller falls back to the reported value.
Recordings streamed by MediaRecorder often carry no duration in the header,
so ffprobe is tried first and a full decode with ffmpeg second.
"""

import logging
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)

_TIMEOUT_S = 30
_FFMPEG_TIME = re.compile(rb"time=(\d+):(\d\d):(\d\d(?:\.\d+)?)")


def ffmpeg_available() -> bool:
    return shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None


def measure_duration_s(data: bytes) -> float | None:
    if not ffmpeg_available():
        return None
    try:
        probed = subprocess.run(  # noqa: S603 — fixed argv, data on stdin
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                "-i",
                "pipe:0",
            ],
            input=data,
            capture_output=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
        text = probed.stdout.decode().strip()
        if text and text != "N/A":
            return float(text)
        decoded = subprocess.run(  # noqa: S603
            ["ffmpeg", "-v", "info", "-i", "pipe:0", "-f", "null", "-"],
            input=data,
            capture_output=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
        times = _FFMPEG_TIME.findall(decoded.stderr)
        if times:
            hours, minutes, seconds = times[-1]
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        logger.warning("audio duration probe failed: %s", exc)
    return None
