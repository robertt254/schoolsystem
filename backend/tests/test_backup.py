"""Backups: admin-only access, snapshot round-trip, and traversal protection."""
import json


def test_backups_restricted_to_system_admin(as_accountant):
    assert as_accountant.get("/api/admin/backups/").status_code == 403
    assert as_accountant.post("/api/admin/backups/").status_code == 403


def test_create_list_download_roundtrip(as_admin, sample_student):
    # Create a snapshot
    r = as_admin.post("/api/admin/backups/")
    assert r.status_code == 201
    filename = r.json()["filename"]
    assert filename.startswith("bns_backup_") and filename.endswith(".json")
    assert r.json()["size_bytes"] > 0

    # It appears in the listing
    r = as_admin.get("/api/admin/backups/")
    assert r.status_code == 200
    assert any(b["filename"] == filename for b in r.json())

    # Download and verify the snapshot contains the data
    r = as_admin.get(f"/api/admin/backups/{filename}")
    assert r.status_code == 200
    snapshot = json.loads(r.content)
    assert snapshot["format"] == 1
    assert "users" in snapshot["tables"]
    students = snapshot["tables"]["students"]
    assert any(s["admission_number"] == sample_student.admission_number for s in students)


def test_download_rejects_non_backup_filenames(as_admin):
    # Not matching the strict backup-name pattern → 404, no path traversal
    assert as_admin.get("/api/admin/backups/evil.json").status_code == 404
    assert as_admin.get("/api/admin/backups/..%2Fmain.py").status_code == 404
