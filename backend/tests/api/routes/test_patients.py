"""Census routes and the patient record, against the real database."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import AuditLog
from tests.utils.handover import confirmed
from tests.utils.utils import random_lower_string

pytestmark = pytest.mark.usefixtures("fake_pipeline")

URL = f"{settings.API_V1_STR}/patients"


def _new_patient(bed: str | None = "CCU-99") -> dict[str, str | None]:
    return {
        "mrn": f"T-{random_lower_string()[:8]}",
        "family_name": "Test",
        "given_name": "Patient",
        "bed": bed,
        "unit": "CCU",
    }


def _audit(db: Session, action: str, patient_id: str) -> list[AuditLog]:
    return list(
        db.exec(
            select(AuditLog).where(
                AuditLog.action == action,
                AuditLog.patient_id == uuid.UUID(patient_id),
            )
        ).all()
    )


def test_read_patients_is_the_census_in_bed_order(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(f"{URL}/", headers=normal_user_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 10  # seeded census
    beds = [p["bed"] for p in content["data"] if p["bed"]]
    assert beds.index("CCU-7") < beds.index("CCU-10")  # natural, not lexical
    assert all(p["active"] for p in content["data"])


def test_one_active_patient_per_bed(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    taken = client.post(
        f"{URL}/", headers=superuser_token_headers, json=_new_patient("CCU-7")
    )
    assert taken.status_code == 409
    assert "Bed CCU-7 is occupied by MRN-100007" in taken.json()["detail"]

    # CCU-95 is used only here: the patient stays active, so the bed stays
    # taken for the rest of the run, and the discharge test needs CCU-97 free.
    created = client.post(
        f"{URL}/", headers=superuser_token_headers, json=_new_patient("CCU-95")
    )
    assert created.status_code == 200, created.text
    moved = client.patch(
        f"{URL}/{created.json()['id']}",
        headers=superuser_token_headers,
        json={"bed": "CCU-8"},
    )
    assert moved.status_code == 409
    assert "occupied" in moved.json()["detail"]


def test_only_admins_change_the_census(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    body = _new_patient()
    denied = client.post(f"{URL}/", headers=normal_user_token_headers, json=body)
    assert denied.status_code == 403

    created = client.post(f"{URL}/", headers=superuser_token_headers, json=body)
    assert created.status_code == 200, created.text
    patient = created.json()
    assert patient["mrn"] == body["mrn"]
    assert len(_audit(db, "patient.created", patient["id"])) == 1

    duplicate = client.post(f"{URL}/", headers=superuser_token_headers, json=body)
    assert duplicate.status_code == 409

    edited = client.patch(
        f"{URL}/{patient['id']}",
        headers=superuser_token_headers,
        json={"bed": "CCU-98", "admitting_diagnosis": "NSTEMI"},
    )
    assert edited.status_code == 200
    assert edited.json()["bed"] == "CCU-98"
    (entry,) = _audit(db, "patient.updated", patient["id"])
    assert entry.details["before"]["bed"] == "CCU-99"
    assert entry.details["after"]["admitting_diagnosis"] == "NSTEMI"

    via_patch = client.patch(
        f"{URL}/{patient['id']}",
        headers=superuser_token_headers,
        json={"active": False},
    )
    assert via_patch.status_code == 400

    assert (
        client.patch(
            f"{URL}/{patient['id']}",
            headers=normal_user_token_headers,
            json={"bed": "x"},
        ).status_code
        == 403
    )


def test_discharge_keeps_the_record_but_leaves_the_census(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    patient = client.post(
        f"{URL}/", headers=superuser_token_headers, json=_new_patient("CCU-97")
    ).json()

    response = client.post(
        f"{URL}/{patient['id']}/discharge", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert len(_audit(db, "patient.discharged", patient["id"])) == 1

    census = client.get(f"{URL}/", headers=normal_user_token_headers).json()
    assert patient["id"] not in {p["id"] for p in census["data"]}
    everyone = client.get(
        f"{URL}/",
        headers=normal_user_token_headers,
        params={"include_discharged": True},
    ).json()
    assert patient["id"] in {p["id"] for p in everyone["data"]}

    still_readable = client.get(
        f"{URL}/{patient['id']}", headers=normal_user_token_headers
    )
    assert still_readable.status_code == 200

    again = client.post(
        f"{URL}/{patient['id']}/discharge", headers=superuser_token_headers
    )
    assert again.status_code == 409


def test_patient_record_lists_confirmed_cards_tasks_flags_and_audio(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    detail = confirmed(client, normal_user_token_headers, bed_7_severity="unstable")
    bed_7 = detail["patients"][0]

    response = client.get(
        f"{URL}/{bed_7['patient_id']}/record", headers=normal_user_token_headers
    )
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["patient"]["id"] == bed_7["patient_id"]

    assert record["cards"][0]["card"]["id"] == bed_7["id"]  # newest first
    assert record["cards"][0]["handover_id"] == detail["id"]
    assert record["cards"][0]["author_id"] == detail["author_id"]

    tasks = [t for t in record["tasks"] if t["handover_id"] == detail["id"]]
    assert [t["description"] for t in tasks] == ["Give metoprolol"]
    categories = {
        f["category"] for f in record["flags"] if f["handover_id"] == detail["id"]
    }
    assert categories == {"task_due_soon", "task_overdue", "unstable_patient"}
    audio = [d for d in record["documents"] if d["handover_id"] == detail["id"]]
    assert [d["type"] for d in audio] == ["audio"]
    assert "storage_key" not in audio[0]


def test_patient_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    missing = uuid.uuid4()
    assert (
        client.get(f"{URL}/{missing}", headers=normal_user_token_headers).status_code
        == 404
    )
    assert (
        client.get(
            f"{URL}/{missing}/record", headers=normal_user_token_headers
        ).status_code
        == 404
    )
