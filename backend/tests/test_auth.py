"""Tests for authentication endpoints and JWT flow."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.api.deps import get_db
from app.auth.passwords import hash_password
from app.auth.jwt import create_access_token, decode_access_token
from app.models.user import User
from tests.conftest import _override_db, TestSession


# ── JWT utility tests ─────────────────────────────────────────────────────────

class TestJWTUtils:
    def test_create_and_decode_access_token(self):
        token = create_access_token(1, "user@thearq.com", "admin")
        claims = decode_access_token(token)
        assert claims["sub"] == "1"
        assert claims["email"] == "user@thearq.com"
        assert claims["role"] == "admin"
        assert claims["type"] == "access"

    def test_decode_invalid_token_raises(self):
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_access_token("invalid.token.here")


# ── Login endpoint tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self):
        async with TestSession() as session:
            # Create a test user directly in DB
            user = User(
                email="logintest@thearq.com",
                password_hash=hash_password("MyPass123!"),
                full_name="Login Test",
                role="analyst",
            )
            session.add(user)
            await session.flush()

            app.dependency_overrides[get_db] = _override_db(session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "logintest@thearq.com",
                    "password": "MyPass123!",
                })
            app.dependency_overrides.clear()

            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert data["user"]["email"] == "logintest@thearq.com"
            assert data["user"]["role"] == "analyst"
            assert "analyst:investigate" in data["user"]["permissions"]

    async def test_login_wrong_password(self):
        async with TestSession() as session:
            user = User(
                email="wrongpw@thearq.com",
                password_hash=hash_password("Correct123!"),
                full_name="Wrong PW",
                role="viewer",
            )
            session.add(user)
            await session.flush()

            app.dependency_overrides[get_db] = _override_db(session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "wrongpw@thearq.com",
                    "password": "Wrong123!",
                })
            app.dependency_overrides.clear()

            assert resp.status_code == 401

    async def test_login_nonexistent_user(self):
        async with TestSession() as session:
            app.dependency_overrides[get_db] = _override_db(session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "nobody@thearq.com",
                    "password": "Whatever123!",
                })
            app.dependency_overrides.clear()

            assert resp.status_code == 401


# ── Auth enforcement tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAuthEnforcement:
    async def test_unauthenticated_request_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/dashboard/overview")
        assert resp.status_code == 401

    async def test_health_endpoint_is_exempt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_invalid_token_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test",
                               headers={"Authorization": "Bearer garbage"}) as client:
            resp = await client.get("/api/dashboard/overview")
        assert resp.status_code == 401


# ── Permission enforcement tests ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestPermissions:
    async def test_viewer_cannot_manage_cases(self, viewer_client: AsyncClient):
        resp = await viewer_client.put("/api/cases/CASE-FAKE/status",
                                       json={"status": "resolved"})
        assert resp.status_code == 403

    async def test_viewer_cannot_run_pipeline(self, viewer_client: AsyncClient):
        resp = await viewer_client.post("/api/pipeline/run-full", json={"limit": 10})
        assert resp.status_code == 403

    async def test_viewer_cannot_admin_users(self, viewer_client: AsyncClient):
        resp = await viewer_client.get("/api/admin/users")
        assert resp.status_code == 403

    async def test_admin_can_read_dashboard(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/dashboard/overview")
        # May return 200 or 500 (if no data), but NOT 401/403
        assert resp.status_code not in (401, 403)
