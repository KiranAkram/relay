"""Handover API against the real database with the Fake providers.

Storage is a per-module temp dir and the job runner is `SyncRunner`, so the
pipeline finishes inside the upload request (see `fake_pipeline`).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import crud
from app.models import (
    DocumentReference,
    Flag,
    FlagCategory,
    Handover,
    HandoverStatus,
    Task,
    UserCreate,
)
from app.services.storage import LocalDirStorage, audio_key
from app.services.stt import MAX_AUDIO_BYTES
from tests.utils.handover import (
    DUE_AT,
    DUE_SOON_AT,
    URL,
    audit_entries,
    resolve_khan,
    reviewed,
    upload,
)
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

pytestmark = pytest.mark.usefixtures("fake_pipeline")


@pytest.fixture(scope="module")
def other_doctor_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    email, password = random_email(), random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    return user_authentication_headers(client=client, email=email, password=password)


# --- upload ------------------------------------------------------------------


def test_upload_runs_pipeline_and_stores_audio(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    fake_pipeline: LocalDirStorage,
) -> None:
    response = upload(client, normal_user_token_headers)
    assert response.status_code == 202
    content = response.json()
    assert content["status"] == HandoverStatus.awaiting_review  # SyncRunner
    assert content["shift_label"] == "night"
    assert content["attempts"] == 1
    assert "audio_key" not in content
    assert "extraction_raw" not in content

    handover_id = uuid.UUID(content["id"])
    assert (
        fake_pipeline.get(audio_key(handover_id, "handover.m4a")) == b"not really audio"
    )
    (doc,) = db.exec(
        select(DocumentReference).where(DocumentReference.handover_id == handover_id)
    ).all()
    assert doc.type == "audio"
    assert doc.patient_id is None
    assert doc.size_bytes == len(b"not really audio")
    (uploaded,) = audit_entries(db, "handover.uploaded", content["id"])
    assert uploaded.request_id == response.headers["x-request-id"]

    detail = client.get(f"{URL}/{handover_id}", headers=normal_user_token_headers)
    assert detail.status_code == 200
    bed_7, khan = detail.json()["patients"]
    assert bed_7["match_status"] == "matched"
    assert bed_7["action_items"][0]["due_at"] == DUE_AT.isoformat().replace(
        "+00:00", "Z"
    )
    assert khan["match_status"] == "ambiguous"
    assert {c["family_name"] for c in khan["match_candidates"]} == {"Khan"}
    assert all(c["bed"] for c in khan["match_candidates"])


def test_upload_rejects_unsupported_suffix(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = upload(client, normal_user_token_headers, filename="notes.txt")
    assert response.status_code == 400
    assert "Unsupported audio type" in response.json()["detail"]


def test_upload_rejects_oversized_file(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = upload(
        client, normal_user_token_headers, data=b"x" * (MAX_AUDIO_BYTES + 1)
    )
    assert response.status_code == 413


def test_upload_rejects_naive_recorded_at(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = upload(
        client, normal_user_token_headers, recorded_at="2026-10-02T07:00:00"
    )
    assert response.status_code == 400
    assert "timezone" in response.json()["detail"]


def test_upload_rejects_implausible_recorded_at(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = upload(client, normal_user_token_headers, recorded_at=future)
    assert response.status_code == 400
    assert "future" in response.json()["detail"]

    stale = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    response = upload(client, normal_user_token_headers, recorded_at=stale)
    assert response.status_code == 400
    assert "days ago" in response.json()["detail"]


# --- list / read -------------------------------------------------------------


def test_read_handovers_scoped_to_author_unless_admin(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    other_doctor_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]

    mine = client.get(f"{URL}/", headers=normal_user_token_headers).json()
    assert handover_id in {h["id"] for h in mine["data"]}
    assert mine["data"][0]["id"] == handover_id  # newest first

    theirs = client.get(f"{URL}/", headers=other_doctor_token_headers).json()
    assert handover_id not in {h["id"] for h in theirs["data"]}

    everyone = client.get(f"{URL}/", headers=superuser_token_headers).json()
    assert handover_id in {h["id"] for h in everyone["data"]}

    filtered = client.get(
        f"{URL}/", headers=normal_user_token_headers, params={"status": "confirmed"}
    ).json()
    assert handover_id not in {h["id"] for h in filtered["data"]}


def test_read_handover_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    other_doctor_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]
    assert (
        client.get(f"{URL}/{handover_id}", headers=other_doctor_token_headers)
    ).status_code == 403
    assert (
        client.get(f"{URL}/{handover_id}", headers=superuser_token_headers)
    ).status_code == 200
    assert (
        client.get(f"{URL}/{uuid.uuid4()}", headers=normal_user_token_headers)
    ).status_code == 404


# --- edit / delete cards -----------------------------------------------------


def test_update_card_text_andaudit_entries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    bed_7 = detail["patients"][0]
    response = client.patch(
        f"{URL}/{detail['id']}/patients/{bed_7['id']}",
        headers=normal_user_token_headers,
        json={"patient_summary": "Fast AF, rate controlled"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["patient_summary"] == "Fast AF, rate controlled"
    assert content["edited_by_doctor"] is True
    assert content["match_status"] == "matched"  # unchanged

    (entry,) = audit_entries(db, "card.edited", detail["id"])
    assert entry.entity_id == uuid.UUID(bed_7["id"])
    assert entry.details["before"] == {"patient_summary": bed_7["patient_summary"]}
    assert entry.details["after"] == {"patient_summary": "Fast AF, rate controlled"}


def test_update_card_resolves_patient(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    khan = detail["patients"][1]
    content = resolve_khan(client, normal_user_token_headers, detail)
    assert content["match_status"] == "doctor_resolved"
    assert content["patient_id"] == khan["match_candidates"][0]["patient_id"]

    response = client.patch(
        f"{URL}/{detail['id']}/patients/{khan['id']}",
        headers=normal_user_token_headers,
        json={"patient_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_update_card_action_items_are_typed(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    bed_7 = detail["patients"][0]
    items = bed_7["action_items"] + [
        {"description": "Repeat ECG", "priority": "urgent", "verbatim": "repeat ECG"}
    ]
    response = client.patch(
        f"{URL}/{detail['id']}/patients/{bed_7['id']}",
        headers=normal_user_token_headers,
        json={"action_items": items},
    )
    assert response.status_code == 200
    added = response.json()["action_items"][1]
    assert added["priority"] == "urgent"
    assert added["due_kind"] == "unspecified"
    assert added["due_at"] is None

    bad = client.patch(
        f"{URL}/{detail['id']}/patients/{bed_7['id']}",
        headers=normal_user_token_headers,
        json={"action_items": [{"priority": "urgent"}]},
    )
    assert bad.status_code == 422


def test_update_card_requires_awaiting_review_and_author(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    other_doctor_token_headers: dict[str, str],
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    card_url = f"{URL}/{detail['id']}/patients/{detail['patients'][0]['id']}"
    body = {"patient_summary": "x"}
    assert (
        client.patch(card_url, headers=other_doctor_token_headers, json=body)
    ).status_code == 403

    assert (
        client.delete(f"{URL}/{detail['id']}", headers=normal_user_token_headers)
    ).status_code == 200
    response = client.patch(card_url, headers=normal_user_token_headers, json=body)
    assert response.status_code == 409
    assert "discarded" in response.json()["detail"]


def test_delete_card(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    khan = detail["patients"][1]
    response = client.delete(
        f"{URL}/{detail['id']}/patients/{khan['id']}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    remaining = client.get(f"{URL}/{detail['id']}", headers=normal_user_token_headers)
    assert [c["id"] for c in remaining.json()["patients"]] == [
        detail["patients"][0]["id"]
    ]
    assert len(audit_entries(db, "card.deleted", detail["id"])) == 1
    assert (
        client.delete(
            f"{URL}/{detail['id']}/patients/{khan['id']}",
            headers=normal_user_token_headers,
        )
    ).status_code == 404


# --- confirm -----------------------------------------------------------------


def test_confirm_refused_while_a_card_is_unresolved(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    response = client.post(
        f"{URL}/{detail['id']}/confirm", headers=normal_user_token_headers
    )
    assert response.status_code == 409
    content = response.json()["detail"]
    assert content["cards"] == [
        {
            "id": detail["patients"][1]["id"],
            "mention_verbatim": detail["patients"][1]["mention_verbatim"],
            "match_status": "ambiguous",
        }
    ]
    assert (
        db.exec(select(Task).where(Task.handover_id == uuid.UUID(detail["id"]))).first()
        is None
    )


def test_confirm_creates_tasks_flags_and_patient_documents(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    handover_id = uuid.UUID(detail["id"])
    bed_7 = detail["patients"][0]
    khan = resolve_khan(client, normal_user_token_headers, detail)
    client.patch(
        f"{URL}/{detail['id']}/patients/{bed_7['id']}",
        headers=normal_user_token_headers,
        json={"illness_severity": "unstable"},
    )

    response = client.post(
        f"{URL}/{detail['id']}/confirm", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == HandoverStatus.confirmed
    assert content["confirmed_at"] is not None
    assert len(content["patients"]) == 2

    (task,) = db.exec(select(Task).where(Task.handover_id == handover_id)).all()
    assert task.patient_id == uuid.UUID(bed_7["patient_id"])
    assert task.handover_patient_id == uuid.UUID(bed_7["id"])
    assert task.description == "Give metoprolol"
    assert task.status == "requested"
    assert task.due_at == DUE_AT
    assert task.due_kind == "clock"
    assert task.due_phrase == "by 8:30"

    flags = db.exec(
        select(Flag).where(Flag.handover_id == handover_id).order_by(col(Flag.category))
    ).all()
    by_category = {f.category: f for f in flags}
    assert set(by_category) == {
        FlagCategory.task_due_soon,
        FlagCategory.task_overdue,
        FlagCategory.unstable_patient,
    }
    assert by_category[FlagCategory.task_due_soon].fire_at == DUE_SOON_AT
    assert by_category[FlagCategory.task_due_soon].task_id == task.id
    assert by_category[FlagCategory.task_overdue].fire_at == DUE_AT
    assert by_category[FlagCategory.unstable_patient].task_id is None
    assert all(f.status == "active" and f.fired_at is None for f in flags)

    patient_docs = db.exec(
        select(DocumentReference).where(
            DocumentReference.handover_id == handover_id,
            col(DocumentReference.patient_id).is_not(None),
        )
    ).all()
    assert {str(d.patient_id) for d in patient_docs} == {
        bed_7["patient_id"],
        khan["patient_id"],
    }
    assert all(d.type == "audio" for d in patient_docs)

    (entry,) = audit_entries(db, "handover.confirmed", detail["id"])
    assert entry.details == {"cards": 2, "tasks": 1, "flags": 3}

    again = client.post(
        f"{URL}/{detail['id']}/confirm", headers=normal_user_token_headers
    )
    assert again.status_code == 409


# --- retry / discard ---------------------------------------------------------


def test_retry_only_when_failed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    response = client.post(
        f"{URL}/{detail['id']}/retry", headers=normal_user_token_headers
    )
    assert response.status_code == 409

    handover = db.get(Handover, uuid.UUID(detail["id"]))
    assert handover is not None
    handover.status = HandoverStatus.failed
    handover.last_error = "TranscriptionError: boom"
    db.add(handover)
    db.commit()

    response = client.post(
        f"{URL}/{detail['id']}/retry", headers=normal_user_token_headers
    )
    assert response.status_code == 202
    content = response.json()
    assert content["status"] == HandoverStatus.awaiting_review
    assert content["attempts"] == 2
    assert len(audit_entries(db, "handover.retried", detail["id"])) == 1


def test_discard_handover(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    response = client.delete(f"{URL}/{detail['id']}", headers=normal_user_token_headers)
    assert response.status_code == 200
    after = client.get(f"{URL}/{detail['id']}", headers=normal_user_token_headers)
    assert after.json()["status"] == HandoverStatus.discarded
    assert len(audit_entries(db, "handover.discarded", detail["id"])) == 1


def test_confirmed_handover_cannot_be_discarded(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    detail = reviewed(client, normal_user_token_headers)
    resolve_khan(client, normal_user_token_headers, detail)
    assert (
        client.post(f"{URL}/{detail['id']}/confirm", headers=normal_user_token_headers)
    ).status_code == 200
    response = client.delete(f"{URL}/{detail['id']}", headers=normal_user_token_headers)
    assert response.status_code == 409
