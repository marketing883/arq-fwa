# Plan: Phase 1 (Auth & Security) + Phase 2 (Testing & Quality)

## Phase 1A: JWT Authentication

### New files

1. **`backend/app/models/user.py`** — User model
   - Fields: `id`, `email` (unique, indexed), `password_hash`, `full_name`, `role` (enum), `is_active`, `created_at`, `updated_at`
   - bcrypt password hashing via `passlib[bcrypt]`

2. **`backend/alembic/versions/..._add_users_table.py`** — Migration
   - Create `users` table
   - Seed 5 demo users (admin, compliance, investigator, analyst, viewer) with bcrypt-hashed default passwords

3. **`backend/app/api/auth.py`** — Auth router
   - `POST /api/auth/login` — email + password → JWT access token (30min) + refresh token (7d, stored in httpOnly cookie)
   - `POST /api/auth/refresh` — refresh token → new access token
   - `POST /api/auth/logout` — revoke refresh token (delete from Redis)
   - `GET /api/auth/me` — return current user profile (id, email, name, role, permissions)
   - `PUT /api/auth/me/password` — change own password (requires current password)

4. **`backend/app/api/admin_users.py`** — Admin user management router
   - `GET /api/admin/users` — list all users (ADMIN only)
   - `POST /api/admin/users` — create user (ADMIN only)
   - `PUT /api/admin/users/{id}` — update role/active status (ADMIN only)
   - `POST /api/admin/users/{id}/reset-password` — generate temp password (ADMIN only)

5. **`backend/app/auth/jwt.py`** — JWT utilities
   - `create_access_token(user_id, role)` → signed JWT (HS256, 30min exp)
   - `create_refresh_token(user_id)` → opaque token stored in Redis with 7d TTL
   - `decode_access_token(token)` → claims dict or raise 401
   - Uses `settings.secret_key` as signing key

### Modified files

6. **`backend/app/api/deps.py`** — THE key change
   - `get_request_context()` now:
     1. Reads `Authorization: Bearer <token>` header
     2. Decodes JWT → extracts user_id, role
     3. Looks up permissions via existing `ROLE_PERMISSIONS[role]`
     4. Resolves workspace_id from header/param (existing logic)
     5. Returns properly scoped `RequestContext`
   - Auth-exempt paths: `/api/auth/login`, `/api/auth/refresh`, `/api/health`, `/metrics`

7. **`backend/app/config.py`** — Add JWT settings
   - `access_token_expire_minutes: int = 30`
   - `refresh_token_expire_days: int = 7`

8. **`backend/app/main.py`** — Register new routers
   - Add `auth_router` and `admin_users_router`

9. **`backend/pyproject.toml`** — Add dependencies
   - `passlib[bcrypt]>=1.7.4`
   - `python-jose[cryptography]>=3.3.0`

### Frontend changes

10. **`frontend/src/app/login/page.tsx`** — Login page
    - Email + password form
    - Calls `POST /api/auth/login`
    - Stores access token in memory (not localStorage — XSS safe)
    - Stores refresh token via httpOnly cookie (set by backend)

11. **`frontend/src/lib/auth.ts`** — Auth context/provider
    - `AuthProvider` wrapping the app — holds current user, token, permissions
    - `useAuth()` hook — exposes `user`, `login()`, `logout()`, `isAuthenticated`
    - Auto-refresh: intercepts 401 responses → calls `/api/auth/refresh` → retries

12. **`frontend/src/lib/api-client.ts`** — Update fetch wrapper
    - Inject `Authorization: Bearer <token>` on every request
    - Handle 401 → refresh → retry flow
    - Handle 403 → show "insufficient permissions" toast

13. **`frontend/src/app/layout.tsx`** — Wrap app in `AuthProvider`
    - Redirect unauthenticated users to `/login`
    - Show current user/role in header

14. **`frontend/src/components/ui/ProtectedRoute.tsx`** — Route guard component
    - Checks `useAuth()` for required role/permission
    - Renders children or redirects to login

---

## Phase 1B: Security Hardening

### Modified files

15. **`backend/app/config.py`** — Production safety
    - DB connection pool: `pool_size=20, max_overflow=10, pool_pre_ping=True`
    - Statement timeout: `connect_args={"command_timeout": 30}`

16. **`backend/app/database.py`** — Apply pool settings from config

17. **`backend/Dockerfile`** — Add non-root user
    - `RUN adduser --disabled-password appuser`
    - `USER appuser`

18. **`docker-compose.yml`** — Resource limits
    - Add `mem_limit` and `cpus` per service
    - Remove hardcoded passwords from defaults (require .env file)

---

## Phase 2A: Backend Tests

### New files

19. **`backend/tests/conftest.py`** — Shared fixtures
    - In-memory SQLite or test PostgreSQL session
    - Authenticated test client (per-role fixtures)
    - Factory functions for claims, cases, providers, members

20. **`backend/tests/test_auth.py`** — Auth endpoint tests
    - Login success/failure, refresh, logout
    - Token expiry handling
    - Permission enforcement (viewer can't manage cases, etc.)

21. **`backend/tests/test_claims_api.py`** — Claims API tests
    - Pagination, filtering, workspace scoping
    - 404 on nonexistent claim
    - Permission checks per role

22. **`backend/tests/test_cases_api.py`** — Cases API tests
    - Status transitions (valid + invalid)
    - Assignment, notes
    - Workspace isolation

23. **`backend/tests/test_agent_chat.py`** — Chat workspace scoping tests
    - Verify workspace filtering on all tool methods
    - Verify data-driven fallbacks respect workspace
    - Mock Ollama responses

24. **`backend/tests/test_pipeline_api.py`** — Pipeline tests
    - Run pipeline scoped to workspace
    - Verify scores/cases created in correct workspace

25. **`backend/tests/test_workspaces_api.py`** — Workspace CRUD + upload tests

26. **`backend/pytest.ini`** or update `pyproject.toml` — pytest config
    - `asyncio_mode = auto`
    - `testpaths = ["tests"]`

---

## Phase 2B: Frontend Tests

### New files

27. **`frontend/jest.config.ts`** or **`frontend/vitest.config.ts`** — Test framework config

28. **`frontend/src/__tests__/login.test.tsx`** — Login page tests
    - Renders form, submits credentials, handles errors

29. **`frontend/src/__tests__/dashboard.test.tsx`** — Dashboard tests
    - Renders with mock data, handles loading/error states

30. **`frontend/src/__tests__/auth-provider.test.tsx`** — Auth context tests
    - Token refresh, logout, permission checks

---

## Phase 2C: CI Pipeline

### New files

31. **`.github/workflows/ci.yml`** — GitHub Actions
    - **Lint**: ruff (Python), eslint (TS)
    - **Type check**: pyright (Python), tsc --noEmit (TS)
    - **Test**: pytest (backend), vitest/jest (frontend)
    - **Security**: pip-audit, npm audit
    - **Build**: docker compose build

---

## Execution Order

1. User model + migration + seed users
2. JWT utilities (create/decode tokens)
3. Auth router (login/refresh/logout/me)
4. Update deps.py (THE switch — auth goes live)
5. Admin user management router
6. Frontend login page + auth provider + API client
7. Security hardening (pool, Dockerfile, compose)
8. Backend tests
9. Frontend tests
10. CI pipeline

## What Does NOT Change
- Existing RBAC framework (roles.py, permissions.py, context.py) — used as-is
- Existing `require()` guards on all endpoints — already wired
- Existing workspace scoping — already working
- Existing API contracts — no breaking changes
