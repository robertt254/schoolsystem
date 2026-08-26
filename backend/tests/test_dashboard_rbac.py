"""Net revenue ('what the school makes') is restricted to admin/principal/
accountant on the main dashboard — subordinate staff must not see it."""
import pytest
import models
from main import app
from auth import get_password_hash
import auth as auth_module


def _make_user(db_session, username, role):
    user = models.User(
        username=username, hashed_password=get_password_hash("irrelevant-pw"),
        name=username.replace("_", " ").title(), role=role, can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_role(client, db_session):
    def _for(role):
        user = _make_user(db_session, f"user_{role}", role)
        app.dependency_overrides[auth_module.get_current_user] = lambda: user
        return client
    return _for


def test_admin_principal_accountant_see_net_revenue(as_role):
    for role in ["admin", "principal", "accountant"]:
        r = as_role(role).get("/api/dashboard/stats", params={"term": "Term 1"})
        assert r.status_code == 200
        assert r.json()["total_revenue"] is not None


def test_subordinate_staff_do_not_see_net_revenue(as_role):
    for role in ["secretary", "teacher", "senior_teacher", "support_staff"]:
        r = as_role(role).get("/api/dashboard/stats", params={"term": "Term 1"})
        assert r.status_code == 200
        assert r.json()["total_revenue"] is None


def test_upcoming_events_shown_to_everyone(as_role):
    r = as_role("teacher").get("/api/dashboard/stats", params={"term": "Term 1"})
    assert "upcoming_events" in r.json()
