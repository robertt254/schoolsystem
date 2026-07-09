"""Tests for the discipline endpoints: create, list/filter, resolve, delete."""


def _create_record(client, student_id):
    return client.post("/api/discipline/", json={
        "student_id": student_id,
        "incident_date": "2026-07-01",
        "incident_type": "Lateness",
        "description": "Arrived 40 minutes late",
        "severity": "Minor",
    })


def test_create_and_list_records(as_admin, sample_student):
    r = _create_record(as_admin, sample_student.id)
    assert r.status_code == 201
    body = r.json()
    assert body["student_name"] == "Jane Wanjiku"
    assert body["grade_level"] == sample_student.grade_level
    assert body["status"] == "Open"

    r = as_admin.get("/api/discipline/")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Filter by status and by student
    assert len(as_admin.get("/api/discipline/", params={"status": "Open"}).json()) == 1
    assert len(as_admin.get("/api/discipline/", params={"status": "Resolved"}).json()) == 0
    assert len(as_admin.get("/api/discipline/", params={"student_id": sample_student.id}).json()) == 1


def test_create_record_unknown_student_404(as_admin):
    r = _create_record(as_admin, 9999)
    assert r.status_code == 404


def test_resolve_and_delete_record(as_admin, sample_student):
    record_id = _create_record(as_admin, sample_student.id).json()["id"]

    r = as_admin.put(f"/api/discipline/{record_id}", json={
        "status": "Resolved", "action_taken": "Warned", "action_date": "2026-07-02"})
    assert r.status_code == 200
    assert r.json()["status"] == "Resolved"
    assert r.json()["action_taken"] == "Warned"

    r = as_admin.delete(f"/api/discipline/{record_id}")
    assert r.status_code == 204
    assert as_admin.get("/api/discipline/").json() == []
