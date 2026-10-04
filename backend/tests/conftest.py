from collections.abc import Generator
from functools import partial

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, delete

from app.api.deps import get_job_runner_dep, get_storage_dep
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
from app.pipeline import process_handover
from app.seed.patients import seed_patients
from app.services.jobs import SyncRunner
from app.services.storage import LocalDirStorage
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


@pytest.fixture(scope="module")
def fake_pipeline(
    tmp_path_factory: pytest.TempPathFactory, db: Session
) -> Generator[LocalDirStorage]:
    """Seed the census; audio goes to a temp dir and the pipeline runs inline."""
    seed_patients(db)
    local = LocalDirStorage(tmp_path_factory.mktemp("audio"))
    app.dependency_overrides[get_storage_dep] = lambda: local
    app.dependency_overrides[get_job_runner_dep] = lambda: SyncRunner(
        partial(process_handover, storage=local)
    )
    yield local
    app.dependency_overrides.pop(get_storage_dep)
    app.dependency_overrides.pop(get_job_runner_dep)
