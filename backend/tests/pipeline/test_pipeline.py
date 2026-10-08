"""Pipeline against the real database with the Fake providers (no API key)."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col, select

from app.models import (
    AuditLog,
    Handover,
    HandoverPatient,
    HandoverStatus,
    IllnessSeverity,
    MatchStatus,
)
from app.pipeline import process_handover
from app.seed.patients import seed_patients
from app.services.intent import FakeIntentChecker
from app.services.storage import LocalDirStorage, audio_key
from app.services.stt import DEMO_TRANSCRIPT, TranscriptionError
from tests.utils.user import create_random_user

RECORDED_AT = datetime(2026, 10, 2, 2, 0, tzinfo=UTC)  # 07:00 in Asia/Karachi


class _BrokenTranscriber:
    def transcribe(
        self,
        audio: bytes,  # noqa: ARG002
        filename: str,  # noqa: ARG002
        hints: Sequence[str] = (),  # noqa: ARG002
    ) -> str:
        raise TranscriptionError("service unavailable")


def _handover_with_audio(db: Session, storage: LocalDirStorage) -> Handover:
    seed_patients(db)
    handover = Handover(
        author_id=create_random_user(db).id,
        recorded_at=RECORDED_AT,
        audio_key="",
        audio_content_type="audio/mp4",
    )
    handover.audio_key = audio_key(handover.id, "handover.m4a")
    storage.put(handover.audio_key, b"not really audio", handover.audio_content_type)
    db.add(handover)
    db.commit()
    return handover


def _live_cards(db: Session, handover: Handover) -> list[HandoverPatient]:
    return list(
        db.exec(
            select(HandoverPatient)
            .where(
                HandoverPatient.handover_id == handover.id,
                col(HandoverPatient.deleted_at).is_(None),
            )
            .order_by(col(HandoverPatient.order_index))
        ).all()
    )


def test_process_handover_writes_transcript_extraction_and_draft_cards(
    db: Session, tmp_path: Path
) -> None:
    storage = LocalDirStorage(tmp_path)
    handover = _handover_with_audio(db, storage)

    process_handover(handover.id, session=db, storage=storage)
    db.refresh(handover)

    assert handover.status == HandoverStatus.awaiting_review
    assert handover.attempts == 1
    assert handover.last_error is None
    assert handover.transcript_text == DEMO_TRANSCRIPT
    assert handover.transcript_provider == "fake"
    assert handover.extraction_raw is not None
    assert len(handover.extraction_raw["patients"]) == 2
    assert handover.extraction_prompt_version == "v1"

    bed_7, khan = _live_cards(db, handover)
    assert bed_7.order_index == 0
    assert bed_7.match_status == MatchStatus.matched
    assert bed_7.patient_id is not None
    assert bed_7.illness_severity == IllnessSeverity.watcher
    assert bed_7.match_candidates[0]["reason"] == "bed exact"
    (action,) = bed_7.action_items
    assert action["description"] == "Give metoprolol"
    assert action["due_kind"] == "clock"
    assert datetime.fromisoformat(action["due_at"]) == datetime(
        2026, 10, 2, 3, 30, tzinfo=UTC
    )
    assert action["needs_review"] is False

    assert khan.match_status == MatchStatus.ambiguous
    assert khan.patient_id is None
    assert len(khan.match_candidates) == 2
    assert khan.action_items == []
    assert len(khan.pending_results) == 1


def test_process_handover_marks_failure_and_keeps_handover_rerunnable(
    db: Session, tmp_path: Path
) -> None:
    storage = LocalDirStorage(tmp_path)
    handover = _handover_with_audio(db, storage)

    process_handover(
        handover.id, session=db, storage=storage, transcriber=_BrokenTranscriber()
    )
    db.refresh(handover)
    assert handover.status == HandoverStatus.failed
    assert handover.attempts == 1
    assert handover.last_error == "TranscriptionError: service unavailable"
    assert _live_cards(db, handover) == []

    process_handover(handover.id, session=db, storage=storage)
    db.refresh(handover)
    assert handover.status == HandoverStatus.awaiting_review
    assert handover.attempts == 2
    assert len(_live_cards(db, handover)) == 2


def test_rerun_replaces_previous_draft_cards(db: Session, tmp_path: Path) -> None:
    storage = LocalDirStorage(tmp_path)
    handover = _handover_with_audio(db, storage)

    process_handover(handover.id, session=db, storage=storage)
    process_handover(handover.id, session=db, storage=storage)

    all_cards = list(
        db.exec(
            select(HandoverPatient).where(HandoverPatient.handover_id == handover.id)
        ).all()
    )
    assert len(all_cards) == 4
    assert len(_live_cards(db, handover)) == 2
    assert sum(c.deleted_at is not None for c in all_cards) == 2


def test_missing_handover_is_a_noop(db: Session) -> None:
    process_handover(uuid.uuid4(), session=db)


def test_rejected_transcript_stops_before_extraction(
    db: Session, tmp_path: Path
) -> None:
    storage = LocalDirStorage(tmp_path)
    handover = _handover_with_audio(db, storage)

    process_handover(
        handover.id,
        session=db,
        storage=storage,
        intent_checker=FakeIntentChecker(probability=0.2),
    )
    db.refresh(handover)
    assert handover.status == HandoverStatus.rejected
    assert handover.transcript_text == DEMO_TRANSCRIPT  # kept for the author
    assert handover.intent_probability == 0.2
    assert handover.extraction_raw is None
    assert handover.last_error is not None
    assert "0.20 below 0.80" in handover.last_error
    assert _live_cards(db, handover) == []
    rejected = db.exec(
        select(AuditLog).where(
            AuditLog.action == "handover.rejected",
            AuditLog.handover_id == handover.id,
        )
    ).all()
    assert len(rejected) == 1 and rejected[0].actor_id is None
