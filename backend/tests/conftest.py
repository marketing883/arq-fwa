"""Shared test fixtures for backend tests."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.config import settings
from app.main import app
from app.api.deps import get_db, get_request_context
from app.auth.context import RequestContext
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password
from app.models.user import User


# Use the same database but with a test-scoped session
engine = create_async_engine(settings.database_url, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test DB session that rolls back after each test."""
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def seed_test_user(db_session: AsyncSession) -> User:
    """Create a test admin user for auth tests."""
    user = User(
        email="test-admin@thearq.com",
        password_hash=hash_password("TestPass123!"),
        full_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _make_auth_header(user_id: int, email: str, role: str) -> dict:
    """Create an Authorization header with a valid JWT."""
    token = create_access_token(user_id, email, role)
    return {"Authorization": f"Bearer {token}"}


def _override_db(session: AsyncSession):
    """Create a dependency override for get_db."""
    async def _get_db():
        yield session
    return _get_db


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession, seed_test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client authenticated as admin."""
    app.dependency_overrides[get_db] = _override_db(db_session)
    headers = _make_auth_header(seed_test_user.id, seed_test_user.email, "admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def viewer_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client authenticated as viewer (limited permissions)."""
    app.dependency_overrides[get_db] = _override_db(db_session)
    headers = _make_auth_header(999, "viewer@thearq.com", "viewer")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with no authentication."""
    app.dependency_overrides[get_db] = _override_db(db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
