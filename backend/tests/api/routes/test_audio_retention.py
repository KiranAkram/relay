"""Serving a recording to its author or an admin, and purging old recordings.

Same setup as `test_handovers.py`: Fake providers, temp-dir storage, pipeline
inline (see `fake_pipeline`).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import crud
from app.core.config import settings
from app.models import DocumentReference, Handover, UserCreate
from app.services.retention import purge_expired
from app.services.storage import LocalDirStorage
from tests.utils.handover import URL, audit_entries, resolve_khan, reviewed, upload
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

pytestmark = pytest.mark.usefixtures("fake_pipeline")


@pytest.fixture(scope="module")
def other_doctor_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    email, password = random_email(), random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    return user_authentication_headers(client=client, email=email, password=password)


def _age(db: Session, handover_id: str, days: int) -> None:
    """Pretend the recording entered storage `days` ago."""
    stored_at = datetime.now(UTC) - timedelta(days=days)
    for doc in db.exec(
        select(DocumentReference).where(
            DocumentReference.handover_id == uuid.UUID(handover_id)
        )
    ).all():
        doc.created_at = stored_at
        db.add(doc)
    db.commit()


def _docs(db: Session, handover_id: str) -> list[DocumentReference]:
    return list(
        db.exec(
            select(DocumentReference)
            .where(DocumentReference.handover_id == uuid.UUID(handover_id))
            .order_by(col(DocumentReference.created_at))
        ).all()
    )


# --- GET /handovers/{id}/audio ----------------------------------------------


def test_author_and_admin_can_play_the_recording(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]
    for headers in (normal_user_token_headers, superuser_token_headers):
        response = client.get(f"{URL}/{handover_id}/audio", headers=headers)
        assert response.status_code == 200
        assert response.content == b"not really audio"
        assert response.headers["content-type"] == "audio/mp4"
        assert response.headers["cache-control"] == "private, no-store"


def test_other_doctor_cannot_play_the_recording(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    other_doctor_token_headers: dict[str, str],
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]
    response = client.get(
        f"{URL}/{handover_id}/audio", headers=other_doctor_token_headers
    )
    assert response.status_code == 403
    response = client.get(
        f"{URL}/{uuid.uuid4()}/audio", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_missing_object_is_404_with_plain_message(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    fake_pipeline: LocalDirStorage,
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]
    handover = db.get(Handover, uuid.UUID(handover_id))
    assert handover is not None
    fake_pipeline.delete(handover.audio_key)  # the Render free-disk case
    response = client.get(
        f"{URL}/{handover_id}/audio", headers=normal_user_token_headers
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"] == "Recording is no longer available on this server"
    )


# --- purge -------------------------------------------------------------------


def test_purge_removes_old_recordings_and_stamps_every_reference(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    fake_pipeline: LocalDirStorage,
) -> None:
    # A confirmed handover: one handover-level audio row + one per patient.
    detail = reviewed(client, normal_user_token_headers)
    resolve_khan(client, normal_user_token_headers, detail)
    assert (
        client.post(
            f"{URL}/{detail['id']}/confirm", headers=normal_user_token_headers
        ).status_code
        == 200
    )
    old_id = detail["id"]
    assert len(_docs(db, old_id)) == 3
    # Upload the fresh one before ageing the old one: an upload runs the purge.
    fresh_id = upload(client, normal_user_token_headers).json()["id"]
    _age(db, old_id, settings.AUDIO_RETENTION_DAYS + 1)
    _age(db, fresh_id, settings.AUDIO_RETENTION_DAYS - 1)
    old_key = db.get(Handover, uuid.UUID(old_id)).audio_key  # type: ignore[union-attr]

    purged = purge_expired(db, fake_pipeline, settings)

    assert purged == 1
    assert fake_pipeline.delete(old_key) is False  # object is gone
    db.expire_all()
    old_docs = _docs(db, old_id)
    assert len(old_docs) == 3
    assert all(d.purged_at is not None for d in old_docs)
    assert all(d.deleted_at is None for d in old_docs)  # row kept for the record
    assert all(d.purged_at is None for d in _docs(db, fresh_id))
    (entry,) = audit_entries(db, "document.purged", old_id)
    assert entry.actor_id is None
    assert entry.details["rows"] == 3
    assert entry.details["object_missing"] is False
    assert entry.details["storage_key"] == old_key

    # The handover itself, transcript and cards are untouched; the audio is 410.
    response = client.get(f"{URL}/{old_id}", headers=normal_user_token_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    response = client.get(f"{URL}/{old_id}/audio", headers=normal_user_token_headers)
    assert response.status_code == 410
    assert "purged on" in response.json()["detail"]

    # Idempotent: nothing left to purge.
    assert purge_expired(db, fake_pipeline, settings) == 0


def test_purge_marks_reference_when_object_already_gone(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    fake_pipeline: LocalDirStorage,
) -> None:
    handover_id = upload(client, normal_user_token_headers).json()["id"]
    handover = db.get(Handover, uuid.UUID(handover_id))
    assert handover is not None
    fake_pipeline.delete(handover.audio_key)
    _age(db, handover_id, settings.AUDIO_RETENTION_DAYS + 1)

    assert purge_expired(db, fake_pipeline, settings) == 1

    db.expire_all()
    (doc,) = _docs(db, handover_id)
    assert doc.purged_at is not None
    (entry,) = audit_entries(db, "document.purged", handover_id)
    assert entry.details["object_missing"] is True


def test_upload_triggers_the_purge(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    old_id = upload(client, normal_user_token_headers).json()["id"]
    _age(db, old_id, settings.AUDIO_RETENTION_DAYS + 1)

    response = upload(client, normal_user_token_headers)
    assert response.status_code == 202

    db.expire_all()
    (doc,) = _docs(db, old_id)
    assert doc.purged_at is not None
    assert audit_entries(db, "document.purged", old_id)
    # The new recording is intact and playable.
    new_id = response.json()["id"]
    assert (
        client.get(
            f"{URL}/{new_id}/audio", headers=normal_user_token_headers
        ).status_code
        == 200
    )
