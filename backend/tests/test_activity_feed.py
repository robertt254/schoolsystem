"""The dashboard's recent-activity feed must describe CREATE as an admission,
not fall through to "removed" just because the logged detail has no name."""
import json
import models


def test_create_log_without_a_name_still_reads_as_admitted(as_admin, db_session, admin_user):
    """Regression test for the exact bug: a CREATE audit row whose detail JSON
    has no first_name/last_name (e.g. older data, or any other gap in what a
    caller logs) used to fall through a chained ternary straight to "removed
    a student record" — reporting a completely different action, not just a
    missing name."""
    log = models.AuditLog(
        user_id=admin_user.id, action="CREATE", resource="student", resource_id=999,
        detail=json.dumps({"admission_number": "BNS-0099"}),  # no name on purpose
    )
    db_session.add(log)
    db_session.commit()

    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 1"})
    assert r.status_code == 200
    student_events = [a for a in r.json()["recent_activity"] if a["resource"] == "student"]
    assert student_events[0]["action"] == "CREATE"
    assert student_events[0]["description"] == "admitted a new student"


def test_new_student_shows_as_admitted_not_removed(as_admin):
    r = as_admin.post("/api/students/", json={
        "first_name": "Amani", "last_name": "Otieno",
        "grade_level": "Grade 1", "status": "Active",
    })
    assert r.status_code == 200

    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 1"})
    assert r.status_code == 200
    activity = r.json()["recent_activity"]
    student_events = [a for a in activity if a["resource"] == "student"]
    assert student_events, "expected the new admission to appear in recent activity"
    assert student_events[0]["action"] == "CREATE"
    assert "admitted" in student_events[0]["description"]
    assert "Amani" in student_events[0]["description"]
    assert "removed" not in student_events[0]["description"]
