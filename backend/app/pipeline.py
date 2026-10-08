"""Recording -> transcript -> draft I-PASS cards for one handover.

A plain function so the job runner decides where it executes (FastAPI
BackgroundTasks locally, Lambda later). Each stage commits its status so a
reader can see progress; any failure leaves `status=failed` with `last_error`
and the handover can be re-run. Output is draft `handover_patient` rows only —
nothing here touches patient records.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col, select

from app import audit
from app.core.config import settings
from app.core.db import engine
from app.extraction.extractor import Extractor, get_extractor
from app.extraction.matching import match_mention
from app.extraction.resolve import resolve_action_item
from app.extraction.schema import PatientCard
from app.models import Handover, HandoverPatient, HandoverStatus, Patient
from app.services.intent import IntentChecker, get_intent_checker
from app.services.storage import Storage, get_storage
from app.services.stt import Transcriber, get_transcriber

logger = logging.getLogger(__name__)


def process_handover(
    handover_id: uuid.UUID,
    *,
    session: Session | None = None,
    storage: Storage | None = None,
    transcriber: Transcriber | None = None,
    extractor: Extractor | None = None,
    intent_checker: IntentChecker | None = None,
) -> None:
    """Run the pipeline for one handover. Providers default to the configured ones."""
    if session is None:
        with Session(engine) as owned:
            process_handover(
                handover_id,
                session=owned,
                storage=storage,
                transcriber=transcriber,
                extractor=extractor,
                intent_checker=intent_checker,
            )
        return

    handover = session.get(Handover, handover_id)
    if handover is None:
        logger.error("handover %s not found", handover_id)
        return

    handover.attempts += 1
    started = time.perf_counter()
    log = {"handover_id": str(handover_id), "attempt": handover.attempts}
    logger.info("pipeline start", extra=log)
    try:
        _run(
            session,
            handover,
            storage or get_storage(settings),
            transcriber or get_transcriber(settings),
            extractor or get_extractor(settings),
            intent_checker or get_intent_checker(settings),
        )
    except Exception as exc:
        logger.exception(
            "pipeline failed", extra={**log, "duration_ms": _elapsed_ms(started)}
        )
        session.rollback()
        handover.status = HandoverStatus.failed
        handover.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        session.add(handover)
        session.commit()
    else:
        logger.info("pipeline done", extra={**log, "duration_ms": _elapsed_ms(started)})


def _run(
    session: Session,
    handover: Handover,
    storage: Storage,
    transcriber: Transcriber,
    extractor: Extractor,
    intent_checker: IntentChecker,
) -> None:
    _set_status(session, handover, HandoverStatus.transcribing)
    census = list(
        session.exec(
            select(Patient).where(
                col(Patient.active).is_(True), col(Patient.deleted_at).is_(None)
            )
        ).all()
    )
    audio = storage.get(handover.audio_key)
    stage = time.perf_counter()
    handover.transcript_text = transcriber.transcribe(
        audio, Path(handover.audio_key).name, sorted({p.family_name for p in census})
    )
    handover.transcript_provider = settings.STT_PROVIDER
    handover.transcript_model = _model_label(settings.STT_PROVIDER, settings.STT_MODEL)
    _log_stage("transcribed", handover, stage, chars=len(handover.transcript_text))

    # Intent gate: only a clinical handover goes on to extraction. A rejection
    # is final (no cards, no retry); the author sees the reason and may discard.
    stage = time.perf_counter()
    intent = intent_checker.check(handover.transcript_text)
    handover.intent_probability = intent.probability
    handover.intent_model = intent.model
    _log_stage("intent", handover, stage, accepted=int(intent.is_handover))
    if not intent.is_handover:
        handover.last_error = f"Not a clinical handover: {intent.reason}"
        audit.record(
            session,
            "handover.rejected",
            "handover",
            actor_id=None,
            handover_id=handover.id,
            entity_id=handover.id,
            details={
                "probability": round(intent.probability, 3),
                "reason": intent.reason,
            },
        )
        _set_status(session, handover, HandoverStatus.rejected)
        return
    _set_status(session, handover, HandoverStatus.extracting)

    stage = time.perf_counter()
    extraction = extractor.extract(handover.transcript_text)
    handover.extraction_raw = extraction.model_dump(mode="json")
    handover.extraction_model = _model_label(settings.LLM_PROVIDER, settings.LLM_MODEL)
    handover.extraction_prompt_version = settings.EXTRACTION_PROMPT_VERSION
    _log_stage("extracted", handover, stage, cards=len(extraction.patients))
    _set_status(session, handover, HandoverStatus.matching)

    # A re-run replaces the previous drafts; they were never confirmed.
    now = datetime.now(UTC)
    previous = session.exec(
        select(HandoverPatient).where(
            HandoverPatient.handover_id == handover.id,
            col(HandoverPatient.deleted_at).is_(None),
        )
    )
    for old in previous:
        old.deleted_at = now
        session.add(old)
    for index, card in enumerate(extraction.patients):
        session.add(_draft_card(handover, index, card, census))
    _set_status(session, handover, HandoverStatus.awaiting_review)


def _draft_card(
    handover: Handover, index: int, card: PatientCard, census: list[Patient]
) -> HandoverPatient:
    match = match_mention(card.mention, census)
    return HandoverPatient(
        handover_id=handover.id,
        patient_id=match.patient_id,
        order_index=index,
        mention_verbatim=card.mention.verbatim[:255],
        match_status=match.status,
        match_candidates=[c.model_dump(mode="json") for c in match.candidates],
        illness_severity=card.illness_severity,
        severity_evidence=card.severity_evidence,
        patient_summary=card.patient_summary,
        situation_awareness=card.situation_awareness,
        contingencies=[c.model_dump(mode="json") for c in card.contingencies],
        pending_results=[p.model_dump(mode="json") for p in card.pending_results],
        action_items=[
            resolve_action_item(item, handover.recorded_at, settings.hospital_tz)
            for item in card.action_items
        ],
        transcript_excerpt=card.transcript_excerpt,
    )


def _elapsed_ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 1)


def _log_stage(stage: str, handover: Handover, since: float, **counts: int) -> None:
    """Ids, timings and counts only — never transcript or card text at INFO."""
    logger.info(
        "pipeline %s",
        stage,
        extra={
            "handover_id": str(handover.id),
            "stage": stage,
            "duration_ms": _elapsed_ms(since),
            **counts,
        },
    )


def _set_status(session: Session, handover: Handover, status: HandoverStatus) -> None:
    handover.status = status
    session.add(handover)
    session.commit()


def _model_label(provider: str, model: str) -> str:
    return model if provider == "openai" else "fake"
