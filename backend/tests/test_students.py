import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from passlib.context import CryptContext

import main
from main import app
from database import get_db, Base
import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
main.engine = engine

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Create tables once for the shared memory db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_db():
    # Clean data before each test
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers(client):
    db = TestingSessionLocal()
    user = models.User(
        username="admin",
        hashed_password=pwd_context.hash("password"),
        name="Admin User",
        role="admin",
        can_login=True
    )
    db.add(user)
    db.commit()
    db.close()

    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "password"}
    )
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_student_success(client, auth_headers):
    student_data = {
        "first_name": "John",
        "last_name": "Doe",
        "grade_level": "Grade 1",
        "status": "Active"
    }
    response = client.post("/api/students/", json=student_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["grade_level"] == "Grade 1"
    assert "admission_number" in data

    # Verify in db
    db = TestingSessionLocal()
    student_db = db.query(models.Student).filter_by(first_name="John").first()
    assert student_db is not None
    assert student_db.last_name == "Doe"
    assert student_db.admission_number == data["admission_number"]
    db.close()

def test_create_student_unauthorized_role(client):
    db = TestingSessionLocal()
    user = models.User(
        username="teacher",
        hashed_password=pwd_context.hash("password"),
        name="Teacher User",
        role="teacher",
        can_login=True
    )
    db.add(user)
    db.commit()
    db.close()

    response = client.post(
        "/api/auth/login",
        data={"username": "teacher", "password": "password"}
    )
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    student_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "grade_level": "Grade 2"
    }
    response = client.post("/api/students/", json=student_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to admit students"

def test_create_student_duplicate_admission_number(client, auth_headers):
    # First student
    student_data_1 = {
        "first_name": "Alice",
        "last_name": "Johnson",
        "grade_level": "Grade 3",
        "admission_number": "BONA-1234"
    }
    response_1 = client.post("/api/students/", json=student_data_1, headers=auth_headers)
    assert response_1.status_code == 200

    # Second student with same admission number
    student_data_2 = {
        "first_name": "Bob",
        "last_name": "Williams",
        "grade_level": "Grade 4",
        "admission_number": "BONA-1234"
    }
    response_2 = client.post("/api/students/", json=student_data_2, headers=auth_headers)
    assert response_2.status_code == 400
    assert response_2.json()["detail"] == "Admission number already registered"

def test_create_student_auto_generate_admission_number(client, auth_headers):
    student_data_1 = {
        "first_name": "Charlie",
        "last_name": "Brown",
        "grade_level": "Grade 1"
    }
    response_1 = client.post("/api/students/", json=student_data_1, headers=auth_headers)
    assert response_1.status_code == 200
    admn_1 = response_1.json()["admission_number"]
    assert admn_1.startswith("BONA-")

    student_data_2 = {
        "first_name": "Diana",
        "last_name": "Prince",
        "grade_level": "Grade 2"
    }
    response_2 = client.post("/api/students/", json=student_data_2, headers=auth_headers)
    assert response_2.status_code == 200
    admn_2 = response_2.json()["admission_number"]
    assert admn_2.startswith("BONA-")
    assert admn_1 != admn_2
