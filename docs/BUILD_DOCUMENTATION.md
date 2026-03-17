# ArqAI FWA Platform — Comprehensive Build Documentation

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Technology Stack](#technology-stack)
3. [Infrastructure & Deployment](#infrastructure--deployment)
4. [Database Models (25 Tables)](#database-models)
5. [Backend Services (15 Modules)](#backend-services)
6. [API Endpoints (17 Routers, 100+ Endpoints)](#api-endpoints)
7. [AI Governance — TAO, CAPC, ODA-RAG](#ai-governance)
8. [Authentication & Authorization](#authentication--authorization)
9. [Middleware Layer](#middleware-layer)
10. [FWA Detection Rules Engine](#fwa-detection-rules-engine)
11. [Worker Process](#worker-process)
12. [Seed Data & Synthetic Generation](#seed-data)
13. [Frontend Application (14 Pages)](#frontend-application)
14. [Planned Features (Next Phase)](#planned-features)

---

## 1. Platform Overview

**ArqAI FWA** is an enterprise healthcare Fraud, Waste, and Abuse detection and prevention platform. It ingests insurance claims data (medical + pharmacy), runs configurable fraud detection rules, scores risk, creates investigation cases, and provides AI-powered investigation assistance.

**Core Pipeline Flow:**
```
CSV Upload / Data Source → Ingestion → Data Quality Validation → Enrichment
→ Rule Engine (30+ rules) → Scoring Engine → Case Creation → Auto-Assignment
→ Investigation (AI Agent + Manual) → Resolution → Audit Trail
```

**Key Capabilities:**
- Multi-tenant workspace isolation
- Medical + pharmacy claim processing (60K+ medical, 36K+ pharmacy synthetic claims)
- 30+ configurable FWA detection rules with dynamic weights/thresholds
- Risk scoring with 4-tier classification (Low/Medium/High/Critical)
- Auto-assignment to investigators (round-robin, workload-balanced, skill-matched)
- AI investigation assistant powered by Claude (with data-driven fallback)
- Three patent-pending AI governance systems (TAO, CAPC, ODA-RAG)
- Real-time notifications via Redis pub/sub + SSE
- Hash-chained immutable audit trail
- AES-256-GCM encryption for PII fields
- Prometheus metrics + structured logging
- Role-based access control with data classification tiers

**File Counts:** ~143 Python files, ~20 TypeScript files

---

## 2. Technology Stack

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | FastAPI | Async HTTP API server |
| ORM | SQLAlchemy 2.0 (async) | Database models with `mapped_column` pattern |
| Database | PostgreSQL 15 | Primary data store with JSONB |
| Cache/Queue | Redis 7 | Job queue (BRPOP), pub/sub (SSE), caching |
| AI | Anthropic Claude API | Investigation assistant, chat |
| Encryption | AES-256-GCM (cryptography lib) | PII field encryption |
| Metrics | prometheus-client | Observability |
| Email | aiosmtplib | Async SMTP delivery |
| DB Driver | asyncpg | Async PostgreSQL driver |
| Validation | Pydantic v2 | Request/response schemas |

### Frontend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 14.2.21 | React app router |
| Language | TypeScript 5.7.2 | Type safety |
| Styling | TailwindCSS 3.4.16 | Utility-first CSS |
| Charts | Recharts 3.7.0 | Data visualization |
| Icons | Lucide React 0.460.0 | Icon library |
| Markdown | react-markdown 10.1.0 + remark-gfm | AI response rendering |

### Infrastructure
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Containers | Docker Compose | Multi-service orchestration |
| Reverse Proxy | Nginx | Frontend + API routing |
| Worker | Custom async worker | Background pipeline jobs, ingestion polling, SLA monitoring |

---

## 3. Infrastructure & Deployment

### `docker-compose.yml` Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | postgres:15 | 5432 | Data persistence |
| `redis` | redis:7 | 6379 | Job queue + pub/sub |
| `backend` | ./backend (FastAPI) | 8000 | API server |
| `worker` | ./backend (worker.py) | — | Background job processor |
| `frontend` | ./frontend (Next.js) | 3000 | UI application |
| `nginx` | nginx | 80 | Reverse proxy |

### Environment Variables
```
POSTGRES_DB=arqai_fwa
POSTGRES_USER=arqai
DATABASE_URL=postgresql+asyncpg://arqai:password@postgres:5432/arqai_fwa
REDIS_URL=redis://redis:6379/0
ANTHROPIC_API_KEY=<key>
LLM_MODEL=claude-haiku-4-5-20251001
SECRET_KEY=<secret>
ENVIRONMENT=development|production
LOG_LEVEL=INFO
ENCRYPTION_KEY=<32-byte-key>
SMTP_HOST=<host>
SMTP_PORT=587
SMTP_USER=<user>
SMTP_PASSWORD=<password>
SMTP_FROM_EMAIL=noreply@arqai.com
```

### Configuration (`backend/app/config.py`)
Pydantic `BaseSettings` class with:
- Database + Redis URLs
- Anthropic API key + model selection
- Secret key + environment mode
- CORS allowed origins
- Rate limit per minute
- Encryption key for PII
- Watched folder base path for ingestion
- SMTP settings (host, port, user, password, from_email, TLS flag)
- **Production validation**: rejects default secret_key, dev DB password, requires encryption_key

### Database Setup (`backend/app/database.py`)
- `create_async_engine()` with `settings.database_url`
- `async_sessionmaker` for session factory
- `Base = DeclarativeBase` — all models inherit from this
- `get_db()` — FastAPI dependency that yields async sessions

### App Initialization (`backend/app/main.py`)
- **Lifespan**: On startup → verify DB connection → create all tables via `Base.metadata.create_all()`
- **Middleware stack** (order matters):
  1. CORS (configurable origins)
  2. Security headers
  3. Rate limiting
  4. Request context (request ID + timing)
  5. Prometheus metrics
- **Global exception handler**: Returns traceback in dev mode, generic 500 in production
- **Router registration**: All 17 API routers included
- **Health check**: `GET /api/health` — returns DB, Redis, LLM connectivity status

---

## 4. Database Models

### 4.1 Core Domain Models

#### Workspace (`backend/app/models/workspace.py`)
**Table:** `workspaces`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| workspace_id | String(32) | UNIQUE, INDEX | — |
| name | String(100) | | — |
| client_name | String(100) | NULLABLE | NULL |
| description | String(500) | NULLABLE | NULL |
| data_source | String(20) | | "upload" |
| status | String(20) | | "active" |
| claim_count | Integer | | 0 |
| created_at | DateTime | SERVER_DEFAULT | func.now() |
| updated_at | DateTime | SERVER_DEFAULT, ONUPDATE | func.now() |

Multi-tenant container — most models have optional `workspace_id` FK.

---

#### Member (`backend/app/models/member.py`)
**Table:** `members`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| member_id | String(20) | UNIQUE, INDEX | — |
| first_name | String(100) | | — |
| last_name | String(100) | | — |
| date_of_birth | Date | | — |
| gender | String(1) | | — |
| address | String(300) | NULLABLE | NULL |
| city | String(100) | NULLABLE | NULL |
| state | String(2) | | — |
| zip_code | String(10) | | — |
| plan_id | String(20) | | — |
| plan_type | String(20) | | — |
| eligibility_start | Date | | — |
| eligibility_end | Date | NULLABLE | NULL |
| is_active | Boolean | | True |
| workspace_id | Integer | FK(workspaces.id), NULLABLE, INDEX | NULL |
| created_at / updated_at | DateTime | SERVER_DEFAULT | func.now() |

Plan types: MA (Medicare Advantage), Commercial, Medicaid.

---

#### Provider (`backend/app/models/provider.py`)
**Table:** `providers`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| npi | String(10) | UNIQUE, INDEX | — |
| name | String(200) | | — |
| specialty | String(100) | | — |
| taxonomy_code | String(20) | NULLABLE | NULL |
| practice_address/city/state/zip | String | NULLABLE | — |
| phone | String(20) | NULLABLE | NULL |
| entity_type | String(20) | | — |
| is_active | Boolean | | True |
| oig_excluded | Boolean | | False |
| dea_registration | String(20) | NULLABLE | NULL |
| dea_schedule | String(10) | NULLABLE | NULL |
| workspace_id | Integer | FK, NULLABLE, INDEX | NULL |
| created_at / updated_at | DateTime | | func.now() |

---

#### Pharmacy (`backend/app/models/provider.py`)
**Table:** `pharmacies`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| npi | String(10) | UNIQUE, INDEX | — |
| name | String(200) | | — |
| chain_name | String(100) | NULLABLE | NULL |
| address/city/state/zip_code | String | | — |
| phone | String(20) | NULLABLE | NULL |
| pharmacy_type | String(20) | | — |
| is_active | Boolean | | True |
| oig_excluded | Boolean | | False |
| workspace_id | Integer | FK, NULLABLE, INDEX | NULL |
| created_at / updated_at | DateTime | | func.now() |

---

#### MedicalClaim (`backend/app/models/claim.py`)
**Table:** `medical_claims`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| claim_id | String(30) | UNIQUE, INDEX | — |
| member_id | Integer | FK(members.id), INDEX | — |
| provider_id | Integer | FK(providers.id), INDEX | — |
| referring_provider_id | Integer | FK(providers.id), NULLABLE | NULL |
| service_date | Date | INDEX | — |
| admission_date / discharge_date | Date | NULLABLE | NULL |
| place_of_service | String(5) | | — |
| claim_type | String(20) | | — |
| cpt_code | String(10) | INDEX | — |
| cpt_modifier | String(10) | NULLABLE | NULL |
| diagnosis_code_primary | String(10) | INDEX | — |
| diagnosis_code_2/3/4 | String(10) | NULLABLE | NULL |
| amount_billed | Numeric(12,2) | | — |
| amount_allowed / amount_paid | Numeric(12,2) | NULLABLE | NULL |
| units | Integer | | 1 |
| length_of_stay | Integer | NULLABLE | NULL |
| drg_code / revenue_code | String(10) | NULLABLE | NULL |
| plan_id | String(20) | NULLABLE | NULL |
| status | String(20) | | "received" |
| workspace_id | Integer | FK, NULLABLE, INDEX | NULL |
| batch_id | String(50) | NULLABLE, INDEX | NULL |
| created_at / updated_at | DateTime | | func.now() |

**Relationships:** member, provider, referring_provider
**Indices:** 8 indexed columns for query performance

---

#### PharmacyClaim (`backend/app/models/claim.py`)
**Table:** `pharmacy_claims`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| claim_id | String(30) | UNIQUE, INDEX | — |
| member_id | Integer | FK(members.id), INDEX | — |
| pharmacy_id | Integer | FK(pharmacies.id), INDEX | — |
| prescriber_id | Integer | FK(providers.id), INDEX | — |
| fill_date | Date | INDEX | — |
| ndc_code | String(15) | INDEX | — |
| drug_name | String(200) | | — |
| drug_class | String(100) | NULLABLE | NULL |
| is_generic / is_controlled | Boolean | | False |
| dea_schedule | String(5) | NULLABLE | NULL |
| quantity_dispensed | Numeric(10,2) | | — |
| days_supply | Integer | | — |
| refill_number | Integer | | 0 |
| amount_billed / amount_allowed / amount_paid | Numeric(12,2) | | — |
| copay | Numeric(8,2) | NULLABLE | NULL |
| prescriber_npi / pharmacy_npi | String(10) | | — |
| prior_auth | Boolean | | False |
| workspace_id | Integer | FK, NULLABLE, INDEX | NULL |
| status | String(20) | | "received" |
| batch_id | String(50) | NULLABLE, INDEX | NULL |
| created_at / updated_at | DateTime | | func.now() |

**Relationships:** member, pharmacy, prescriber

---

### 4.2 Investigation Models

#### InvestigationCase (`backend/app/models/case.py`)
**Table:** `investigation_cases`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| case_id | String(30) | UNIQUE, INDEX | — |
| claim_id | String(30) | INDEX | — |
| claim_type | String(20) | | — |
| risk_score | Numeric(6,2) | | — |
| risk_level | String(10) | | — |
| status | String(20) | INDEX | "open" |
| priority | String(5) | INDEX | — |
| assigned_to | String(100) | NULLABLE | NULL |
| resolution_path | String(30) | NULLABLE | NULL |
| resolution_notes | String(2000) | NULLABLE | NULL |
| estimated_fraud_amount | Numeric(12,2) | NULLABLE | NULL |
| recovery_amount | Numeric(12,2) | NULLABLE | NULL |
| workspace_id | Integer | FK, NULLABLE, INDEX | NULL |
| sla_deadline | DateTime | NULLABLE | NULL |
| created_at | DateTime | | func.now() |
| resolved_at / closed_at | DateTime | NULLABLE | NULL |

**Relationships:** notes (cascade delete), evidence (cascade delete)

**Status Flow:** open → under_review → escalated → resolved → closed
**Priority Levels:** P1 (48h SLA), P2 (120h), P3 (240h), P4 (480h)
**Resolution Paths:** provider_accepts, provider_disputes, plan_benefit_issue, no_response, complex_case, false_positive

---

#### CaseNote (`backend/app/models/case.py`)
**Table:** `case_notes` — id, case_id (FK), author, content (5000 chars), created_at

#### CaseEvidence (`backend/app/models/case.py`)
**Table:** `case_evidence` — id, case_id (FK), evidence_type, title, content (JSONB), created_at
Evidence types: claim_data, risk_assessment, rule_findings, provider_history

---

### 4.3 Rules & Scoring Models

#### Rule (`backend/app/models/rule.py`)
**Table:** `rules`

| Column | Type | Constraints | Default |
|--------|------|-----------|---------|
| id | Integer | PK | auto |
| rule_id | String(10) | UNIQUE, INDEX | — |
| category | String(50) | | — |
| fraud_type | String(20) | | — |
| claim_type | String(20) | | — |
| description | String(500) | | — |
| detection_logic | String(500) | | — |
| enabled | Boolean | | True |
| weight | Numeric(4,1) | | — |
| thresholds | JSONB | | {} |
| benchmark_source | String(50) | NULLABLE | NULL |
| implementation_priority | String(10) | | — |
| version | Integer | | 1 |
| last_modified_by | String(100) | NULLABLE | NULL |
| created_at / updated_at | DateTime | | func.now() |

---

#### RuleResult (`backend/app/models/rule.py`)
**Table:** `rule_results` — claim_id, claim_type, rule_id, triggered (bool), severity (0-3.0), confidence (0-1.0), evidence (JSONB), details, workspace_id, evaluated_at, batch_id

#### RiskScore (`backend/app/models/scoring.py`)
**Table:** `risk_scores` — claim_id (UNIQUE), claim_type, total_score (0-100), risk_level, rules_triggered (count), rule_contributions (JSONB), confidence_factor, workspace_id, scored_at, batch_id

**Risk Thresholds:** Low: 0-30, Medium: 31-60, High: 61-85, Critical: 86-100

---

### 4.4 Pipeline & Ingestion Models

#### PipelineRun (`backend/app/models/pipeline_run.py`)
**Table:** `pipeline_runs` — run_id, workspace_id, batch_id, started_at, completed_at, status, duration_seconds, config_snapshot (JSONB), stats (JSONB), quality_report (JSONB)

#### DataSource (`backend/app/models/data_source.py`)
**Table:** `data_sources` — source_id, name, source_type (watched_folder|api_endpoint|database_query), claim_type, connection_config (JSONB), field_mapping (JSONB), polling_interval_seconds (default 3600), is_enabled, auto_run_pipeline, workspace_id, last_polled_at, last_watermark

#### IngestionRun (`backend/app/models/ingestion_run.py`)
**Table:** `ingestion_runs` — run_id, data_source_id (FK), status (running|completed|failed|no_data), rows_found, rows_ingested, rows_skipped, error_count, errors (JSONB), batch_id, pipeline_job_id, duration_seconds, started_at, completed_at

---

### 4.5 Assignment & Notification Models

#### Investigator (`backend/app/models/investigator.py`)
**Table:** `investigators` — investigator_id, name, email, specialty (medical|pharmacy|both), seniority (junior|standard|senior), max_caseload (default 20), is_available, workspace_id, created_at, updated_at

#### AssignmentRule (`backend/app/models/assignment_rule.py`)
**Table:** `assignment_rules` — rule_id, name, description, priority (lower=higher), conditions (JSONB), strategy (round_robin|workload_balanced|skill_matched), target_filter (JSONB), is_enabled, workspace_id

#### Notification (`backend/app/models/notification.py`)
**Table:** `notifications` — notification_id, recipient (INDEX), notification_type (INDEX), title, body, resource_type, resource_id, is_read (INDEX), created_at (INDEX), read_at
Types: case_assigned, case_status_changed, sla_warning, sla_breached, case_resolved, pipeline_completed, case_escalated

#### NotificationPreference (`backend/app/models/notification.py`)
**Table:** `notification_preferences` — recipient (UNIQUE), preferences (JSONB)

---

### 4.6 Audit & Chat Models

#### AuditLog (`backend/app/models/audit.py`)
**Table:** `audit_log` — event_id, event_type (INDEX), actor, action, resource_type, resource_id, details (JSONB), previous_hash, current_hash, created_at (INDEX)
**Hash chain:** SHA-256(content + previous_hash) — immutable, verifiable

#### ChatSession (`backend/app/models/chat.py`)
**Table:** `chat_sessions` — session_id, workspace_id, title (default "New Chat"), case_id (INDEX)

#### ChatMessage (`backend/app/models/chat.py`)
**Table:** `chat_messages` — session_id (FK, CASCADE DELETE), role, content (Text), sources_cited (JSONB), model_used, confidence, created_at

---

### 4.7 Reference Data Models

#### CPTReference (`backend/app/models/reference.py`)
**Table:** `cpt_reference` — cpt_code (UNIQUE), description, category, facility_price, non_facility_price, rvu_work, rvu_practice, rvu_malpractice, global_period, bundled_codes (JSONB), is_outpatient_typical, is_lab_diagnostic, is_dme

#### ICDReference (`backend/app/models/reference.py`)
**Table:** `icd_reference` — icd_code (UNIQUE), description, category, is_billable, valid_cpt_codes (JSONB), gender_specific, age_range_min, age_range_max

#### NDCReference (`backend/app/models/reference.py`)
**Table:** `ndc_reference` — ndc_code (UNIQUE), proprietary_name, nonproprietary_name, dosage_form, route, substance_name, dea_schedule, therapeutic_class, avg_wholesale_price, unit_price, generic_available, generic_ndc, generic_price

---

### 4.8 Governance Models (TAO/CAPC/ODA-RAG)

Registered in `__init__.py` alongside core models:

**TAO Models:** LineageNode, LineageEdge, CapabilityToken, AgentTrustProfile, HITLRequest, AuditReceipt
**CAPC Models:** ComplianceIRRecord, EvidencePacket
**ODA-RAG Models:** RAGSignal, AdaptationEvent, RAGFeedback

*(Detailed in Section 7)*

---

## 5. Backend Services

### 5.1 UploadService (`backend/app/services/upload_service.py`)
**Purpose:** Parse CSV uploads, validate data, ingest claims into database.

**Classes:** UploadPreview, ValidationResult, IngestionResult, UploadService

**Key Methods:**
- `preview_csv(file_content, claim_type)` → Auto-maps columns, returns preview (100 rows max)
- `ingest_medical(workspace, file_content, mapping)` → Parses medical claims CSV, creates providers/members on-the-fly, batch flushes every 500 rows
- `ingest_pharmacy(workspace, file_content, mapping)` → Same for pharmacy claims

**Patterns:**
- Pre-loads existing providers/members/claim_ids into memory caches for deduplication
- Handles 6 date formats, strips `$` and commas from amounts
- CSV injection prevention: rejects formula prefixes (`=`, `+`, `-`, `@`) via `_sanitize_cell()`

---

### 5.2 CaseManager (`backend/app/services/case_manager.py`)
**Purpose:** Full investigation case lifecycle — creation, status transitions, resolution, SLA tracking.

**Key Methods:**
- `create_cases_from_scores(scores, generate_evidence=True)` → Auto-creates cases for high/critical scores, sets priority (critical→P1, high→P2), calculates SLA deadlines, auto-assigns via AssignmentService, generates evidence bundles
- `_generate_evidence_bundle(case)` → Creates 4 evidence types: claim_data, risk_assessment, rule_findings, provider_history
- `update_status(case_id, new_status, actor)` → Validates state transitions, audit logs
- `resolve_case(case_id, resolution_path, notes, recovery_amount)` → Sets resolved + records recovery
- `escalate_case(case_id, reason, new_priority)` → Escalates + optional priority upgrade with new SLA
- `get_sla_breached_cases()` → Past-deadline cases
- `get_case_stats()` → Dashboard statistics (by status, priority, avg resolution, SLA breach count)

**SLA Deadlines:** P1=48h, P2=120h, P3=240h, P4=480h

---

### 5.3 RuleEngine (`backend/app/services/rule_engine.py`)
**Purpose:** Dynamic rule discovery, loading, evaluation orchestration.

**Key Methods:**
- `load_rules()` → Discovers `BaseRule` subclasses from `app.rules.medical` and `app.rules.pharmacy` via `importlib`/`pkgutil`
- `load_configs()` → Loads rule metadata from DB (enabled, weight, thresholds)
- `evaluate_claim(claim, batch_id)` → Runs all enabled rules for claim type, catches exceptions per rule
- `evaluate_batch(claims, batch_id)` → Batch wrapper → `dict[claim_id: list[RuleResult]]`
- `save_results(results)` → Persists in batches of 500

---

### 5.4 ScoringEngine (`backend/app/services/scoring_engine.py`)
**Purpose:** Aggregate rule results into 0-100 risk scores.

**Algorithm:**
```
Total Score = SUM(weight x severity x confidence) / max_possible x 100
max_possible per rule = weight x 3.0 (max severity)
Clamped to [0, 100]
```

**Key Methods:**
- `load_weights()` → From DB rule configs
- `classify_risk(score)` → Maps to Low/Medium/High/Critical
- `score_claim(claim_id, claim_type, rule_results, batch_id)` → Calculates contributions per rule, average confidence
- `score_batch(results, claim_type, batch_id)` → Batch wrapper
- `save_scores(scores)` → Batches of 500

---

### 5.5 AssignmentService (`backend/app/services/assignment_service.py`)
**Purpose:** Auto-assign cases to investigators using configurable rules and strategies.

**Three Strategies:**
1. **round_robin** — Least recently assigned investigator
2. **workload_balanced** — Fewest active cases (open/under_review/escalated)
3. **skill_matched** — Exact specialty match (medical/pharmacy), then workload tiebreaker

**Key Methods:**
- `auto_assign(case)` → Loads enabled rules by priority ASC, matches case conditions (priority, claim_type, risk_level), filters candidates by workspace/seniority/specialty/availability/capacity, applies strategy
- `_find_candidates(target_filter, workspace_id)` → Filters available investigators under max_caseload
- `_get_active_caseload(investigator)` → Counts open/under_review/escalated cases
- `get_workload_summary(workspace_id)` → Per-investigator: active_cases, max_caseload, utilization %

---

### 5.6 NotificationService (`backend/app/services/notification_service.py`)
**Purpose:** In-app notifications with Redis pub/sub for real-time SSE delivery.

**Key Methods:**
- `notify(recipient, type, title, body, resource_type, resource_id)` → Creates DB record + publishes to Redis channel `notifications:{recipient}`
- Specialized methods: `notify_case_assigned()`, `notify_case_status_changed()`, `notify_sla_warning()`, `notify_sla_breached()`, `notify_case_escalated()`, `notify_pipeline_completed()`
- `get_unread_count(recipient)` → Count
- `get_notifications(recipient, is_read, limit, offset)` → Ordered by created_at DESC
- `mark_read(notification_id, recipient)` → Single
- `mark_all_read(recipient)` → Batch, returns rowcount

---

### 5.7 IngestionService (`backend/app/services/ingestion_service.py`)
**Purpose:** Continuous data ingestion from external sources.

**Supported Source Types:**
1. **watched_folder** — Scans for new/modified CSV files (watermark = mtime)
2. **api_endpoint** — Polls external REST API (JSON→CSV), supports GET/POST, custom headers, Bearer/API-Key auth from env vars
3. **database_query** — Executes SQL with `:watermark` parameter substitution

**Key Methods:**
- `poll_source(source)` → Dispatches to fetcher, counts rows, calls upload_service.ingest_*, auto-triggers pipeline if configured, records IngestionRun
- `_fetch_watched_folder(config, watermark)` → Filters by glob pattern, processes files newer than watermark, concatenates CSVs
- `_fetch_api_endpoint(config, watermark)` → External API call, JSON→CSV conversion, cursor_field tracking
- `_fetch_database_query(config, watermark)` → SQL execution, watermark_column updates
- `test_connection(source)` → Validates connectivity, returns sample 5 rows

---

### 5.8 AgentService (`backend/app/services/agent_service.py`)
**Purpose:** AI-powered investigation assistant with Claude API + data-driven fallback.

**Components integrated:** TAO (trust/lineage), CAPC (compliance IR), ODA-RAG (adaptive signals)

**Key Features:**
- Conversation memory (session-based, max 20 history messages)
- Workspace-scoped guardrails (permission checks)
- Tool-use / ReAct loop when API available
- Citation linking (auto-converts case/rule IDs to markdown links)
- Confidence indicators (high/medium/low)
- Streaming support via AsyncIterator
- Fallback to data-driven queries when Anthropic API unavailable

**Key Methods:**
- `investigate_case(case_id)` → Full case analysis → InvestigationResult (summary, findings, risk_assessment, recommended_actions, confidence)
- `chat(message, case_id, session_id)` → Interactive conversation → ChatResponse (text, sources_cited, model_used, confidence)

---

### 5.9 AuditService (`backend/app/services/audit_service.py`)
**Purpose:** Immutable, hash-chained audit trail.

**Hash Chain:** `SHA-256(content + previous_hash)` — each entry links to the prior, cannot modify without breaking chain.

**Key Methods:**
- `log_event(event_type, actor, action, resource_type, resource_id, details)` → Core method
- Specialized: `log_claim_ingested()`, `log_rule_evaluated()`, `log_score_calculated()`, `log_case_created()`, `log_case_updated()`, `log_rule_config_changed()`
- `verify_chain_integrity()` → Walks all entries, validates hashes → `{valid, entries_checked, first_invalid}`
- `get_entries(event_type, resource_type, resource_id, limit, offset)` → Filtered retrieval

---

### 5.10 JobQueue (`backend/app/services/job_queue.py`)
**Purpose:** Async job queue for pipeline execution via Redis.

**Key Functions:**
- `enqueue_pipeline_job(workspace_id, limit, batch_id, force_reprocess)` → Creates `PJOB-{uuid}`, stores in Redis hash `pipeline:job:{job_id}`, pushes to `arqai:pipeline:queue`, 24h expiry
- `get_job_status(job_id)` → Retrieves from Redis hash
- `update_job_status(job_id, status, phase, progress, claims_processed, errors, result)` → Updates hash fields, auto-sets timestamps

**Job Phases:** pending → queued → running → loading → quality → enrichment → rules → scoring → cases → done → completed|failed

---

### 5.11 DataQualityService (`backend/app/services/data_quality.py`)
**Purpose:** Pre-enrichment validation gates.

**Validation Checks:**
1. **Duplicate Detection** — Medical: (provider_id, member_id, service_date, cpt_code); Pharmacy: (member_id, fill_date, ndc_code)
2. **Schema Conformance** — Required fields, valid dates, positive amounts
3. **Outlier Detection** — amount_billed > 3 std devs from mean for CPT/NDC code (requires ≥5 samples)
4. **Referential Integrity** — provider_id and member_id exist in DB

**Output:** `QualityReport` with total_claims, passed, failed, issues[] (capped at 200)

---

### 5.12 EnrichmentService (`backend/app/services/enrichment.py`)
**Purpose:** Adds reference lookups, provider context, historical patterns to raw claims.

**EnrichedMedicalClaim adds:**
- CPT enrichment: description, category, facility/non-facility prices, flags (outpatient_typical, lab_diagnostic, dme)
- ICD enrichment: description, valid CPT codes, gender_specific, age_range
- Provider enrichment: NPI, name, specialty, OIG exclusion status
- Member enrichment: member_id, gender, age, plan_type, eligibility_end
- Historical: member_claims_30d/90d, member_total_billed_30d, provider_claims_30d
- Provider patterns: modifier_25/59 rates, copay_waiver_rate, lab_order_rate, telehealth_per_day_max, avg_diagnosis_codes, referral_concentration

**EnrichedPharmacyClaim** — Similar structure for pharmacy domain.

---

### 5.13 EncryptionService (`backend/app/services/encryption_service.py`)
**Purpose:** AES-256-GCM encryption for PII fields.

- `encrypt_field(plaintext)` → Random 12-byte nonce + AES-256-GCM → `"enc::{base64}"`
- `decrypt_field(value)` → Extracts nonce, decrypts; passes through unencrypted values
- `is_encrypted(value)` → Checks `"enc::"` prefix
- Falls back to plaintext with warning if key not configured (dev mode)

---

### 5.14 PatternConfidenceService (`backend/app/services/pattern_confidence.py`)
**Purpose:** Compute confidence scores blending rule evaluation with historical case outcomes.

**Algorithm:**
- Historical accuracy = confirmed_fraud_rate from resolved cases where rule triggered
- Weighting: ≥10 samples → 40% rule + 60% historical; ≥3 samples → 60% rule + 40% historical; else rule only
- `compute_for_claim(claim_id)` → overall_confidence + per-rule pattern_scores with historical_accuracy, sample_size, confirmed_rate

---

### 5.15 RuleTraceService (`backend/app/services/rule_trace.py`)
**Purpose:** Generate human-readable rule evaluation explanations.

- `get_trace(claim_id)` → total_score, risk_level, steps[] (triggered first desc by contribution, then non-triggered alphabetical)
- Each step: rule_id, name, category, fraud_type, triggered, severity, confidence, weight, contribution, explanation, evidence
- Templates: high-volume pattern ("Provider billed X patients... Average: Y... Z x above threshold"), billed amount ("$X vs expected max $Y"), fallback (detection_logic + evidence)

---

## 6. API Endpoints

### 6.1 Dashboard (`backend/app/api/dashboard.py`) — `/api/dashboard`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/overview` | Total claims, flagged, fraud amount, active cases, recovery rate, risk distribution |
| GET | `/trends` | Claims processed/flagged over time (30d/90d/custom) |
| GET | `/top-providers` | Top N providers by risk/fraud amount |
| GET | `/rule-effectiveness` | Rule stats (trigger count, avg severity, total fraud) |
| GET | `/sla-status` | SLA breach summary |

### 6.2 Claims (`backend/app/api/claims.py`) — `/api/claims`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Paginated list with type/status/risk_level filters |
| GET | `/{claim_id}` | Detail + rule results + risk score + related cases |
| POST | `/process-batch` | Run enrichment → rules → scoring on batch |
| GET | `/{claim_id}/rule-trace` | Step-by-step rule evaluation explanation |
| GET | `/{claim_id}/confidence` | Pattern confidence breakdown |

### 6.3 Cases (`backend/app/api/cases.py`) — `/api/cases`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Paginated queue with status/priority/assignee filters |
| GET | `/{case_id}` | Detail with claim info, risk score, triggered rules, evidence, notes |
| POST | `/{case_id}/status` | Update status with validation + audit |
| POST | `/{case_id}/assign` | Manual assignment (validates against Investigator table) |
| POST | `/{case_id}/escalate` | Escalate with reason |
| POST | `/{case_id}/resolve` | Resolve with path + notes + recovery amount |
| POST | `/{case_id}/notes` | Add case note |
| GET | `/{case_id}/evidence` | Retrieve evidence bundle |
| GET | `/stats` | Case statistics for dashboard |

### 6.4 Rules (`backend/app/api/rules.py`) — `/api/rules`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | All rules with config (enabled, weight, thresholds) |
| GET | `/{rule_id}` | Single rule detail |
| PUT | `/{rule_id}/config` | Update weight/thresholds/enabled (audit logged) |
| GET | `/{rule_id}/stats` | Rule effectiveness (times triggered, avg severity, total fraud) |
| GET | `/compare` | Compare effectiveness across rules |

### 6.5 Pipeline (`backend/app/api/pipeline.py`) — `/api/pipeline`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/run-full` | Synchronous full pipeline (loads → quality → enrich → rules → score → cases) |
| POST | `/enqueue` | Async job enqueue (returns job_id immediately) |
| GET | `/jobs/{job_id}` | Job status (phase, progress, claims_processed, errors) |
| GET | `/status` | Overall pipeline statistics |
| GET | `/runs` | List past runs |
| GET | `/runs/{run_id}` | Run detail with quality report |

### 6.6 Agents (`backend/app/api/agents.py`) — `/api/agents`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Agent readiness, model, mode (claude/data-engine) |
| POST | `/investigate` | AI case analysis → findings + recommendations |
| POST | `/chat` | Interactive conversation with case/session scoping |
| GET | `/sessions` | List chat sessions |
| GET | `/sessions/{session_id}` | Session detail with message history |
| POST | `/sessions/{session_id}/messages` | Add message to session |
| POST | `/sessions/new` | Create new chat session |

### 6.7 Governance (`backend/app/api/governance.py`) — `/api/governance`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | TAO/CAPC/ODA-RAG health summary |
| GET | `/tao/trust-profiles` | Agent trust scores |
| GET | `/tao/hitl-requests` | Human-in-the-loop approval queue |
| GET | `/tao/lineage` | Lineage nodes (filter by node_type, agent_id) |
| GET | `/tao/audit-receipts` | Cryptographic attestation receipts |
| GET | `/capc/evidence-packets` | Compliance audit packets |
| GET | `/oda-rag/signals` | RAG observability metrics |
| GET | `/oda-rag/adaptations` | Parameter update history |
| GET | `/oda-rag/feedback` | User quality feedback |

### 6.8 Audit (`backend/app/api/audit.py`) — `/api/audit`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/logs` | Filtered by event_type, resource_type, resource_id |
| GET | `/logs/{log_id}` | Single entry detail |
| GET | `/verify-chain` | Hash chain integrity verification |
| GET | `/stats` | Audit statistics by event type |

### 6.9 Workspaces (`backend/app/api/workspaces.py`) — `/api/workspaces`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List workspaces |
| POST | `/` | Create workspace |
| GET | `/{workspace_id}` | Workspace detail |
| PUT | `/{workspace_id}` | Update workspace |
| DELETE | `/{workspace_id}` | Archive workspace |
| GET | `/{workspace_id}/members` | Workspace members |
| POST | `/{workspace_id}/members` | Add member |

### 6.10 Investigators (`backend/app/api/investigators.py`) — `/api/investigators`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List with availability/workload |
| POST | `/` | Create investigator |
| PUT | `/{id}` | Update investigator |
| GET | `/{id}/caseload` | Current cases by status/priority |
| GET | `/{id}/performance` | Stats (avg resolution, SLA compliance, recovery) |
| GET | `/workload` | Workload summary dashboard data |
| POST | `/assignment-rules` | Create assignment rule |
| GET | `/assignment-rules` | List rules ordered by priority |
| PUT | `/assignment-rules/{id}` | Update rule |
| DELETE | `/assignment-rules/{id}` | Delete rule |

### 6.11 Notifications (`backend/app/api/notifications.py`) — `/api/notifications`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | User's notifications with is_read filter |
| GET | `/unread/count` | Unread count (bell badge) |
| PUT | `/{notification_id}/read` | Mark as read |
| PUT | `/read-all` | Mark all as read |
| GET | `/subscribe` | SSE real-time stream via Redis pub/sub |

### 6.12 Ingestion (`backend/app/api/ingestion.py`) — `/api/ingestion`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/sources` | List data sources |
| POST | `/sources` | Create source |
| GET | `/sources/{source_id}` | Source detail |
| PUT | `/sources/{source_id}` | Update config |
| DELETE | `/sources/{source_id}` | Delete source |
| POST | `/sources/{source_id}/test` | Test connection + sample rows |
| POST | `/sources/{source_id}/poll` | Manual trigger |
| GET | `/runs` | List ingestion runs |
| GET | `/runs/{run_id}` | Run detail with errors |

### 6.13 Providers (`backend/app/api/providers.py`) — `/api/providers`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Search/filter providers |
| GET | `/{npi}` | Provider detail + claims history + risk profile |
| PUT | `/{npi}/flags` | Manual flagging/unflagging |
| GET | `/{npi}/claims` | Claims from this provider |
| GET | `/{npi}/patterns` | Historical patterns (modifier rates, referral concentration) |

### 6.14 Scoring (`backend/app/api/scoring.py`) — `/api/scoring`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/thresholds` | Current risk thresholds |
| PUT | `/thresholds` | Update thresholds (low_max, medium_max, high_max) |
| GET | `/{claim_id}` | Detailed score breakdown with rule contributions |

### 6.15 Metrics (`backend/app/api/metrics.py`) — `/metrics`
Prometheus-format export: pipeline_runs_total, pipeline_duration_seconds, pipeline_claims_processed, agent_chat_requests_total, agent_chat_duration_seconds, active_cases by risk level

### 6.16 Compliance (`backend/app/api/governance.py`) — `/api/governance`
Policy management, audit trail with hash chain verification, risk register, data classification metadata

---

## 7. AI Governance — TAO, CAPC, ODA-RAG

### 7.1 TAO: Trust-Aware Agent Orchestration (`backend/app/tao/`)

**Purpose:** Patent-pending governance for autonomous AI agent actions in regulated environments.

**Models (`tao/models.py`):**
- **LineageNode** — Processing event in DAG (node_id, node_type, agent_id, action, trust_score_at_action, capability_token_id)
- **LineageEdge** — Causal/data-flow dependency (source → target, relationship: produced|consumed|triggered|overrode|escalated_to)
- **CapabilityToken** — Ephemeral scoped authorization (issuer, subject_agent_id, action, resource_scope, constraints JSONB, expires_at, uses_remaining)
- **AgentTrustProfile** — Dynamic trust (agent_id, trust_score 0.0-1.0, decay_model, escalation_level, trust_history JSONB)
- **HITLRequest** — Human-in-the-loop approval (agent_id, action_risk_score, risk_tier, status: pending|approved|denied)
- **AuditReceipt** — Cryptographic attestation (lineage_node_id, action_type, input/output_hash, capability_token_snapshot, signature)

**Modules:**
- `lineage.py` — DAG engine for action lineage tracking
- `capability_tokens.py` — Ephemeral scoped token issuance/validation
- `risk_scoring.py` — Per-action risk calculation
- `trust.py` — Trust profiles with decay and escalation
- `orchestration.py` — Central controller coordinating all TAO components
- `audit_receipts.py` — Cryptographic receipt generation

**Risk Tiers:** LOW, MEDIUM, HIGH, CRITICAL — determine capability scope and HITL routing

---

### 7.2 CAPC: Compliance-Aware Prompt Compiler (`backend/app/capc/`)

**Purpose:** Transform NL agent requests into compliance-annotated intermediate representations with signed evidence packets.

**Models (`capc/models.py`):**
- **ComplianceIRRecord** — Compiled IR snapshot (ir_id, original_request, parsed_intents/entities, sensitivity_level, opcodes JSONB, validation_status)
- **EvidencePacket** — Signed audit packet (packet_id, ir_id, original_request, compiled_ir, policy_decisions, lineage_hashes, results, packet_hash, signature)

**Modules:**
- `compiler.py` — NL → Compliance IR compilation
- `opcodes.py` — Opcode definitions (query, filter, aggregate, join, encrypt, audit, escalate, approve), IR DAG structure
- `validator.py` — Static IR validation against policy graph
- `evidence.py` — Signed evidence packet generation
- `exception_router.py` — Exception handling (abort|rollback|manual_review)
- `policy_graph.py` — Policy enforcement graph

**Sensitivity Levels:** PUBLIC, INTERNAL, SENSITIVE, RESTRICTED, CLASSIFIED

---

### 7.3 ODA-RAG: Observability-Driven Adaptive RAG (`backend/app/oda_rag/`)

**Purpose:** Monitor RAG pipeline signals, detect drift/anomalies, dynamically adapt parameters.

**Models (`oda_rag/models.py`):**
- **RAGSignal** — Observability metric (signal_id, signal_type, metric_name, metric_value, context JSONB)
- **AdaptationEvent** — Parameter update action (event_id, trigger_signal_ids, drift_score, action_type, parameters_before/after JSONB, reason)
- **RAGFeedback** — User feedback (feedback_id, query, response_quality 0.0-1.0, relevance_score, feedback_source: explicit|implicit)

**Modules:**
- `signals.py` — Signal collection & monitoring (latency, recall, relevance, cost)
- `drift_detector.py` — Statistical drift and anomaly detection
- `adaptive_controller.py` — Decision engine for parameter updates
- `parameter_updaters.py` — Source re-weighting, chunk size adjustment, embedding refresh
- `learner.py` — Closed-loop learner integrating feedback

**Adaptation Types:** Source reweighting, chunk size adjustment, embedding refresh, prompt/model selection

---

## 8. Authentication & Authorization

### Roles (`backend/app/auth/roles.py`)
```
VIEWER < ANALYST < INVESTIGATOR < COMPLIANCE < ADMIN
                                                 ├─ SYSTEM (internal services)
```

### Permissions (`backend/app/auth/permissions.py`)
20+ granular permissions:
- **Claims:** READ, PROCESS
- **Cases:** READ, MANAGE, INVESTIGATE
- **Rules:** READ, CONFIGURE
- **Financial:** VIEW, EXPORT
- **Pipeline:** RUN, STATUS
- **Workspace:** READ, MANAGE, UPLOAD
- **Audit:** READ
- **Agent:** CHAT, INVESTIGATE
- **Admin:** USERS, SYSTEM

### Data Classification (`backend/app/auth/data_classification.py`)
Sensitivity tiers gate data disclosure:

| Tier | Examples | Required Permission |
|------|----------|-------------------|
| PUBLIC | Counts, statuses | None |
| INTERNAL | Case details | CASES_READ |
| SENSITIVE | Dollar amounts, PII | FINANCIAL_VIEW |
| RESTRICTED | Fraud estimates | FINANCIAL_VIEW |
| CLASSIFIED | Full audit trail | AUDIT_READ |

### RequestContext (`backend/app/auth/context.py`)
Per-request container: user_id, role, permissions set, workspace_id. Injected via middleware.

---

## 9. Middleware Layer

### `backend/app/middleware/`

| Module | Purpose |
|--------|---------|
| `metrics.py` | Prometheus instrumentation — HTTP request counter/histogram (method, path, status), pipeline metrics, agent chat metrics, case gauges by risk level |
| `rate_limit.py` | Token bucket rate limiting (configurable per endpoint) |
| `request_context.py` | Injects RequestContext (request ID + timing) per request |
| `logging_config.py` | Structured logging (JSON format, correlation IDs) |
| `security_headers.py` | CORS, CSP, security headers |

---

## 10. FWA Detection Rules Engine

### Base Rule Pattern (`backend/app/rules/base.py`)
```python
class BaseRule(ABC):
    rule_id: str
    category: str            # "billing", "clinical", "pharmacy"
    fraud_type: str          # "Fraud", "Waste", "Abuse"
    claim_type: str          # "medical" | "pharmacy"
    default_weight: float
    default_thresholds: dict

    async def evaluate(claim, thresholds) -> RuleEvaluation
```

**RuleEvaluation Output:**
- `triggered`: bool
- `severity`: 0.0-3.0 (higher = more severe)
- `confidence`: 0.3-1.0
- `evidence`: dict (supporting data points)
- `details`: str (human-readable explanation)

### Medical Rules (`backend/app/rules/medical/`)
- Upcoding detection
- Unbundling detection
- Phantom billing
- Duplicate claims
- High-volume billing patterns
- Modifier abuse (25, 59)
- Place of service anomalies
- Clinical impossibility checks

### Pharmacy Rules (`backend/app/rules/pharmacy/`)
- Doctor shopping detection
- Pill mill patterns
- Kickback indicators
- Early refill patterns
- Quantity anomalies
- Generic substitution avoidance
- Controlled substance patterns

---

## 11. Worker Process (`backend/worker.py`)

Async worker with multiple concurrent loops via `asyncio.gather()`:

### Pipeline Job Processing Loop
- Retrieves jobs from Redis queue: `arqai:pipeline:queue` (BRPOP)
- **Phases:** loading → quality → enrichment → rules → scoring → cases → audit
- Updates Redis job hash with progress (0-100%), claims_processed, errors
- Records `PipelineRun` with stats and quality report
- Mirrors synchronous `/api/pipeline/run-full` logic

### Ingestion Scheduler Loop
- Polls `DataSource` table for enabled sources where `last_polled_at + interval < now`
- Calls `IngestionService.poll_source()` for each due source
- Auto-enqueues pipeline job if `source.auto_run_pipeline`
- Checks every 30 seconds

### SLA Monitoring Loop
- Calls `CaseManager.get_sla_breached_cases()`
- Sends `sla_warning` notifications (24h before deadline)
- Sends `sla_breach` notifications (past deadline)
- Triggers escalation for breached cases

---

## 12. Seed Data

### `backend/app/seed/`

| Module | Content | Scale |
|--------|---------|-------|
| `claims_medical.py` | Medical claims with realistic CPT/ICD codes | 60,000+ lines |
| `claims_pharmacy.py` | Pharmacy claims with NDC codes | 36,000+ lines |
| `fraud_scenarios.py` | 15,000+ fraudulent claims with embedded patterns: upcoding, unbundling, phantom billing, doctor shopping, pill mill | |
| `members.py` | Member records (demographics, plan enrollment) | |
| `providers.py` | Provider records (NPI, specialty, OIG status) | |
| `reference_data.py` | CPT codes (with CMS pricing), ICD-10 codes, NDC codes (with AWP) | |
| `governance_data.py` | TAO: 10 pipeline agents, 1000+ lineage nodes, trust profiles, HITL requests; CAPC: evidence packets; ODA-RAG: signals, adaptations, feedback | |
| `synthetic_data.py` | Utility functions for synthetic generation | |

---

## 13. Frontend Application

### Design System

**ArqAI Brand Colors (TailwindCSS `tailwind.config.ts`):**
- Blue: #4F7AEF (400), #2A5BDB (500), #1E45B0 (600)
- Lime: #A3E635 (400), #84CC16 (500)
- Surface (dark): 0: #0A0E1A, 1: #111827, 2: #1A2235, 3: #243044
- Text: Primary #F1F5F9, Secondary #94A3B8, Muted #64748B
- Risk: Low #22c55e, Medium #f59e0b, High #ef4444, Critical #991b1b

### Pages & Routes

| Route | Page File | Purpose |
|-------|-----------|---------|
| `/` | `app/page.tsx` | Executive dashboard — stats, risk distribution, top providers, rule effectiveness, governance health |
| `/claims` | `app/claims/page.tsx` | Claims explorer — medical/pharmacy tabs, risk level filtering, amount sorting, detail slide-out panel |
| `/cases` | `app/cases/page.tsx` | Investigation queue — status/priority filtering, SLA tracking, assignment, pagination |
| `/cases/[id]` | `app/cases/[id]/page.tsx` | Case detail — notes, evidence, claim link, rule results, status updates, timeline |
| `/rules` | `app/rules/page.tsx` | Rule configuration — medical/pharmacy tabs, weight slider, threshold editing, enable/disable, stats |
| `/agents` | `app/agents/page.tsx` | AI investigation assistant — case-scoped chat, investigation button, session persistence |
| `/governance` | `app/governance/page.tsx` | AI governance — TAO trust/lineage, CAPC evidence, ODA-RAG signals/adaptation monitoring |
| `/pipeline` | `app/pipeline/page.tsx` | Detection pipeline — real-time run progress, batch stats, run history, job status |
| `/compliance` | `app/compliance/page.tsx` | Compliance tracking — policy status, audit trail summary |
| `/upload` | `app/upload/page.tsx` | Data upload — CSV upload with auto-column mapping, workspace selection, preview |
| `/investigators` | `app/investigators/page.tsx` | Investigator workload — caseload management, SLA tracking, assignment rules config |
| `/data-sources` | `app/data-sources/page.tsx` | Data sources — connection config, polling setup, ingestion run history |
| `/notifications` | `app/notifications/page.tsx` | Notification center — read/unread, preferences |

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Sidebar | `components/layout/sidebar.tsx` | 12 nav items, workspace switcher dropdown |
| NotificationBell | `components/layout/notification-bell.tsx` | Bell icon + unread badge + dropdown |
| ConfidenceIndicator | `components/confidence-indicator.tsx` | Color-coded confidence score display |
| PeerComparison | `components/peer-comparison.tsx` | Provider vs peer group analysis |
| RuleTrace | `components/rule-trace.tsx` | Step-by-step rule evaluation visualization |
| PipelineMonitor | `components/pipeline-monitor.tsx` | Real-time pipeline progress tracker |

### API Client (`frontend/src/lib/api.ts`)
~850 lines, 14 namespaces covering all backend endpoints:

1. **Dashboard** — overview, trends, topProviders, ruleEffectiveness
2. **Claims** — list, detail, ruleTrace, processBatch
3. **Rules** — list, detail, updateConfig, stats
4. **Cases** — list, detail, updateStatus, assign, addNote, evidence
5. **Audit** — list, integrity check
6. **Scoring** — thresholds
7. **Workspaces** — list, create, detail, archive
8. **Pipeline** — runFull, status, enqueue, jobStatus, runs, runDetail
9. **Providers** — peerComparison
10. **Agents** — status, investigate, chat, sessions, sessionMessages, newSession
11. **Governance** — trustProfiles, hitlRequests, lineage, auditReceipts, evidencePackets, signals, adaptations, feedback
12. **Investigators** — list, create, detail, update, delete, workload, rules
13. **Notifications** — list, unreadCount, markRead, markAllRead, preferences
14. **Ingestion** — sources, createSource, updateSource, testConnection, pollNow, runs

### State Management
- **WorkspaceContext** (`lib/workspace-context.tsx`) — React context for multi-workspace switching, active workspace ID, loading states

### Utility Functions (`lib/utils.ts`)
- Risk level → color mapping
- Priority (P1-P4) → color mapping
- Status → color mapping
- Currency/number/date/datetime formatting
- Chart styling (dark theme, custom colors, tooltips)

---

## 14. Planned Features (Next Phase)

### Feature 1: Continuous Data Ingestion Enhancements
- Watched folder auto-pickup for POC demos (drop CSV → auto-ingest → pipeline → cases)
- API endpoint polling (future)
- Database query integration (future)
- Already built: DataSource model, IngestionService (all 3 fetcher types), ingestion API, data-sources UI, worker scheduler loop

### Feature 2: Case Assignment Enhancements
- Already built: Investigator model, AssignmentRule model, AssignmentService (3 strategies), investigators API, auto-assignment in case_manager.py, investigators UI
- Potential enhancements: escalation paths, SLA-based auto-escalation, capacity planning

### Feature 3: Notification & Communication System Enhancements
- Already built: Notification model, NotificationService (in-app + Redis pub/sub), notifications API with SSE, notification-bell component
- Potential additions: DocumentRequest model for documentation lifecycle, enhanced case detail timeline with full activity feed, SMTP email delivery for external parties

---

## Architecture Summary

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend   │────▶│    Nginx     │────▶│   Backend   │
│   Next.js    │     │   (proxy)    │     │   FastAPI    │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌───────────────┬─────────────┼─────────────┐
                    │               │             │             │
              ┌─────▼─────┐  ┌─────▼─────┐ ┌────▼────┐  ┌────▼────┐
              │ PostgreSQL │  │   Redis   │ │  Worker │  │ Claude  │
              │   (data)   │  │(queue+pub)│ │ (async) │  │  (AI)   │
              └───────────┘  └───────────┘ └─────────┘  └─────────┘

Pipeline Flow:
  Upload/Ingest → DataQuality → Enrichment → RuleEngine → ScoringEngine
       → CaseManager → AssignmentService → NotificationService → AuditService

Governance Layer:
  TAO (Trust/Lineage) ←→ CAPC (Compliance IR) ←→ ODA-RAG (Adaptive Signals)
```

**Total:** 25 database tables, 15 service modules, 17 API routers (100+ endpoints), 14 frontend pages, 3 AI governance systems
