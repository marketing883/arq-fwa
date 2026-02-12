# Enterprise Readiness Implementation Plan

## Execution Order
1. **Workstream 2** — Security & HIPAA Compliance
2. **Workstream 4** — Observability & Monitoring
3. **Workstream 5** — Pipeline Robustness
4. **Workstream 7** — AI Agent Intelligence

---

## Workstream 2: Security & HIPAA Compliance

### 2A. Environment-Aware Config Validation
**File:** `backend/app/config.py`

- Add a `@model_validator` that **refuses to start** in `environment=production` if `secret_key` is the default dev value or if `database_url` contains `arqai_dev_password`
- Add `allowed_origins: str = "http://localhost:3000"` (comma-separated, parsed to list) — no more hardcoded list in `main.py`
- Add `rate_limit_per_minute: int = 60` config
- Add `encryption_key: str = ""` for PII encryption (required in production)

### 2B. Redis-Backed Rate Limiting Middleware
**New file:** `backend/app/middleware/rate_limit.py`

- Uses the **existing Redis** service (configured, dependency installed, currently unused)
- Sliding window algorithm: track request counts per IP per minute in Redis
- Configurable via `settings.rate_limit_per_minute` (default 60)
- Returns `429 Too Many Requests` with `Retry-After` header when exceeded
- Exempt health check and metrics endpoints
- Register in `main.py` as ASGI middleware

### 2C. Security Headers Middleware
**New file:** `backend/app/middleware/security_headers.py`

- Adds headers to every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- Also update **nginx/nginx.conf** to add:
  - `Strict-Transport-Security` (HSTS)
  - `Content-Security-Policy` (CSP) header

### 2D. PII Field Encryption
**New file:** `backend/app/services/encryption_service.py`

- AES-256-GCM encryption using `cryptography` library (new dep)
- Encrypt/decrypt helper functions keyed by `settings.encryption_key`
- Apply to sensitive Member fields at write time: `first_name`, `last_name`, `date_of_birth`
- Decrypt transparently on read via a service layer
- Graceful handling: if `encryption_key` is empty (dev mode), store plaintext with a logged warning

### 2E. CSV Upload Sanitization
**File:** `backend/app/services/upload_service.py`

- Add file size validation (configurable max, e.g., 50MB)
- Validate CSV structure before processing: max column count, max row count, no binary content
- Strip/escape special characters in string fields to prevent injection
- Reject files with embedded formulas (=, +, -, @ at cell start — CSV injection prevention)

### 2F. CORS Tightening
**File:** `backend/app/main.py`

- Read allowed origins from `settings.allowed_origins` instead of hardcoded list
- In production: restrict to actual deployment domain only
- Remove `allow_methods=["*"]` — list only GET, POST, PUT, PATCH, DELETE
- Remove `allow_headers=["*"]` — list only Content-Type, Authorization, X-Request-ID

### New dependencies:
- `cryptography>=43.0.0` (for AES encryption)

---

## Workstream 4: Observability & Monitoring

### 4A. Structured JSON Logging
**New file:** `backend/app/middleware/logging_config.py`

- Replace text formatter with JSON structured logging
- Every log line includes: `timestamp`, `level`, `logger`, `message`, `request_id`, `duration_ms`
- Configure in `main.py` lifespan, driven by `settings.log_level`
- Use Python's `logging.Formatter` subclass for JSON output

### 4B. Request Context Middleware
**New file:** `backend/app/middleware/request_context.py`

- Generate or propagate `X-Request-ID` header (UUID4 if not provided)
- Store in `contextvars.ContextVar` so all downstream code (services, DB queries, logs) can access it
- Add `request_id` to every log line automatically via the JSON formatter
- Add response timing: capture start time, compute `duration_ms`, log on response
- Return `X-Request-ID` in response headers for client-side correlation

### 4C. Prometheus Metrics
**New file:** `backend/app/middleware/metrics.py`
**New endpoint in:** `backend/app/api/metrics.py`

- Use `prometheus_client` library (new dep)
- Collect metrics:
  - `http_requests_total` — Counter by method, path, status_code
  - `http_request_duration_seconds` — Histogram by method, path
  - `pipeline_runs_total` — Counter by workspace, status (success/error)
  - `pipeline_duration_seconds` — Histogram
  - `pipeline_claims_processed` — Counter
  - `agent_chat_requests_total` — Counter by model_used
  - `agent_chat_duration_seconds` — Histogram
  - `active_cases_by_risk_level` — Gauge (updated periodically)
- Expose `GET /metrics` endpoint (Prometheus text format)

### 4D. Expanded Health Checks
**File:** `backend/app/main.py` (existing `/api/health`)

- Expand to check:
  - **Database**: Attempt `SELECT 1` — report connected/disconnected
  - **Redis**: Attempt `PING` — report connected/disconnected
  - **Ollama**: Check model availability — report ready/loading/unavailable
- Return overall status: `healthy` (all up), `degraded` (some down), `unhealthy` (DB down)
- Include component details in response body
- Keep the endpoint lightweight (cache component checks for 10s)

### New dependencies:
- `prometheus-client>=0.21.0`

---

## Workstream 5: Pipeline Robustness

### 5A. Async Job Queue (ARQ + Redis)
**New file:** `backend/app/services/job_queue.py`

- Use **ARQ** library (async Redis queue, natively async, lightweight)
- Define pipeline as an ARQ task function
- Expose new endpoint: `POST /api/pipeline/enqueue` — returns `job_id` immediately
- Expose new endpoint: `GET /api/pipeline/jobs/{job_id}` — returns job status, progress, result
- Store job progress in Redis hash: `pipeline:job:{job_id}` → `{status, phase, progress, claims_processed, errors, started_at, completed_at}`
- Worker runs as a separate process (new entrypoint `worker.py`)
- Keep existing `/run-full` and `/run-stream` endpoints for backward compatibility
- Add `worker` service to `docker-compose.yml` (same image, different command)

### 5B. Incremental Processing
**File:** `backend/app/api/pipeline.py` + services

- Pipeline only picks up claims where `status != 'processed'` (already partially implemented)
- Add `force_reprocess: bool = False` parameter to pipeline endpoints — when true, reprocesses all claims
- Track `last_pipeline_run` timestamp per workspace in the Workspace model
- On upload of new data, auto-mark workspace as needing reprocessing

### 5C. Data Quality Gates
**New file:** `backend/app/services/data_quality.py`

- Pre-enrichment validation phase inserted at the start of the pipeline:
  - **Duplicate detection**: Flag claims with identical (provider, member, service_date, cpt_code) or (member, fill_date, ndc_code)
  - **Schema conformance**: Validate required fields are non-null, dates are valid, amounts are positive
  - **Outlier detection**: Flag claims where `amount_billed` > 3 standard deviations from mean for that CPT/NDC
  - **Referential integrity**: Verify provider_id and member_id exist in reference tables
- Returns a quality report: `{total_claims, passed, failed, issues: [{claim_id, issue_type, detail}]}`
- Pipeline can be configured to: `skip_invalid` (default), `halt_on_errors`, or `flag_only`
- Quality report stored and returned in pipeline results

### 5D. Pipeline Run Versioning
**New model:** `PipelineRun` table

- Fields: `run_id` (UUID), `workspace_id`, `batch_id`, `started_at`, `completed_at`, `status`, `config_snapshot` (JSONB — captures rule weights, thresholds, scoring config at time of run), `stats` (JSONB — claims processed, cases created, etc.), `quality_report` (JSONB)
- Every pipeline execution creates a PipelineRun record
- Enables: "What rules/thresholds were in effect when this claim was scored?"
- New endpoint: `GET /api/pipeline/runs` — list past runs with stats
- New endpoint: `GET /api/pipeline/runs/{run_id}` — detail with config snapshot

### New dependencies:
- `arq>=0.26.0` (async Redis job queue)

### New migration:
- Add `pipeline_runs` table

---

## Workstream 7: AI Agent Intelligence

### 7A. Conversation Memory (DB-Backed Sessions)
**New model:** `ChatSession` and `ChatMessage` tables

- `ChatSession`: `session_id` (UUID), `workspace_id`, `created_at`, `updated_at`, `title` (auto-generated from first message), `case_id` (optional — pins session to a case)
- `ChatMessage`: `id`, `session_id` (FK), `role` (user/assistant), `content`, `sources_cited` (JSONB), `model_used`, `created_at`
- New endpoints:
  - `POST /api/agents/sessions` — create new session
  - `GET /api/agents/sessions` — list sessions (by workspace)
  - `GET /api/agents/sessions/{session_id}` — get session with messages
  - `DELETE /api/agents/sessions/{session_id}` — delete session
- Modify `POST /api/agents/chat` to accept `session_id` — if provided, loads last N messages as conversation history and includes them in the LLM prompt
- LLM receives conversation history as alternating user/assistant messages (standard chat format)
- Cap history at last 20 messages to stay within context window
- Frontend: sidebar with session list, create new chat, switch between sessions

### 7B. Tool-Use Pattern (Function Calling)
**File:** `backend/app/services/agent_service.py`

- Instead of only pre-querying everything, define **tools** the LLM can call:
  - `query_pipeline_stats()` — returns claim counts, case counts, risk breakdown
  - `query_cases(risk_level?, status?, limit?)` — search/filter investigation cases
  - `query_case_detail(case_id)` — full case context
  - `query_rules(triggered_only?, limit?)` — rule stats
  - `query_provider(npi?)` — provider lookup
  - `run_pipeline(workspace_id)` — trigger pipeline execution
- Implement a **ReAct loop**:
  1. Send user message + tool definitions to LLM
  2. If LLM responds with a tool call → execute it, append result, re-call LLM
  3. If LLM responds with text → return to user
  4. Max 5 iterations to prevent infinite loops
- For Ollama models that don't support native function calling: use a prompt-based tool-use format (describe tools in system prompt, parse structured output)
- Keep the existing RAG approach as a fast-path: if the question clearly matches a known pattern (stats, top risk, etc.), pre-fetch data without waiting for tool calls

### 7C. Streaming Chat Responses
**File:** `backend/app/api/agents.py` + `backend/app/services/agent_service.py`

- New endpoint: `POST /api/agents/chat/stream` — returns Server-Sent Events
- Modify `_call_ollama` to support `stream=True` — Ollama returns token-by-token
- Stream tokens to client as SSE events: `data: {"token": "The", "done": false}`
- Final event includes full response, sources, model: `data: {"done": true, "response": "...", "sources_cited": [...]}`
- Frontend: `EventSource` or `fetch` with ReadableStream to consume SSE and render tokens incrementally

### 7D. Workspace-Scoped Guardrails
**File:** `backend/app/services/agent_service.py`

- **All database queries in `_gather_data_context` and `_gather_case_context` filter by workspace_id** (passed through from the chat request)
- Add `workspace_id` parameter to `chat()` and `investigate_case()` methods
- Validate that the requested `case_id` belongs to the active workspace
- System prompt includes: "You are scoped to workspace {workspace_name}. Only reference data from this workspace."
- Post-processing: scan LLM output for case IDs that don't belong to the workspace (defense-in-depth)

### 7E. Citation Linking
**File:** `backend/app/services/agent_service.py`

- When the LLM references a case ID (e.g., `CASE-001234`), wrap it in a markdown link: `[CASE-001234](/cases/CASE-001234)`
- Similarly for rule IDs: `[RULE-MED-001](/rules/RULE-MED-001)`
- Post-process the LLM response with regex to find and linkify known entity patterns
- Frontend already renders markdown via `react-markdown`, so links will be clickable

### 7F. Confidence Indicator on Chat
**File:** `backend/app/services/agent_service.py` + API schema

- Add `confidence: str` field to ChatResponse: `"high"` (answer from DB data), `"medium"` (LLM with data context), `"low"` (LLM without data / fallback)
- Determined by: which sources were used, whether LLM had data context, whether it's a fallback response
- Frontend shows a subtle indicator: green dot (high), yellow (medium), orange (low)

### New migration:
- Add `chat_sessions` and `chat_messages` tables

### Frontend changes:
- Chat sidebar: session list, create new, switch sessions
- Streaming message rendering (token-by-token appearance)
- Confidence indicator on each message
- Clickable entity links in responses

---

## File Change Summary

### New files:
| File | Workstream | Purpose |
|------|-----------|---------|
| `backend/app/middleware/__init__.py` | 2 | Package init |
| `backend/app/middleware/rate_limit.py` | 2 | Redis rate limiting |
| `backend/app/middleware/security_headers.py` | 2 | Security response headers |
| `backend/app/services/encryption_service.py` | 2 | PII AES-256 encryption |
| `backend/app/middleware/logging_config.py` | 4 | JSON structured logging |
| `backend/app/middleware/request_context.py` | 4 | Request ID + timing |
| `backend/app/middleware/metrics.py` | 4 | Prometheus collection |
| `backend/app/api/metrics.py` | 4 | /metrics endpoint |
| `backend/app/services/job_queue.py` | 5 | ARQ job queue |
| `backend/app/services/data_quality.py` | 5 | Pre-pipeline validation |
| `backend/app/models/pipeline_run.py` | 5 | PipelineRun model |
| `backend/app/models/chat.py` | 7 | ChatSession + ChatMessage models |
| `backend/worker.py` | 5 | ARQ worker entrypoint |

### Modified files:
| File | Workstream | Changes |
|------|-----------|---------|
| `backend/app/config.py` | 2 | Env validation, new settings |
| `backend/app/main.py` | 2, 4 | Register middleware, expand health check, tighten CORS |
| `backend/app/services/upload_service.py` | 2 | CSV sanitization |
| `nginx/nginx.conf` | 2 | Security headers (HSTS, CSP) |
| `backend/app/api/pipeline.py` | 5 | Enqueue endpoint, incremental flag, run versioning |
| `backend/app/services/agent_service.py` | 7 | Tool-use, memory, streaming, guardrails, citations |
| `backend/app/api/agents.py` | 7 | Session endpoints, streaming, workspace param |
| `backend/app/models/__init__.py` | 5, 7 | Export new models |
| `backend/pyproject.toml` | 2, 4, 5 | New dependencies |
| `docker-compose.yml` | 5 | Worker service |
| `frontend/src/lib/api.ts` | 7 | Session + streaming interfaces |
| `frontend/src/app/agents/page.tsx` | 7 | Session UI, streaming, confidence |

### New migrations:
- `add_pipeline_runs_table.py`
- `add_chat_sessions_and_messages.py`

### New dependencies:
- `cryptography>=43.0.0` (encryption)
- `prometheus-client>=0.21.0` (metrics)
- `arq>=0.26.0` (async job queue)
