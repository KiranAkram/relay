"""Incoming doctor's dashboard.

Priority = stated illness severity, then the nearest due task. Flags have no
scheduler: a flag whose `fire_at` has passed is stamped `fired_at` the first
time this endpoint observes it, so there is a record of when the alert went off.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from sqlmodel import col, select

from app import audit
from app.api.deps import CurrentUser, SessionDep
from app.api.routes.patients import bed_key
from app.models import (
    DashboardHandoverStatus,
    DashboardPatientPublic,
    DashboardPublic,
    Flag,
    FlagPublic,
    FlagStatus,
    Handover,
    HandoverPatient,
    HandoverStatus,
    IllnessSeverity,
    Patient,
    PatientPublic,
    Task,
    TaskPublic,
    TaskStatus,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SEVERITY_RANK = {
    IllnessSeverity.unstable: 0,
    IllnessSeverity.watcher: 1,
    IllnessSeverity.stable: 2,
    IllnessSeverity.unspecified: 3,
}
OPEN_TASK_STATUSES = (TaskStatus.requested, TaskStatus.accepted)
FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


@router.get("/", response_model=DashboardPublic)
def read_dashboard(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Every active census patient, highest priority first; patients with no
    confirmed handover come last, marked `no_handover`.
    """
    now = datetime.now(UTC)
    census = session.exec(
        select(Patient).where(
            col(Patient.active).is_(True), col(Patient.deleted_at).is_(None)
        )
    ).all()
    if not census:
        return DashboardPublic(generated_at=now, patients=[])
    patient_ids = [p.id for p in census]
    latest = _latest_confirmed_cards(session)
    tasks_by_patient: dict[uuid.UUID, list[Task]] = {pid: [] for pid in patient_ids}
    for task in session.exec(
        select(Task)
        .where(
            col(Task.patient_id).in_(patient_ids),
            col(Task.status).in_(OPEN_TASK_STATUSES),
            col(Task.deleted_at).is_(None),
        )
        .order_by(col(Task.due_at).asc().nulls_last(), col(Task.created_at))
    ):
        tasks_by_patient[task.patient_id].append(task)

    flags_by_patient: dict[uuid.UUID, list[Flag]] = {pid: [] for pid in patient_ids}
    fired = 0
    for flag in session.exec(
        select(Flag)
        .where(
            col(Flag.patient_id).in_(patient_ids),
            Flag.status == FlagStatus.active,
            col(Flag.deleted_at).is_(None),
        )
        .order_by(col(Flag.fire_at))
    ):
        if flag.fired_at is None and flag.fire_at <= now:
            flag.fired_at = now
            session.add(flag)
            audit.record(
                session,
                "flag.fired",
                "flag",
                actor_id=None,
                handover_id=flag.handover_id,
                patient_id=flag.patient_id,
                entity_id=flag.id,
                details={
                    "category": flag.category,
                    "observed_by": str(current_user.id),
                },
            )
            fired += 1
        flags_by_patient[flag.patient_id].append(flag)
    if fired:
        session.commit()

    rows = []
    for patient in census:
        tasks = tasks_by_patient[patient.id]
        flags = [FlagPublic.model_validate(f) for f in flags_by_patient[patient.id]]
        due_times = [t.due_at for t in tasks if t.due_at is not None]
        public = PatientPublic.model_validate(patient)
        if patient.id not in latest:
            rows.append(
                DashboardPatientPublic(
                    patient=public,
                    handover_status=DashboardHandoverStatus.no_handover,
                    handover_id=None,
                    card_id=None,
                    confirmed_at=None,
                    illness_severity=IllnessSeverity.unspecified,
                    patient_summary=None,
                    situation_awareness=None,
                    contingencies=[],
                    pending_results=[],
                    tasks=[TaskPublic.model_validate(t) for t in tasks],
                    flags=flags,
                    next_due_at=min(due_times) if due_times else None,
                )
            )
            continue
        card, handover = latest[patient.id]
        assert handover.confirmed_at is not None  # status is confirmed
        rows.append(
            DashboardPatientPublic(
                patient=public,
                handover_status=DashboardHandoverStatus.handed_over,
                handover_id=handover.id,
                card_id=card.id,
                confirmed_at=handover.confirmed_at,
                illness_severity=card.illness_severity,
                patient_summary=card.patient_summary,
                situation_awareness=card.situation_awareness,
                contingencies=card.contingencies,
                pending_results=card.pending_results,
                tasks=[TaskPublic.model_validate(t) for t in tasks],
                flags=flags,
                next_due_at=min(due_times) if due_times else None,
            )
        )
    by_id = {p.id: p for p in census}
    rows.sort(
        key=lambda r: (
            r.handover_status == DashboardHandoverStatus.no_handover,
            SEVERITY_RANK[r.illness_severity],
            r.next_due_at or FAR_FUTURE,
            bed_key(by_id[r.patient.id]),
        )
    )
    return DashboardPublic(generated_at=now, patients=rows)


def _latest_confirmed_cards(
    session: SessionDep,
) -> dict[uuid.UUID, tuple[HandoverPatient, Handover]]:
    """Newest confirmed card per active census patient."""
    rows = session.exec(
        select(HandoverPatient, Handover)
        .join(Handover, col(HandoverPatient.handover_id) == col(Handover.id))
        .join(Patient, col(HandoverPatient.patient_id) == col(Patient.id))
        .where(
            Handover.status == HandoverStatus.confirmed,
            col(Handover.deleted_at).is_(None),
            col(HandoverPatient.deleted_at).is_(None),
            col(Patient.active).is_(True),
            col(Patient.deleted_at).is_(None),
        )
        .order_by(col(Handover.confirmed_at).desc(), col(HandoverPatient.order_index))
    ).all()
    latest: dict[uuid.UUID, tuple[HandoverPatient, Handover]] = {}
    for card, handover in rows:
        assert card.patient_id is not None  # joined on it
        latest.setdefault(card.patient_id, (card, handover))
    return latest
