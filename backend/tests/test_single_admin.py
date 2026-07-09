"""The single-system-admin invariant: exactly one admin account exists, and no
one can create another, promote into it, demote it, terminate it, or reset its
password."""
import pytest

import models
from main import app
from auth import get_password_hash
import auth as auth_module


@pytest.fixture
def principal_user(db_session):
    user = models.User(
        username="the_principal", hashed_password=get_password_hash("irrelevant-pw"),
        name="The Principal", role="principal", can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_principal(client, principal_user):
    app.dependency_overrides[auth_module.get_current_user] = lambda: principal_user
    return client


def _teacher(db_session):
    user = models.User(
        username="a_teacher", hashed_password=get_password_hash("irrelevant-pw"),
        name="A Teacher", role="teacher", can_login=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_no_one_can_create_another_admin(as_admin):
    r = as_admin.post("/api/staff/", json={
        "username": "second_admin", "name": "Second Admin",
        "role": "admin", "password": "supersecret1"})
    assert r.status_code == 403
    assert "one system administrator" in r.json()["detail"]


def test_principal_cannot_create_admin_either(as_principal):
    r = as_principal.post("/api/staff/", json={
        "username": "sneaky_admin", "name": "Sneaky Admin",
        "role": "admin", "password": "supersecret1"})
    assert r.status_code == 403


def test_no_one_can_be_promoted_to_admin(as_admin, db_session):
    teacher = _teacher(db_session)
    r = as_admin.put(f"/api/staff/{teacher.id}", json={"role": "admin"})
    assert r.status_code == 403
    assert "promoted" in r.json()["detail"]


def test_admin_role_cannot_be_changed(as_admin, admin_user):
    r = as_admin.put(f"/api/staff/{admin_user.id}", json={"role": "principal"})
    assert r.status_code == 400
    assert "cannot be changed" in r.json()["detail"]


def test_admin_account_cannot_be_terminated(as_principal, admin_user):
    r = as_principal.delete(f"/api/staff/{admin_user.id}")
    assert r.status_code == 403
    assert "cannot be terminated" in r.json()["detail"]


def test_no_one_can_reset_admin_password(as_principal, admin_user):
    r = as_principal.post(f"/api/staff/{admin_user.id}/reset-password",
                          json={"new_password": "hijacked-pw1"})
    assert r.status_code == 403
    assert "administrator" in r.json()["detail"]
