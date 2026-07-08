import pytest
from auth import verify_password
import models

def test_change_password_success(client, test_user, db_session):
    # First login to get a token
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "old_password"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Now change password
    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "old_password",
            "new_password": "new_strong_password"
        }
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully"}

    # Verify in DB
    db_session.refresh(test_user)
    assert verify_password("new_strong_password", test_user.hashed_password)

    # Verify can login with new password
    new_login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "new_strong_password"}
    )
    assert new_login_response.status_code == 200

def test_change_password_incorrect_current_password(client, test_user):
    # First login to get a token
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "old_password"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Attempt to change password with wrong current password
    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "wrong_password",
            "new_password": "new_strong_password"
        }
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is incorrect"}

def test_change_password_unauthenticated(client):
    # Attempt to change password without a token
    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "old_password",
            "new_password": "new_strong_password"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
