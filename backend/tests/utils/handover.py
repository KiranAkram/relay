"""Drive a handover through the API with the Fake providers.

The Fake pipeline always yields two cards: Bed 7 (matched, one action item
due 03:30Z) and Mr Khan (ambiguous between the two seeded Khans).
"""

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, select

from app.core.config import settings
from app.models import AuditLog, HandoverStatus

URL = f"{settings.API_V1_STR}/handovers"
# The upload route refuses recordings older than a week or in the future, so
# anchor on today: 07:00 in Asia/Karachi, with "by 8:30" resolving to 03:30Z.
_TODAY: date = datetime.now(UTC).date()
RECORDED_AT = datetime.combine(_TODAY, time(2, 0), tzinfo=UTC)
DUE_AT = datetime.combine(_TODAY, time(3, 30), tzinfo=UTC)
DUE_SOON_AT = datetime.combine(_TODAY, time(3, 15), tzinfo=UTC)


def upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str = "handover.m4a",
    data: bytes = b"not really audio",
    recorded_at: str = RECORDED_AT.isoformat(),
) -> Response:
    return client.post(
        f"{URL}/",
        headers=headers,
        files={"file": (filename, data, "audio/mp4")},
        data={"recorded_at": recorded_at, "shift_label": "night"},
    )


def reviewed(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """Upload and return the detail: two cards, Bed 7 matched, Khan ambiguous."""
    handover_id = upload(client, headers).json()["id"]
    detail = client.get(f"{URL}/{handover_id}", headers=headers).json()
    assert detail["status"] == HandoverStatus.awaiting_review
    assert [c["match_status"] for c in detail["patients"]] == ["matched", "ambiguous"]
    return detail


def resolve_khan(
    client: TestClient, headers: dict[str, str], detail: dict[str, Any]
) -> dict[str, Any]:
    khan = detail["patients"][1]
    # Both candidates score the same; pick deterministically so tests agree.
    chosen = min(khan["match_candidates"], key=lambda c: c["mrn"])
    return client.patch(
        f"{URL}/{detail['id']}/patients/{khan['id']}",
        headers=headers,
        json={"patient_id": chosen["patient_id"]},
    ).json()


def edit_card(
    client: TestClient,
    headers: dict[str, str],
    detail: dict[str, Any],
    index: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    card = detail["patients"][index]
    response = client.patch(
        f"{URL}/{detail['id']}/patients/{card['id']}", headers=headers, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirmed(
    client: TestClient,
    headers: dict[str, str],
    *,
    bed_7_severity: str | None = None,
    khan_severity: str | None = None,
) -> dict[str, Any]:
    """Upload, resolve Khan, optionally set severities, confirm; return the detail."""
    detail = reviewed(client, headers)
    resolve_khan(client, headers, detail)
    if bed_7_severity:
        edit_card(client, headers, detail, 0, {"illness_severity": bed_7_severity})
    if khan_severity:
        edit_card(client, headers, detail, 1, {"illness_severity": khan_severity})
    response = client.post(f"{URL}/{detail['id']}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def audit_entries(db: Session, action: str, handover_id: str) -> list[AuditLog]:
    return list(
        db.exec(
            select(AuditLog).where(
                AuditLog.action == action,
                AuditLog.handover_id == uuid.UUID(handover_id),
            )
        ).all()
    )
