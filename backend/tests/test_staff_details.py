"""Staff records carry ID, contact, next-of-kin and bank details."""

DETAILS = {
    "national_id": "12345678",
    "phone": "+254700111222",
    "email": "j.otieno@bona.ac.ke",
    "address": "Kisumu",
    "next_of_kin_name": "Mary Otieno",
    "next_of_kin_phone": "+254700333444",
    "next_of_kin_relationship": "Spouse",
    "bank_name": "KCB",
    "bank_account": "1234567890",
}


def test_staff_created_with_full_details(as_admin):
    r = as_admin.post("/api/staff/", json={
        "username": "detailed_teacher", "name": "John Otieno",
        "role": "teacher", **DETAILS})
    assert r.status_code == 200
    body = r.json()
    for key, value in DETAILS.items():
        assert body[key] == value, key

    # Listed with the same details
    r = as_admin.get("/api/staff/")
    row = next(s for s in r.json() if s["name"] == "John Otieno")
    assert row["national_id"] == DETAILS["national_id"]
    assert row["next_of_kin_phone"] == DETAILS["next_of_kin_phone"]


def test_staff_details_updatable(as_admin, db_session):
    r = as_admin.post("/api/staff/", json={
        "username": "updatable_teacher", "name": "Grace Akinyi", "role": "teacher"})
    staff_id = r.json()["id"]

    r = as_admin.put(f"/api/staff/{staff_id}", json={
        "phone": "+254711999888", "next_of_kin_name": "Peter Akinyi"})
    assert r.status_code == 200
    assert r.json()["phone"] == "+254711999888"
    assert r.json()["next_of_kin_name"] == "Peter Akinyi"
