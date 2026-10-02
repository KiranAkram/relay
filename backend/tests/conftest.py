from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    DocumentReference,
    Flag,
    Handover,
    HandoverPatient,
    Item,
    Patient,
    Task,
    User,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
        # audit_log rejects DELETE (append-only trigger); TRUNCATE is allowed.
        session.execute(text("TRUNCATE audit_log"))
        # Order matters: delete children before their parents (`handover`, `patient`, `user`).
        for model in (
            Flag,
            Task,
            DocumentReference,
            HandoverPatient,
            Handover,
            Item,
            Patient,
            User,
        ):
            session.execute(delete(model))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
