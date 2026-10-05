"""Demo-access endpoint, no database."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.utils import router
from app.core.config import settings


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_demo_access_hidden_by_default(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DEMO_ACCESS_BANNER", False)
    assert client.get("/utils/demo-access/").json() is None


def test_demo_access_shown_when_enabled_and_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DEMO_ACCESS_BANNER", True)
    monkeypatch.setattr(settings, "DEMO_DOCTOR_EMAIL", "doctor@example.com")
    monkeypatch.setattr(settings, "DEMO_DOCTOR_PASSWORD", "demo-pass-1")
    assert client.get("/utils/demo-access/").json() == {
        "email": "doctor@example.com",
        "password": "demo-pass-1",
    }

    monkeypatch.setattr(settings, "DEMO_DOCTOR_PASSWORD", None)
    assert client.get("/utils/demo-access/").json() is None
