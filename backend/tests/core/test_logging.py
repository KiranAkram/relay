"""Log formatting and request-id plumbing, no database."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var
from app.core.request_id import RequestIdMiddleware


def _format(record: logging.LogRecord) -> dict:
    RequestIdFilter().filter(record)
    return json.loads(JsonFormatter().format(record))


def test_json_formatter_emits_one_parseable_object_with_extras() -> None:
    logger = logging.getLogger("tests.logging")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        1,
        "pipeline %s",
        ("done",),
        None,
        extra={"handover_id": "abc", "duration_ms": 12.5},
    )
    token = request_id_var.set("req-1")
    try:
        payload = _format(record)
    finally:
        request_id_var.reset(token)

    assert payload["message"] == "pipeline done"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.logging"
    assert payload["request_id"] == "req-1"
    assert payload["handover_id"] == "abc"
    assert payload["duration_ms"] == 12.5
    assert payload["time"].endswith("+00:00")


def test_json_formatter_includes_exceptions() -> None:
    logger = logging.getLogger("tests.logging")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logger.makeRecord(
            logger.name, logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
        )
    payload = _format(record)
    assert payload["request_id"] is None
    assert "ValueError: boom" in payload["exception"]


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    def echo() -> dict[str, str | None]:
        return {"request_id": request_id_var.get()}

    return app


def test_middleware_generates_an_id_and_returns_it(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/echo")
    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32
    assert response.json()["request_id"] == request_id
    assert request_id_var.get() is None  # reset after the request


def test_middleware_keeps_a_caller_supplied_id(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/echo", headers={"X-Request-ID": "gateway-42"})
    assert response.headers["x-request-id"] == "gateway-42"
    assert response.json()["request_id"] == "gateway-42"


def test_middleware_logs_one_line_per_request(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"), TestClient(app) as client:
        client.get("/echo")
    (record,) = [r for r in caplog.records if r.name == "app.request"]
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.path == "/echo"  # type: ignore[attr-defined]
    assert record.status == 200  # type: ignore[attr-defined]
    assert record.duration_ms >= 0  # type: ignore[attr-defined]
