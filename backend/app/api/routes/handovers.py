"""Handover lifecycle: upload → (pipeline) → review/edit → confirm.

Only the author or an admin may read or change a handover. Cards are drafts
until `confirm`, which is the single place that writes tasks, flags and
patient document references — nothing reaches a patient record before that.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile
from sqlmodel import col, func, select

from app import audit
from app.api.deps import CurrentUser, JobRunnerDep, SessionDep, StorageDep, is_admin
from app.core.config import settings
from app.core.visitor import client_ip, visitor_id
from app.models import (
    ActionItemDraft,
    DocumentReference,
    DocumentType,
    Flag,
    FlagCategory,
    Handover,
    HandoverDetailPublic,
    HandoverPatient,
    HandoverPatientPublic,
    HandoverPatientUpdate,
    HandoverPublic,
    HandoversPublic,
    HandoverStatus,
    IllnessSeverity,
    MatchStatus,
    Message,
    Patient,
    QuotaPublic,
    Task,
    User,
)
from app.services import quota
from app.services.audio import measure_duration_s
from app.services.storage import audio_key
from app.services.stt import AUDIO_SUFFIXES, MAX_AUDIO_BYTES

router = APIRouter(prefix="/handovers", tags=["handovers"])

UNRESOLVED = (MatchStatus.ambiguous, MatchStatus.unmatched)
# Due times are computed from `recorded_at`; a wrong device clock would silently
# shift every alert, so refuse timestamps that cannot be a real end-of-shift.
RECORDED_AT_MAX_FUTURE = timedelta(hours=24)
RECORDED_AT_MAX_PAST = timedelta(days=7)


@router.get("/quota", response_model=QuotaPublic)
def read_quota(
    *,
    session: SessionDep,
    current_user: CurrentUser,  # noqa: ARG001 — any logged-in doctor
    request: Request,
    response: Response,
) -> Any:
    """
    What this visitor may still record today (demo limits).
    """
    return quota.snapshot(
        session,
        settings,
        visitor=visitor_id(request, response),
        ip=client_ip(request),
    )


@router.post("/", status_code=202, response_model=HandoverPublic)
def upload_handover(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: StorageDep,
    job_runner: JobRunnerDep,
    request: Request,
    response: Response,
    file: UploadFile,
    recorded_at: Annotated[datetime, Form()],
    duration_s: Annotated[float, Form(gt=0)],
    shift_label: Annotated[str | None, Form(max_length=64)] = None,
) -> Any:
    """
    Receive the browser recording and start the pipeline.

    `duration_s` is what the recorder measured; it is checked against the
    recording cap and, when ffmpeg is installed, against the audio itself.
    """
    filename = file.filename or ""
    if duration_s > settings.RECORDING_MAX_SECONDS:
        raise HTTPException(
            status_code=413,
            detail=f"Recording longer than {settings.RECORDING_MAX_SECONDS} seconds",
        )
    suffix = Path(filename).suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type {suffix!r}; "
            f"expected one of {', '.join(sorted(AUDIO_SUFFIXES))}",
        )
    if recorded_at.tzinfo is None:
        raise HTTPException(
            status_code=400, detail="recorded_at must include a timezone offset"
        )
    now = datetime.now(UTC)
    if recorded_at > now + RECORDED_AT_MAX_FUTURE:
        raise HTTPException(
            status_code=400, detail="recorded_at is in the future; check the clock"
        )
    if recorded_at < now - RECORDED_AT_MAX_PAST:
        raise HTTPException(
            status_code=400,
            detail=f"recorded_at is more than {RECORDED_AT_MAX_PAST.days} days ago",
        )
    data = file.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio larger than {MAX_AUDIO_BYTES // (1024 * 1024)} MB",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    # The client is not trusted for a limit that costs money: measure when we can.
    measured = measure_duration_s(data)
    if measured is not None and measured > settings.RECORDING_MAX_SECONDS + 1:
        raise HTTPException(
            status_code=413,
            detail=f"Recording longer than {settings.RECORDING_MAX_SECONDS} seconds",
        )
    audio_seconds = measured if measured is not None else duration_s
    # Locks and increments the counters in this transaction; 429 if exhausted.
    quota.reserve(
        session,
        settings,
        visitor=visitor_id(request, response),
        ip=client_ip(request),
        seconds=audio_seconds,
    )

    handover = Handover(
        author_id=current_user.id,
        recorded_at=recorded_at,
        shift_label=shift_label,
        audio_key="",
        audio_content_type=file.content_type or "application/octet-stream",
        audio_duration_s=audio_seconds,
    )
    handover.audio_key = audio_key(handover.id, filename)
    storage.put(handover.audio_key, data, handover.audio_content_type)

    session.add(handover)
    session.add(
        DocumentReference(
            handover_id=handover.id,
            type=DocumentType.audio,
            storage_key=handover.audio_key,
            content_type=handover.audio_content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            author_id=current_user.id,
            authored_at=recorded_at,
        )
    )
    audit.record(
        session,
        "handover.uploaded",
        "handover",
        actor_id=current_user.id,
        handover_id=handover.id,
        entity_id=handover.id,
        details={
            "filename": filename,
            "size_bytes": len(data),
            "duration_s": round(audio_seconds, 1),
            "duration_measured": measured is not None,
        },
    )
    session.commit()
    job_runner.submit(handover.id)
    session.refresh(handover)
    return handover


@router.get("/", response_model=HandoversPublic)
def read_handovers(
    session: SessionDep,
    current_user: CurrentUser,
    status: HandoverStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List the caller's handovers (admins: everyone's), newest first.
    """
    statement = select(Handover).where(col(Handover.deleted_at).is_(None))
    if not is_admin(current_user):
        statement = statement.where(Handover.author_id == current_user.id)
    if status is not None:
        statement = statement.where(Handover.status == status)
    count = session.exec(select(func.count()).select_from(statement.subquery())).one()
    handovers = session.exec(
        statement.order_by(col(Handover.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return HandoversPublic(
        data=[HandoverPublic.model_validate(h) for h in handovers], count=count
    )


@router.get("/{id}", response_model=HandoverDetailPublic)
def read_handover(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get a handover with its live cards.
    """
    handover = _get_handover(session, current_user, id)
    return _detail(session, handover)


@router.patch("/{id}/patients/{card_id}", response_model=HandoverPatientPublic)
def update_card(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    card_id: uuid.UUID,
    card_in: HandoverPatientUpdate,
) -> Any:
    """
    Edit a draft card on the review screen.
    """
    handover = _get_handover(session, current_user, id)
    _require_status(handover, HandoverStatus.awaiting_review)
    card = _get_card(session, handover, card_id)

    update = card_in.model_dump(exclude_unset=True, mode="json")
    if "patient_id" in update:
        patient = (
            session.get(Patient, card_in.patient_id) if card_in.patient_id else None
        )
        if patient is None or not patient.active or patient.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Patient not found")
        update["patient_id"] = patient.id
        update["match_status"] = MatchStatus.doctor_resolved
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")

    before = card.model_dump(mode="json", include=set(update))
    card.sqlmodel_update(update)
    card.edited_by_doctor = True
    session.add(card)
    audit.record(
        session,
        "card.edited",
        "handover_patient",
        actor_id=current_user.id,
        handover_id=handover.id,
        patient_id=card.patient_id,
        entity_id=card.id,
        details={
            "before": before,
            "after": card.model_dump(mode="json", include=set(update)),
        },
    )
    session.commit()
    session.refresh(card)
    return _cards_public(session, [card])[0]


@router.delete("/{id}/patients/{card_id}")
def delete_card(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID, card_id: uuid.UUID
) -> Message:
    """
    Remove a draft card (soft delete).
    """
    handover = _get_handover(session, current_user, id)
    _require_status(handover, HandoverStatus.awaiting_review)
    card = _get_card(session, handover, card_id)
    card.deleted_at = datetime.now(UTC)
    session.add(card)
    audit.record(
        session,
        "card.deleted",
        "handover_patient",
        actor_id=current_user.id,
        handover_id=handover.id,
        patient_id=card.patient_id,
        entity_id=card.id,
        details={"mention_verbatim": card.mention_verbatim},
    )
    session.commit()
    return Message(message="Card deleted successfully")


@router.post("/{id}/retry", status_code=202, response_model=HandoverPublic)
def retry_handover(
    session: SessionDep,
    current_user: CurrentUser,
    job_runner: JobRunnerDep,
    id: uuid.UUID,
) -> Any:
    """
    Re-run the pipeline for a failed handover.
    """
    handover = _get_handover(session, current_user, id)
    _require_status(handover, HandoverStatus.failed)
    audit.record(
        session,
        "handover.retried",
        "handover",
        actor_id=current_user.id,
        handover_id=handover.id,
        entity_id=handover.id,
        details={"attempts": handover.attempts, "last_error": handover.last_error},
    )
    session.commit()
    job_runner.submit(handover.id)
    session.refresh(handover)
    return handover


@router.post("/{id}/confirm", response_model=HandoverDetailPublic)
def confirm_handover(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Confirm the reviewed cards: create tasks, flags and patient document
    references in one transaction. Refused while any card is unresolved.
    """
    handover = _get_handover(session, current_user, id, lock=True)
    _require_status(handover, HandoverStatus.awaiting_review)
    cards = _live_cards(session, handover)
    unresolved = [
        c for c in cards if c.match_status in UNRESOLVED or c.patient_id is None
    ]
    if unresolved:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Resolve or delete unmatched patients before confirming",
                "cards": [
                    {
                        "id": str(c.id),
                        "mention_verbatim": c.mention_verbatim,
                        "match_status": c.match_status,
                    }
                    for c in unresolved
                ],
            },
        )

    now = datetime.now(UTC)
    lead = timedelta(minutes=settings.ALERT_LEAD_MINUTES)
    n_tasks = n_flags = 0
    patients_done: set[uuid.UUID] = set()
    for card in cards:
        assert card.patient_id is not None  # checked above; narrows the type
        patient_id = card.patient_id
        for item in card.action_items:
            draft = ActionItemDraft.model_validate(item)
            task = Task(
                handover_patient_id=card.id,
                handover_id=handover.id,
                patient_id=patient_id,
                description=draft.description,
                due_at=draft.due_at,
                due_kind=draft.due_kind,
                due_phrase=draft.due_phrase,
                priority=draft.priority,
                verbatim=draft.verbatim,
            )
            session.add(task)
            # No Relationship links Task and Flag, so SQLAlchemy won't order the
            # inserts for us: flush the task before adding flags that reference it.
            session.flush()
            n_tasks += 1
            if draft.due_at is not None:
                for category, fire_at in (
                    (FlagCategory.task_due_soon, draft.due_at - lead),
                    (FlagCategory.task_overdue, draft.due_at),
                ):
                    session.add(
                        Flag(
                            patient_id=patient_id,
                            handover_id=handover.id,
                            task_id=task.id,
                            category=category,
                            fire_at=fire_at,
                        )
                    )
                    n_flags += 1
        if card.illness_severity == IllnessSeverity.unstable:
            session.add(
                Flag(
                    patient_id=patient_id,
                    handover_id=handover.id,
                    category=FlagCategory.unstable_patient,
                    fire_at=now,
                )
            )
            n_flags += 1
        if patient_id not in patients_done:
            patients_done.add(patient_id)
            session.add(
                DocumentReference(
                    handover_id=handover.id,
                    patient_id=patient_id,
                    type=DocumentType.audio,
                    storage_key=handover.audio_key,
                    content_type=handover.audio_content_type,
                    author_id=handover.author_id,
                    authored_at=handover.recorded_at,
                )
            )

    handover.status = HandoverStatus.confirmed
    handover.confirmed_at = now
    handover.confirmed_by_id = current_user.id
    session.add(handover)
    audit.record(
        session,
        "handover.confirmed",
        "handover",
        actor_id=current_user.id,
        handover_id=handover.id,
        entity_id=handover.id,
        details={"cards": len(cards), "tasks": n_tasks, "flags": n_flags},
    )
    session.commit()
    session.refresh(handover)
    return _detail(session, handover)


@router.delete("/{id}")
def discard_handover(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Discard an unconfirmed handover.
    """
    handover = _get_handover(session, current_user, id)
    if handover.status == HandoverStatus.confirmed:
        raise HTTPException(
            status_code=409, detail="A confirmed handover cannot be discarded"
        )
    handover.status = HandoverStatus.discarded
    session.add(handover)
    audit.record(
        session,
        "handover.discarded",
        "handover",
        actor_id=current_user.id,
        handover_id=handover.id,
        entity_id=handover.id,
    )
    session.commit()
    return Message(message="Handover discarded")


# --- helpers ---------------------------------------------------------------


def _get_handover(
    session: SessionDep, user: User, id: uuid.UUID, *, lock: bool = False
) -> Handover:
    """Load a handover the user may act on. `lock=True` takes a row lock
    (SELECT ... FOR UPDATE) so two requests cannot both pass a status check."""
    if lock:
        handover = session.exec(
            select(Handover).where(Handover.id == id).with_for_update()
        ).first()
    else:
        handover = session.get(Handover, id)
    if handover is None or handover.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Handover not found")
    if not is_admin(user) and handover.author_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return handover


def _require_status(handover: Handover, expected: HandoverStatus) -> None:
    if handover.status != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Handover is {handover.status}, expected {expected}",
        )


def _live_cards(session: SessionDep, handover: Handover) -> list[HandoverPatient]:
    return list(
        session.exec(
            select(HandoverPatient)
            .where(
                HandoverPatient.handover_id == handover.id,
                col(HandoverPatient.deleted_at).is_(None),
            )
            .order_by(col(HandoverPatient.order_index))
        ).all()
    )


def _get_card(
    session: SessionDep, handover: Handover, card_id: uuid.UUID
) -> HandoverPatient:
    card = session.get(HandoverPatient, card_id)
    if card is None or card.handover_id != handover.id or card.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _cards_public(
    session: SessionDep, cards: list[HandoverPatient]
) -> list[HandoverPatientPublic]:
    """Serialise cards, enriching match candidates with census details."""
    ids = {uuid.UUID(c["patient_id"]) for card in cards for c in card.match_candidates}
    patients = (
        {p.id: p for p in session.exec(select(Patient).where(col(Patient.id).in_(ids)))}
        if ids
        else {}
    )
    result = []
    for card in cards:
        public = HandoverPatientPublic.model_validate(card)
        for candidate in public.match_candidates:
            if (patient := patients.get(candidate.patient_id)) is not None:
                candidate.family_name = patient.family_name
                candidate.given_name = patient.given_name
                candidate.bed = patient.bed
                candidate.mrn = patient.mrn
        result.append(public)
    return result


def _detail(session: SessionDep, handover: Handover) -> HandoverDetailPublic:
    return HandoverDetailPublic.model_validate(
        handover,
        update={"patients": _cards_public(session, _live_cards(session, handover))},
    )
