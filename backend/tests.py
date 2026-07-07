from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine
import pytest

# Create the test client
client = TestClient(app)

def setup_module(module):
    """ setup any state specific to the execution of the given module."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to School API"}

def test_create_teacher():
    response = client.post(
        "/teachers/",
        json={"name": "Test Teacher", "department": "Math"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Teacher"
    assert data["department"] == "Math"
    assert "id" in data

def test_create_student():
    response = client.post(
        "/students/",
        json={"name": "Test Student", "email": "test@student.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Student"
    assert data["email"] == "test@student.com"
    assert "id" in data
