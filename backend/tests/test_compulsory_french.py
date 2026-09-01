"""French is compulsory for every student from Grade 1 through Grade 6:
auto-subscribed on admission (single + bulk), on promotion into Grade 1, and
it can't be unsubscribed. Play Group/PP1/PP2 are unaffected."""
from datetime import datetime
import models
from activities import ensure_compulsory_enrollment
from constants import COMPULSORY_ACTIVITY_NAME


def _french_enrollment(db_session, student_id, year):
    return db_session.query(models.ActivityEnrollment).filter(
        models.ActivityEnrollment.student_id == student_id,
        models.ActivityEnrollment.activity_name == COMPULSORY_ACTIVITY_NAME,
        models.ActivityEnrollment.academic_year == year,
    ).first()


def test_new_grade1_admission_is_auto_enrolled_in_french(as_admin, db_session):
    r = as_admin.post("/api/students/", json={
        "first_name": "Amani", "last_name": "Otieno",
        "grade_level": "Grade 1", "status": "Active",
    })
    assert r.status_code == 200
    student_id = r.json()["id"]
    year = datetime.now().year

    enrollment = _french_enrollment(db_session, student_id, year)
    assert enrollment is not None
    assert enrollment.is_active is True


def test_playgroup_admission_is_not_enrolled_in_french(as_admin, db_session):
    r = as_admin.post("/api/students/", json={
        "first_name": "Baby", "last_name": "Wanjiru",
        "grade_level": "Play Group", "status": "Active",
    })
    student_id = r.json()["id"]
    assert _french_enrollment(db_session, student_id, datetime.now().year) is None


def test_bulk_import_grade3_auto_enrolls_french(as_admin, db_session):
    r = as_admin.post("/api/students/bulk", json=[{
        "first_name": "Bulk", "last_name": "Kid",
        "grade_level": "Grade 3", "status": "Active",
    }])
    assert r.status_code == 201
    student = db_session.query(models.Student).filter(models.Student.last_name == "Kid").first()
    assert _french_enrollment(db_session, student.id, datetime.now().year) is not None


def test_cannot_unsubscribe_french(as_admin, db_session):
    r = as_admin.post("/api/students/", json={
        "first_name": "Cannot", "last_name": "Drop",
        "grade_level": "Grade 2", "status": "Active",
    })
    student_id = r.json()["id"]
    enrollment = _french_enrollment(db_session, student_id, datetime.now().year)

    r = as_admin.delete(f"/api/activities/enrollments/{enrollment.id}")
    assert r.status_code == 400
    assert "compulsory" in r.json()["detail"].lower()

    db_session.refresh(enrollment)
    assert enrollment.is_active is True


def test_ensure_compulsory_enrollment_is_idempotent(db_session, sample_student):
    """sample_student is Grade 1 but created directly (bypassing the create_
    student endpoint), so starts with no French enrollment — the same
    helper used on promotion must handle both 'first time' and 'already
    enrolled' cases cleanly."""
    year = datetime.now().year
    assert ensure_compulsory_enrollment(db_session, sample_student, year, "Term 1", "system") is True
    db_session.commit()
    # Second call: already enrolled, must not create a duplicate row.
    assert ensure_compulsory_enrollment(db_session, sample_student, year, "Term 1", "system") is False
    db_session.commit()

    count = db_session.query(models.ActivityEnrollment).filter(
        models.ActivityEnrollment.student_id == sample_student.id,
        models.ActivityEnrollment.activity_name == COMPULSORY_ACTIVITY_NAME,
        models.ActivityEnrollment.academic_year == year,
    ).count()
    assert count == 1


def test_ensure_compulsory_enrollment_reactivates_a_dropped_row(db_session, sample_student):
    """If a French enrollment somehow ended up inactive (e.g. legacy data
    from before this rule existed), re-running the helper must reactivate it
    rather than leaving a compulsory subject silently unsubscribed."""
    year = datetime.now().year
    ensure_compulsory_enrollment(db_session, sample_student, year, "Term 1", "system")
    db_session.commit()
    row = db_session.query(models.ActivityEnrollment).filter(
        models.ActivityEnrollment.student_id == sample_student.id,
        models.ActivityEnrollment.activity_name == COMPULSORY_ACTIVITY_NAME,
    ).first()
    row.is_active = False
    db_session.commit()

    ensure_compulsory_enrollment(db_session, sample_student, year, "Term 1", "system")
    db_session.commit()
    db_session.refresh(row)
    assert row.is_active is True
