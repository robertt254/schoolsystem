"""Tests for the admin reset endpoint's guard rails.

The actual TRUNCATE path uses PostgreSQL's information_schema and cannot run on
the SQLite test database; the authorisation and confirmation guards are the
security-relevant part and are covered here.
"""


def test_reset_requires_system_admin(as_accountant):
    r = as_accountant.post("/api/admin/reset-data", json={"confirm": "RESET"})
    assert r.status_code == 403


def test_reset_requires_confirmation_text(as_admin):
    r = as_admin.post("/api/admin/reset-data", json={"confirm": "yes please"})
    assert r.status_code == 400
    assert "RESET" in r.json()["detail"]
