"""Tests for the attendance endpoints: bulk marking, today's register, summaries."""


def test_bulk_mark_and_today_register(as_admin, sample_student):
    # Mark present (student has no guardian phone → no SMS side effects)
    r = as_admin.post("/api/attendance/bulk", json=[
        {"student_id": sample_student.id, "is_present": True, "remarks": None}])
    assert r.status_code == 200

    r = as_admin.get(f"/api/attendance/today/{sample_student.grade_level}")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["student_id"] == sample_student.id)
    assert row["is_present"] is True

    # Marking again the same day updates instead of duplicating
    r = as_admin.post("/api/attendance/bulk", json=[
        {"student_id": sample_student.id, "is_present": False, "remarks": "Sick"}])
    assert r.status_code == 200

    r = as_admin.get(f"/api/attendance/today/{sample_student.grade_level}")
    row = next(x for x in r.json() if x["student_id"] == sample_student.id)
    assert row["is_present"] is False
    assert row["remarks"] == "Sick"


def test_bulk_mark_unknown_student_404(as_admin):
    r = as_admin.post("/api/attendance/bulk", json=[
        {"student_id": 12345, "is_present": True, "remarks": None}])
    assert r.status_code == 404


def test_student_attendance_history(as_admin, sample_student):
    as_admin.post("/api/attendance/bulk", json=[
        {"student_id": sample_student.id, "is_present": True, "remarks": None}])

    r = as_admin.get(f"/api/attendance/student/{sample_student.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["total_days"] == 1
    assert body["days_present"] == 1
    assert body["attendance_percentage"] == 100
    assert len(body["records"]) == 1


def test_attendance_summary_by_grade(as_admin, sample_student):
    as_admin.post("/api/attendance/bulk", json=[
        {"student_id": sample_student.id, "is_present": False, "remarks": None}])

    r = as_admin.get("/api/attendance/summary")
    assert r.status_code == 200
    grade_row = next(x for x in r.json() if x["grade"] == sample_student.grade_level)
    assert grade_row["total_records"] == 1
    assert grade_row["present"] == 0
    assert grade_row["percentage"] == 0
