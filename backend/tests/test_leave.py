"""Tests for leave requests, including granting leave on behalf of staff
who have no portal account (teachers, support staff)."""
import models
from auth import get_password_hash


def _add_staff(db_session, username, role="teacher", can_login=False):
    staff = models.User(
        username=username, hashed_password=get_password_hash("irrelevant-pw"),
        name=username.replace("_", " ").title(), role=role, can_login=can_login,
    )
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)
    return staff


def test_own_leave_request_starts_pending(as_admin):
    r = as_admin.post("/api/leave/", json={
        "leave_type": "Annual", "start_date": "2026-08-03",
        "end_date": "2026-08-05", "reason": "Family event"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["reviewed_by"] is None


def test_admin_grants_leave_for_non_portal_staff(as_admin, admin_user, db_session):
    teacher = _add_staff(db_session, "class_teacher", can_login=False)

    r = as_admin.post("/api/leave/", json={
        "leave_type": "Sick", "start_date": "2026-08-10",
        "end_date": "2026-08-12", "reason": "Medical",
        "staff_id": teacher.id})
    assert r.status_code == 200
    body = r.json()
    # Filed by the approver → granted immediately, attributed to the teacher
    assert body["staff_id"] == teacher.id
    assert body["staff_name"] == teacher.name
    assert body["status"] == "approved"
    assert body["reviewed_by"] == admin_user.id
    assert body["reviewed_at"] is not None


def test_non_admin_cannot_file_leave_for_others(as_accountant, db_session):
    teacher = _add_staff(db_session, "other_teacher")
    r = as_accountant.post("/api/leave/", json={
        "leave_type": "Annual", "start_date": "2026-08-10",
        "end_date": "2026-08-11", "reason": "Trip",
        "staff_id": teacher.id})
    assert r.status_code == 403


def test_grant_leave_unknown_staff_404(as_admin):
    r = as_admin.post("/api/leave/", json={
        "leave_type": "Annual", "start_date": "2026-08-10",
        "end_date": "2026-08-11", "reason": "Trip",
        "staff_id": 9999})
    assert r.status_code == 404


def test_end_before_start_rejected(as_admin):
    r = as_admin.post("/api/leave/", json={
        "leave_type": "Annual", "start_date": "2026-08-10",
        "end_date": "2026-08-01", "reason": "Backwards"})
    assert r.status_code == 400


def test_granted_leave_counts_against_leave_days(as_admin, db_session):
    teacher = _add_staff(db_session, "leave_days_teacher")

    as_admin.post("/api/leave/", json={
        "leave_type": "Annual", "start_date": "2026-08-03",
        "end_date": "2026-08-05", "reason": "Family",
        "staff_id": teacher.id})

    # Staff list shows 3 approved days deducted from the entitlement
    r = as_admin.get("/api/staff/")
    row = next(s for s in r.json() if s["id"] == teacher.id)
    assert row["leave_days_used"] == 3
    assert row["leave_days_left"] == row["accrued_leave_days"] - 3
