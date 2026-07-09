import os
import tempfile

# Must be set before `main` (and therefore `backup`) is imported: keep test
# snapshots out of the repo and don't start the periodic scheduler thread.
os.environ["BACKUP_DIR"] = tempfile.mkdtemp(prefix="bns_test_backups_")
os.environ["BACKUP_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import get_db, Base
import models
from auth import get_password_hash
from limiter import limiter

# The login endpoint is rate-limited to 10/minute per client IP. Every test
# request comes from the same "testclient" address, so a full-suite run trips
# the limiter and later auth fixtures fail with 429. Disable it under pytest.
limiter.enabled = False

# Use in-memory SQLite for testing. StaticPool shares the single in-memory
# connection across threads — without it, TestClient requests (served on a
# different thread) would see a separate, empty database.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    user = models.User(
        username="testuser",
        hashed_password=get_password_hash("old_password"),
        name="Test User",
        role="admin",
        can_login=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_user(db_session, username, role):
    user = models.User(
        username=username,
        hashed_password=get_password_hash("irrelevant-pw"),
        name=username.replace("_", " ").title(),
        role=role,
        can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session):
    return _make_user(db_session, "sys_admin", "admin")


@pytest.fixture(scope="function")
def accountant_user(db_session):
    return _make_user(db_session, "school_accountant", "accountant")


def _override_current_user(user):
    import auth as auth_module
    app.dependency_overrides[auth_module.get_current_user] = lambda: user


@pytest.fixture(scope="function")
def as_admin(client, admin_user):
    """Client whose requests are authenticated as a system admin.
    Bypasses the login rate limiter, which would trip on many logins per run."""
    _override_current_user(admin_user)
    return client


@pytest.fixture(scope="function")
def as_accountant(client, accountant_user):
    _override_current_user(accountant_user)
    return client


@pytest.fixture(scope="function")
def sample_student(db_session):
    student = models.Student(
        first_name="Jane",
        last_name="Wanjiku",
        admission_number="BNS-0001",
        grade_level="Grade 1",
        status="Active",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student
