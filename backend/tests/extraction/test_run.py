import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.extraction.extractor import DEMO_EXTRACTION
from app.extraction.run import census_from_seed, main, resolve_cards
from app.services.stt import DEMO_TRANSCRIPT

TZ = ZoneInfo("Asia/Karachi")
RECORDED_AT = datetime(2026, 10, 2, 7, 0, tzinfo=TZ)


def test_census_from_seed_builds_patients_with_ids() -> None:
    census = census_from_seed()
    assert len(census) == 10
    assert len({p.id for p in census}) == 10
    assert {p.bed for p in census} >= {"CCU-1", "CCU-10"}


def test_resolve_cards_matches_and_resolves_due_times() -> None:
    bed_7, khan = resolve_cards(DEMO_EXTRACTION, RECORDED_AT, census_from_seed(), TZ)

    assert bed_7["match"]["status"] == "matched"
    assert bed_7["match"]["patient"]["mrn"] == "MRN-100007"
    assert bed_7["match"]["candidates"][0]["reason"] == "bed exact"
    (action,) = bed_7["action_items"]
    assert action["description"] == "Give metoprolol"
    assert action["priority"] == "routine"
    assert action["due_phrase"] == "by 8:30"
    assert datetime.fromisoformat(action["due_at"]) == datetime(
        2026, 10, 2, 3, 30, tzinfo=UTC
    )
    assert action["needs_review"] is False

    assert khan["match"]["status"] == "ambiguous"
    assert khan["match"]["patient"] is None
    assert {c["mrn"] for c in khan["match"]["candidates"]} == {
        "MRN-100001",
        "MRN-100008",
    }
    assert khan["action_items"] == []


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    assert main(argv) == 0
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


def test_main_with_transcript_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "handover.txt"
    transcript.write_text("Bed 7 needs metoprolol by 8:30")

    output = _run(
        [
            str(transcript),
            "--provider",
            "fake",
            "--recorded-at",
            "2026-10-02T07:00:00+05:00",
        ],
        capsys,
    )

    assert output["provider"] == "fake"
    assert output["transcript"] == "Bed 7 needs metoprolol by 8:30"
    assert "stt_provider" not in output
    patients = output["patients"]
    assert isinstance(patients, list) and len(patients) == 2
    assert patients[0]["match"]["patient"]["bed"] == "CCU-7"


def test_main_with_audio_file_transcribes_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audio = tmp_path / "handover.m4a"
    audio.write_bytes(b"not really audio")

    output = _run(
        [str(audio), "--stt-provider", "fake", "--provider", "fake"],
        capsys,
    )

    assert output["stt_provider"] == "fake"
    assert output["stt_model"]
    assert output["transcript"] == DEMO_TRANSCRIPT


def test_main_naive_recorded_at_uses_hospital_timezone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "handover.txt"
    transcript.write_text("Bed 7 needs metoprolol by 8:30")

    output = _run(
        [str(transcript), "--provider", "fake", "--recorded-at", "2026-10-02T07:00:00"],
        capsys,
    )

    assert output["recorded_at"] == "2026-10-02T07:00:00+05:00"
