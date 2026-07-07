import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

from backend.main import app
from backend.database import Base, get_db
from backend.auth import get_password_hash
from backend.models import User, Role

# Setup test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_school.db"
engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(autouse=True)
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # create admin user for tests
        db_user = User(username="admin", hashed_password=get_password_hash("password"), role=Role.ADMIN)
        session.add(db_user)
        await session.commit()
        yield session

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_read_main(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to CBC School API"}

@pytest.mark.asyncio
async def test_auth_and_create_teacher(client: AsyncClient):
    # 1. Login to get token
    login_response = await client.post(
        "/token",
        data={"username": "admin", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # 2. Use token to create teacher
    response = await client.post(
        "/teachers/",
        json={"name": "Test Teacher", "department": "Math"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Teacher"
    assert data["department"] == "Math"

@pytest.mark.asyncio
async def test_auth_and_create_student(client: AsyncClient):
    login_response = await client.post(
        "/token",
        data={"username": "admin", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/students/",
        json={
            "admission_number": "ADM-123",
            "name": "Test Student",
            "grade": "Grade 1",
            "guardian_contact": "0700000000"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Student"
    assert data["admission_number"] == "ADM-123"
