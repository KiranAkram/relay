"""Dashboard, task and flag acknowledgement against the real database.

Each test confirms its own handover, so the dashboard also carries rows left by
earlier tests; assertions look rows up by patient id rather than by position.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Flag, FlagCategory, FlagStatus
from tests.utils.handover import DUE_AT, audit_entries, confirmed

pytestmark = pytest.mark.usefixtures("fake_pipeline")

DASHBOARD = f"{settings.API_V1_STR}/dashboard/"
TASKS = f"{settings.API_V1_STR}/tasks"
FLAGS = f"{settings.API_V1_STR}/flags"


def _rows(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get(DASHBOARD, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["patients"]


def _row(rows: list[dict[str, Any]], patient_id: str) -> dict[str, Any]:
    (row,) = [r for r in rows if r["patient"]["id"] == patient_id]
    return row


def _position(rows: list[dict[str, Any]], patient_id: str) -> int:
    return [r["patient"]["id"] for r in rows].index(patient_id)


def test_dashboard_row_carries_card_tasks_and_flags(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    detail = confirmed(client, normal_user_token_headers)
    bed_7, khan = detail["patients"]

    rows = _rows(client, normal_user_token_headers)
    row = _row(rows, bed_7["patient_id"])
    assert row["handover_id"] == detail["id"]
    assert row["card_id"] == bed_7["id"]
    assert row["illness_severity"] == "watcher"
    assert row["patient"]["bed"] == "CCU-7"
    assert row["patient_summary"] == bed_7["patient_summary"]
    assert row["next_due_at"] == DUE_AT.isoformat().replace("+00:00", "Z")
    assert len(row["tasks"]) >= 1
    (task,) = [t for t in row["tasks"] if t["handover_id"] == detail["id"]]
    assert task["description"] == "Give metoprolol"
    assert task["status"] == "requested"
    categories = {f["category"] for f in row["flags"] if f["task_id"] == task["id"]}
    assert categories == {"task_due_soon", "task_overdue"}

    khan_row = _row(rows, khan["patient_id"])
    assert khan_row["next_due_at"] is None
    assert khan_row["illness_severity"] == "unspecified"


def test_dashboard_orders_by_stated_severity_then_due_time(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    # Khan is unstable with nothing due; Bed 7 is stable with a task due.
    detail = confirmed(
        client,
        normal_user_token_headers,
        bed_7_severity="stable",
        khan_severity="unstable",
    )
    bed_7, khan = detail["patients"]
    rows = _rows(client, normal_user_token_headers)
    assert _position(rows, khan["patient_id"]) < _position(rows, bed_7["patient_id"])
    assert _row(rows, khan["patient_id"])["illness_severity"] == "unstable"
    assert rows[0]["illness_severity"] == "unstable"

    # Latest confirmed card wins: same patients, newer handover, severities swapped.
    newer = confirmed(
        client,
        normal_user_token_headers,
        bed_7_severity="unstable",
        khan_severity="stable",
    )
    rows = _rows(client, normal_user_token_headers)
    assert _position(rows, bed_7["patient_id"]) < _position(rows, khan["patient_id"])
    assert _row(rows, bed_7["patient_id"])["handover_id"] == newer["id"]
    assert _row(rows, khan["patient_id"])["handover_id"] == newer["id"]


def test_dashboard_fires_due_flags_once(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = confirmed(client, normal_user_token_headers)
    handover_id = uuid.UUID(detail["id"])
    flags = db.exec(select(Flag).where(Flag.handover_id == handover_id)).all()
    due_soon = next(f for f in flags if f.category == FlagCategory.task_due_soon)
    overdue = next(f for f in flags if f.category == FlagCategory.task_overdue)
    # Fixtures record on 2 Oct 2026, so both would already be "fired". Push the
    # overdue one into the future to show only elapsed flags fire.
    due_soon.fire_at = datetime.now(UTC) - timedelta(minutes=1)
    overdue.fire_at = datetime.now(UTC) + timedelta(hours=1)
    db.add_all([due_soon, overdue])
    db.commit()

    row = _row(
        _rows(client, normal_user_token_headers), detail["patients"][0]["patient_id"]
    )
    by_id = {f["id"]: f for f in row["flags"]}
    assert by_id[str(due_soon.id)]["fired_at"] is not None
    assert by_id[str(overdue.id)]["fired_at"] is None
    assert len(audit_entries(db, "flag.fired", detail["id"])) == 1

    again = _row(
        _rows(client, normal_user_token_headers), detail["patients"][0]["patient_id"]
    )
    assert {f["id"]: f for f in again["flags"]}[str(due_soon.id)]["fired_at"] == (
        by_id[str(due_soon.id)]["fired_at"]
    )
    assert len(audit_entries(db, "flag.fired", detail["id"])) == 1


def test_acknowledge_task_accepts_it_and_clears_its_flags(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = confirmed(client, normal_user_token_headers)
    bed_7 = detail["patients"][0]
    row = _row(_rows(client, normal_user_token_headers), bed_7["patient_id"])
    (task,) = [t for t in row["tasks"] if t["handover_id"] == detail["id"]]

    response = client.post(
        f"{TASKS}/{task['id']}/acknowledge", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "accepted"
    assert content["acknowledged_at"] is not None
    assert content["acknowledged_by_id"] is not None

    task_flags = db.exec(
        select(Flag).where(Flag.task_id == uuid.UUID(task["id"]))
    ).all()
    assert len(task_flags) == 2
    assert all(f.status == FlagStatus.inactive for f in task_flags)
    assert all(f.acknowledged_at is not None for f in task_flags)
    (entry,) = audit_entries(db, "task.acknowledged", detail["id"])
    assert entry.details == {"flags": 2}

    # Still listed (accepted is open) but with no active flags for this task.
    row = _row(_rows(client, normal_user_token_headers), bed_7["patient_id"])
    (listed,) = [t for t in row["tasks"] if t["id"] == task["id"]]
    assert listed["status"] == "accepted"
    assert not [f for f in row["flags"] if f["task_id"] == task["id"]]

    again = client.post(
        f"{TASKS}/{task['id']}/acknowledge", headers=normal_user_token_headers
    )
    assert again.status_code == 409
    missing = client.post(
        f"{TASKS}/{uuid.uuid4()}/acknowledge", headers=normal_user_token_headers
    )
    assert missing.status_code == 404


def test_acknowledge_unstable_patient_flag(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = confirmed(client, normal_user_token_headers, khan_severity="unstable")
    khan = detail["patients"][1]
    row = _row(_rows(client, normal_user_token_headers), khan["patient_id"])
    (flag,) = [
        f
        for f in row["flags"]
        if f["category"] == "unstable_patient" and f["handover_id"] == detail["id"]
    ]
    assert flag["fired_at"] is not None  # fire_at = confirm time, already elapsed

    response = client.post(
        f"{FLAGS}/{flag['id']}/acknowledge", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"
    assert len(audit_entries(db, "flag.acknowledged", detail["id"])) == 1

    again = client.post(
        f"{FLAGS}/{flag['id']}/acknowledge", headers=normal_user_token_headers
    )
    assert again.status_code == 409
    missing = client.post(
        f"{FLAGS}/{uuid.uuid4()}/acknowledge", headers=normal_user_token_headers
    )
    assert missing.status_code == 404


def test_patients_without_a_handover_are_listed_last(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    confirmed(client, normal_user_token_headers)
    fresh = client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=superuser_token_headers,
        json={
            "mrn": f"T-{uuid.uuid4().hex[:8]}",
            "family_name": "Nobody",
            "given_name": "Mentioned",
            "bed": "CCU-96",
        },
    ).json()

    rows = _rows(client, normal_user_token_headers)
    row = _row(rows, fresh["id"])
    assert row["handover_status"] == "no_handover"
    assert row["card_id"] is None
    assert row["handover_id"] is None
    assert row["illness_severity"] == "unspecified"
    assert row["tasks"] == []

    statuses = [r["handover_status"] for r in rows]
    assert "handed_over" in statuses
    assert statuses.index("no_handover") > statuses.index("handed_over")
    assert statuses == sorted(statuses, key=lambda s: s == "no_handover")
    assert all(r["handover_status"] == "handed_over" for r in rows if r["card_id"])

    client.post(
        f"{settings.API_V1_STR}/patients/{fresh['id']}/discharge",
        headers=superuser_token_headers,
    )
    assert fresh["id"] not in {
        r["patient"]["id"] for r in _rows(client, normal_user_token_headers)
    }


def _bed_7_task(
    client: TestClient, headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    detail = confirmed(client, headers)
    bed_7 = detail["patients"][0]
    row = _row(_rows(client, headers), bed_7["patient_id"])
    (task,) = [t for t in row["tasks"] if t["handover_id"] == detail["id"]]
    return detail, task


def test_complete_task_closes_it_and_its_flags(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail, task = _bed_7_task(client, normal_user_token_headers)

    response = client.post(
        f"{TASKS}/{task['id']}/complete", headers=normal_user_token_headers
    )
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["status"] == "completed"
    assert content["completed_at"] is not None
    assert content["completed_by_id"] is not None
    assert content["cancel_reason"] is None

    task_flags = db.exec(
        select(Flag).where(Flag.task_id == uuid.UUID(task["id"]))
    ).all()
    assert {f.status for f in task_flags} == {FlagStatus.inactive}
    (entry,) = audit_entries(db, "task.completed", detail["id"])
    assert entry.details["flags"] == 2

    row = _row(
        _rows(client, normal_user_token_headers), detail["patients"][0]["patient_id"]
    )
    assert task["id"] not in {t["id"] for t in row["tasks"]}  # off the dashboard

    again = client.post(
        f"{TASKS}/{task['id']}/complete", headers=normal_user_token_headers
    )
    assert again.status_code == 409
    assert (
        client.post(
            f"{TASKS}/{task['id']}/acknowledge", headers=normal_user_token_headers
        )
    ).status_code == 409


def test_cancel_task_requires_a_reason_and_keeps_it(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail, task = _bed_7_task(client, normal_user_token_headers)
    # Acknowledge first: cancel must work from `accepted` too.
    assert (
        client.post(
            f"{TASKS}/{task['id']}/acknowledge", headers=normal_user_token_headers
        )
    ).status_code == 200

    missing = client.post(
        f"{TASKS}/{task['id']}/cancel", headers=normal_user_token_headers, json={}
    )
    assert missing.status_code == 422
    short = client.post(
        f"{TASKS}/{task['id']}/cancel",
        headers=normal_user_token_headers,
        json={"reason": "no"},
    )
    assert short.status_code == 422

    response = client.post(
        f"{TASKS}/{task['id']}/cancel",
        headers=normal_user_token_headers,
        json={"reason": "  Given on the previous shift  "},
    )
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["status"] == "cancelled"
    assert content["cancel_reason"] == "Given on the previous shift"
    (entry,) = audit_entries(db, "task.cancelled", detail["id"])
    assert entry.details["was"] == "accepted"
    assert entry.details["reason"] == "Given on the previous shift"

    record = client.get(
        f"{settings.API_V1_STR}/patients/{detail['patients'][0]['patient_id']}/record",
        headers=normal_user_token_headers,
    ).json()
    (kept,) = [t for t in record["tasks"] if t["id"] == task["id"]]
    assert kept["status"] == "cancelled"
    assert kept["cancel_reason"] == "Given on the previous shift"
