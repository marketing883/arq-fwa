# ArqAI FWA Detection & Prevention — Complete Build Plan

> **Purpose**: This is the single source of truth for the entire build. If context is ever lost,
> point Claude back to this file and the corresponding phase to resume work.
>
> **Source Documents**: `ArqAI FWA Detection POC.pdf`, `Trust_Aware_Agent_Orchestration_Whitepaper.pdf`,
> `Compliance_Aware_Prompt_Compiler.pdf`, `Observability_Driven_Adaptive_RAG.pdf`

---

## Tech Stack (Final)

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.11+, FastAPI | Async, healthcare/ML libs, fast dev |
| **Data Processing** | Polars (primary), pandas (compat) | Polars 10x faster for claims |
| **Database** | PostgreSQL 15+ (via Docker) | ACID for audit trail, proven at scale |
| **Cache** | Redis 7 (via Docker) | Session cache, API response cache |
| **Frontend** | Next.js 14 + TypeScript + Tailwind + shadcn/ui | Production-grade from day 1 |
| **Charts** | Recharts (React-native) | Lightweight, composable |
| **Tables** | TanStack Table | Headless, high-performance |
| **LLM (local)** | Ollama (llama3.1 / mistral) | Air-gapped, no API keys needed |
| **Vector DB** | ChromaDB | Local embeddings, RAG retrieval |
| **Task Queue** | None for POC (sync batch) | Keep simple; add Celery post-POC |
| **Deployment** | Docker Compose | Single `docker compose up` |
| **Testing** | pytest + httpx (async) | Backend tests |

---

## Final Directory Structure

```
arq-fwa/
├── BUILD_PLAN.md                    # THIS FILE
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app entry
│   │   ├── config.py                # Settings (pydantic-settings)
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── claim.py             # MedicalClaim, PharmacyClaim
│   │   │   ├── provider.py          # Provider, Pharmacy
│   │   │   ├── member.py            # Member
│   │   │   ├── rule.py              # Rule, RuleConfig, RuleResult
│   │   │   ├── scoring.py           # RiskScore
│   │   │   ├── case.py              # InvestigationCase, CaseNote
│   │   │   ├── audit.py             # AuditLog
│   │   │   └── reference.py         # NDCReference, CPTReference, ICDReference
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── claim.py
│   │   │   ├── rule.py
│   │   │   ├── scoring.py
│   │   │   ├── case.py
│   │   │   ├── dashboard.py
│   │   │   └── admin.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # Main API router
│   │   │   ├── claims.py
│   │   │   ├── rules.py
│   │   │   ├── scoring.py
│   │   │   ├── cases.py
│   │   │   ├── dashboard.py
│   │   │   ├── admin.py
│   │   │   ├── agents.py            # LLM agent endpoints
│   │   │   └── audit.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py         # Claims ingestion pipeline
│   │   │   ├── enrichment.py        # Data enrichment (NPI, NDC, CPT lookups)
│   │   │   ├── rule_engine.py       # Core rule evaluation engine
│   │   │   ├── scoring_engine.py    # Risk scoring calculator
│   │   │   ├── case_manager.py      # Investigation case lifecycle
│   │   │   ├── audit_service.py     # Immutable audit trail (ArqMesh)
│   │   │   ├── evidence_generator.py # Compliance evidence bundles
│   │   │   └── agent_service.py     # LLM agent orchestration
│   │   ├── rules/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # BaseRule abstract class
│   │   │   ├── medical/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── m01_upcoding.py
│   │   │   │   ├── m02_unbundling.py
│   │   │   │   ├── m03_duplicate_billing.py
│   │   │   │   ├── m04_phantom_billing.py
│   │   │   │   ├── m05_kickback_self_referral.py
│   │   │   │   ├── m06_medically_unnecessary.py
│   │   │   │   ├── m07_provider_collusion.py
│   │   │   │   ├── m08_modifier_misuse.py
│   │   │   │   ├── m09_copay_waiver.py
│   │   │   │   ├── m10_inpatient_outpatient_misclass.py
│   │   │   │   ├── m11_dme_fraud.py
│   │   │   │   ├── m12_lab_diagnostic_abuse.py
│   │   │   │   ├── m13_provider_ghosting.py
│   │   │   │   ├── m14_double_dipping.py
│   │   │   │   ├── m15_telehealth_fraud.py
│   │   │   │   └── m16_chart_padding.py
│   │   │   └── pharmacy/
│   │   │       ├── __init__.py
│   │   │       ├── p01_prescription_forgery.py
│   │   │       ├── p02_doctor_shopping.py
│   │   │       ├── p03_pharmacy_shopping.py
│   │   │       ├── p04_early_refill.py
│   │   │       ├── p05_controlled_substance_diversion.py
│   │   │       ├── p06_phantom_claims.py
│   │   │       ├── p07_upcoding_high_cost_substitution.py
│   │   │       ├── p08_kickback_split_billing.py
│   │   │       ├── p09_invalid_prescriber.py
│   │   │       ├── p10_stockpiling.py
│   │   │       ├── p11_compound_drug_fraud.py
│   │   │       ├── p12_phantom_members.py
│   │   │       └── p13_pharmacy_provider_collusion.py
│   │   └── seed/
│   │       ├── __init__.py
│   │       ├── synthetic_data.py    # Master data generator
│   │       ├── providers.py         # Provider/pharmacy seed data
│   │       ├── members.py           # Member seed data
│   │       ├── claims_medical.py    # Medical claims generator
│   │       ├── claims_pharmacy.py   # Pharmacy claims generator
│   │       ├── reference_data.py    # NDC, CPT, ICD-10 seed data
│   │       └── fraud_scenarios.py   # Pre-built fraud patterns
│   └── tests/
│       ├── conftest.py
│       ├── test_rules/
│       │   ├── test_medical_rules.py
│       │   └── test_pharmacy_rules.py
│       ├── test_scoring.py
│       ├── test_ingestion.py
│       ├── test_api.py
│       └── test_audit.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # Dashboard home (Executive Overview)
│   │   │   ├── claims/
│   │   │   │   └── page.tsx          # Claims explorer
│   │   │   ├── cases/
│   │   │   │   ├── page.tsx          # Investigation queue
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Case detail / investigation workspace
│   │   │   ├── rules/
│   │   │   │   └── page.tsx          # Rule configuration (admin)
│   │   │   ├── compliance/
│   │   │   │   └── page.tsx          # Compliance & audit logs
│   │   │   └── agents/
│   │   │       └── page.tsx          # AI agent chat / investigation assistant
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── header.tsx
│   │   │   │   └── nav-items.ts
│   │   │   ├── dashboard/
│   │   │   │   ├── stat-card.tsx
│   │   │   │   ├── fraud-trend-chart.tsx
│   │   │   │   ├── risk-distribution.tsx
│   │   │   │   ├── top-flagged-providers.tsx
│   │   │   │   └── recent-cases.tsx
│   │   │   ├── claims/
│   │   │   │   ├── claims-table.tsx
│   │   │   │   └── claim-detail-drawer.tsx
│   │   │   ├── cases/
│   │   │   │   ├── case-queue-table.tsx
│   │   │   │   ├── case-detail.tsx
│   │   │   │   ├── evidence-panel.tsx
│   │   │   │   └── case-timeline.tsx
│   │   │   ├── rules/
│   │   │   │   ├── rule-list.tsx
│   │   │   │   └── rule-config-form.tsx
│   │   │   ├── compliance/
│   │   │   │   ├── audit-log-table.tsx
│   │   │   │   └── compliance-report.tsx
│   │   │   └── agents/
│   │   │       ├── chat-interface.tsx
│   │   │       └── agent-response.tsx
│   │   └── lib/
│   │       ├── api.ts                # API client (fetch wrapper)
│   │       ├── types.ts              # TypeScript interfaces
│   │       └── utils.ts
│   └── public/
│       └── arqai-logo.svg
└── nginx/
    └── nginx.conf
```

---

## PHASE 0: Project Scaffolding & Infrastructure

### Objective
Set up the monorepo structure, Docker Compose services, and both backend/frontend skeletons so that `docker compose up` brings up a working (empty) system.

### Files to Create

**Root level:**
- `docker-compose.yml` — PostgreSQL 15, Redis 7, backend (FastAPI), frontend (Next.js), nginx
- `.env.example` — Template for DB_PASSWORD, REDIS_URL, OLLAMA_URL, etc.
- `.gitignore` — Python, Node, Docker, .env

**Backend skeleton:**
- `backend/Dockerfile` — Python 3.11-slim, install deps, uvicorn entrypoint
- `backend/pyproject.toml` — Dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, polars, pandas, httpx, redis, chromadb, ollama, pytest, pytest-asyncio
- `backend/app/__init__.py`
- `backend/app/main.py` — FastAPI app with health check `/api/health`
- `backend/app/config.py` — Pydantic Settings class reading from env vars
- `backend/app/database.py` — Async SQLAlchemy engine + sessionmaker + Base
- `backend/alembic.ini` + `backend/alembic/env.py` — Alembic configured for async

**Frontend skeleton:**
- `frontend/Dockerfile` — Node 20-alpine, next build, next start
- `frontend/package.json` — next, react, typescript, tailwindcss, @shadcn/ui deps
- `frontend/next.config.js` — API proxy rewrite to backend
- `frontend/tailwind.config.ts`
- `frontend/tsconfig.json`
- `frontend/src/app/layout.tsx` — Root layout with sidebar shell
- `frontend/src/app/page.tsx` — Placeholder dashboard

**Nginx:**
- `nginx/nginx.conf` — Reverse proxy: `/api/*` → backend:8000, `/*` → frontend:3000

### Acceptance Criteria
- `docker compose up` starts all 5 services (postgres, redis, backend, frontend, nginx)
- `GET /api/health` returns `{"status": "ok"}`
- Frontend loads at `http://localhost:3000` showing the layout shell
- Database is reachable from backend

---

## PHASE 1: Data Models & Database Migrations

### Objective
Define all SQLAlchemy ORM models for the entire system and generate Alembic migrations. This is the data foundation everything else builds on.

### Models to Create

#### `backend/app/models/provider.py`
```python
class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int]                        # PK
    npi: Mapped[str]                       # National Provider Identifier (10 digits)
    name: Mapped[str]
    specialty: Mapped[str]                 # e.g. "Orthopedic Surgery", "Family Medicine"
    taxonomy_code: Mapped[str | None]
    practice_address: Mapped[str | None]
    practice_city: Mapped[str | None]
    practice_state: Mapped[str]            # 2-letter state code
    practice_zip: Mapped[str | None]
    phone: Mapped[str | None]
    entity_type: Mapped[str]               # "individual" | "organization"
    is_active: Mapped[bool]                # default True
    oig_excluded: Mapped[bool]             # default False — on OIG exclusion list?
    dea_registration: Mapped[str | None]   # DEA number (for prescribers)
    dea_schedule: Mapped[str | None]       # "II", "III", etc.
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[int]
    npi: Mapped[str]
    name: Mapped[str]
    chain_name: Mapped[str | None]         # "CVS", "Walgreens", etc.
    address: Mapped[str]
    city: Mapped[str]
    state: Mapped[str]
    zip_code: Mapped[str]
    phone: Mapped[str | None]
    pharmacy_type: Mapped[str]             # "retail" | "mail_order" | "specialty" | "compounding"
    is_active: Mapped[bool]
    oig_excluded: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

#### `backend/app/models/member.py`
```python
class Member(Base):
    __tablename__ = "members"

    id: Mapped[int]
    member_id: Mapped[str]                 # External member ID (e.g. "MBR-100001")
    first_name: Mapped[str]
    last_name: Mapped[str]
    date_of_birth: Mapped[date]
    gender: Mapped[str]                    # "M" | "F"
    address: Mapped[str | None]
    city: Mapped[str | None]
    state: Mapped[str]
    zip_code: Mapped[str]
    plan_id: Mapped[str]                   # Insurance plan identifier
    plan_type: Mapped[str]                 # "MA" | "Commercial" | "Medicaid"
    eligibility_start: Mapped[date]
    eligibility_end: Mapped[date | None]   # NULL = still active
    is_active: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

#### `backend/app/models/claim.py`
```python
class MedicalClaim(Base):
    __tablename__ = "medical_claims"

    id: Mapped[int]
    claim_id: Mapped[str]                  # Unique claim identifier (e.g. "MCL-2025-000001")
    member_id: Mapped[int]                 # FK → members.id
    provider_id: Mapped[int]              # FK → providers.id (rendering/billing provider)
    referring_provider_id: Mapped[int | None]  # FK → providers.id
    service_date: Mapped[date]
    admission_date: Mapped[date | None]    # For inpatient
    discharge_date: Mapped[date | None]    # For inpatient
    place_of_service: Mapped[str]          # "11"=office, "21"=inpatient, "23"=ER, "02"=telehealth
    claim_type: Mapped[str]                # "professional" | "institutional" | "dental"
    cpt_code: Mapped[str]                  # CPT/HCPCS procedure code
    cpt_modifier: Mapped[str | None]       # e.g. "25", "59", "76"
    diagnosis_code_primary: Mapped[str]    # ICD-10 primary dx
    diagnosis_code_2: Mapped[str | None]
    diagnosis_code_3: Mapped[str | None]
    diagnosis_code_4: Mapped[str | None]
    amount_billed: Mapped[Decimal]         # What provider charged
    amount_allowed: Mapped[Decimal | None] # What plan allows
    amount_paid: Mapped[Decimal | None]    # What plan paid
    units: Mapped[int]                     # Service units
    length_of_stay: Mapped[int | None]     # Inpatient days
    drg_code: Mapped[str | None]           # Diagnosis Related Group (inpatient)
    revenue_code: Mapped[str | None]       # For institutional claims
    status: Mapped[str]                    # "received" | "processed" | "flagged" | "paid" | "denied"
    batch_id: Mapped[str | None]           # Ingestion batch identifier
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    member: Mapped["Member"] = relationship()
    provider: Mapped["Provider"] = relationship(foreign_keys=[provider_id])
    referring_provider: Mapped["Provider"] = relationship(foreign_keys=[referring_provider_id])


class PharmacyClaim(Base):
    __tablename__ = "pharmacy_claims"

    id: Mapped[int]
    claim_id: Mapped[str]                  # e.g. "RX-2025-000001"
    member_id: Mapped[int]                 # FK → members.id
    pharmacy_id: Mapped[int]              # FK → pharmacies.id
    prescriber_id: Mapped[int]            # FK → providers.id (prescribing doctor)
    fill_date: Mapped[date]
    ndc_code: Mapped[str]                  # 11-digit National Drug Code
    drug_name: Mapped[str]
    drug_class: Mapped[str | None]         # Therapeutic class
    is_generic: Mapped[bool]
    is_controlled: Mapped[bool]
    dea_schedule: Mapped[str | None]       # "II", "III", "IV", "V" or NULL
    quantity_dispensed: Mapped[Decimal]
    days_supply: Mapped[int]
    refill_number: Mapped[int]             # 0 = original, 1+ = refill
    amount_billed: Mapped[Decimal]
    amount_allowed: Mapped[Decimal | None]
    amount_paid: Mapped[Decimal | None]
    copay: Mapped[Decimal | None]
    prescriber_npi: Mapped[str]
    pharmacy_npi: Mapped[str]
    prior_auth: Mapped[bool]               # Prior authorization obtained?
    status: Mapped[str]
    batch_id: Mapped[str | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    member: Mapped["Member"] = relationship()
    pharmacy: Mapped["Pharmacy"] = relationship()
    prescriber: Mapped["Provider"] = relationship()
```

#### `backend/app/models/rule.py`
```python
class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int]
    rule_id: Mapped[str]                   # "M1", "M2", ..., "P1", "P2", ...
    category: Mapped[str]                  # "Upcoding", "Unbundling", "Phantom Billing", etc.
    fraud_type: Mapped[str]                # "Fraud" | "Waste" | "Abuse"
    claim_type: Mapped[str]                # "medical" | "pharmacy"
    description: Mapped[str]               # Human-readable description
    detection_logic: Mapped[str]           # Short logic description
    enabled: Mapped[bool]                  # default True
    weight: Mapped[Decimal]                # 1.0 - 10.0 (importance)
    thresholds: Mapped[dict]               # JSONB — rule-specific config (varies per rule)
    benchmark_source: Mapped[str | None]   # "CMS_fee_schedule", "NDC_directory", etc.
    implementation_priority: Mapped[str]   # "HIGH", "MEDIUM", "LOW"
    version: Mapped[int]                   # Incremented on threshold changes
    last_modified_by: Mapped[str | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[int]
    claim_id: Mapped[str]                  # The claim that was evaluated
    claim_type: Mapped[str]                # "medical" | "pharmacy"
    rule_id: Mapped[str]                   # FK conceptual → rules.rule_id
    triggered: Mapped[bool]
    severity: Mapped[Decimal | None]       # 0.0 - 3.0 severity multiplier
    confidence: Mapped[Decimal | None]     # 0.3 - 1.0 confidence factor
    evidence: Mapped[dict]                 # JSONB — structured evidence
    details: Mapped[str | None]            # Human-readable explanation
    evaluated_at: Mapped[datetime]
    batch_id: Mapped[str | None]
```

#### `backend/app/models/scoring.py`
```python
class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int]
    claim_id: Mapped[str]
    claim_type: Mapped[str]
    total_score: Mapped[Decimal]           # 0-100 normalized
    risk_level: Mapped[str]                # "low" | "medium" | "high" | "critical"
    rules_triggered: Mapped[int]           # Count of triggered rules
    rule_contributions: Mapped[dict]       # JSONB — {rule_id: contribution_score}
    confidence_factor: Mapped[Decimal]     # Overall confidence
    scored_at: Mapped[datetime]
    batch_id: Mapped[str | None]
```

#### `backend/app/models/case.py`
```python
class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[int]
    case_id: Mapped[str]                   # "CASE-2025-000001"
    claim_id: Mapped[str]
    claim_type: Mapped[str]
    risk_score: Mapped[Decimal]
    risk_level: Mapped[str]
    status: Mapped[str]                    # "open" | "under_review" | "resolved" | "closed" | "escalated"
    priority: Mapped[str]                  # "P1" | "P2" | "P3" | "P4"
    assigned_to: Mapped[str | None]        # Investigator name/email
    resolution_path: Mapped[str | None]    # "provider_accepts" | "provider_disputes" | "plan_benefit_issue" | "no_response" | "complex_case"
    resolution_notes: Mapped[str | None]
    estimated_fraud_amount: Mapped[Decimal | None]
    recovery_amount: Mapped[Decimal | None]
    sla_deadline: Mapped[datetime | None]
    created_at: Mapped[datetime]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]

    # Relationships
    notes: Mapped[list["CaseNote"]] = relationship(back_populates="case")
    evidence: Mapped[list["CaseEvidence"]] = relationship(back_populates="case")


class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[int]
    case_id: Mapped[int]                   # FK → investigation_cases.id
    author: Mapped[str]                    # "system" | "investigator" | "agent"
    content: Mapped[str]
    created_at: Mapped[datetime]

    case: Mapped["InvestigationCase"] = relationship(back_populates="notes")


class CaseEvidence(Base):
    __tablename__ = "case_evidence"

    id: Mapped[int]
    case_id: Mapped[int]
    evidence_type: Mapped[str]             # "rule_trigger" | "benchmark_comparison" | "pattern_analysis" | "agent_finding"
    title: Mapped[str]
    content: Mapped[dict]                  # JSONB — structured evidence data
    created_at: Mapped[datetime]

    case: Mapped["InvestigationCase"] = relationship(back_populates="evidence")
```

#### `backend/app/models/audit.py`
```python
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int]
    event_id: Mapped[str]                  # UUID
    event_type: Mapped[str]                # "claim_ingested" | "rule_evaluated" | "score_calculated" | "case_created" | "case_updated" | "rule_config_changed" | "agent_action"
    actor: Mapped[str]                     # "system" | "admin@example.com" | "agent:investigator"
    action: Mapped[str]                    # Human-readable action description
    resource_type: Mapped[str | None]      # "claim" | "rule" | "case"
    resource_id: Mapped[str | None]        # The ID of the affected resource
    details: Mapped[dict]                  # JSONB — full event details
    previous_hash: Mapped[str | None]      # SHA-256 of previous entry (chain integrity)
    current_hash: Mapped[str]              # SHA-256 of this entry
    created_at: Mapped[datetime]

    # NOTE: This table has NO update/delete — append-only via trigger/policy
```

#### `backend/app/models/reference.py`
```python
class NDCReference(Base):
    """National Drug Code directory — seeded from CMS data"""
    __tablename__ = "ndc_reference"

    id: Mapped[int]
    ndc_code: Mapped[str]                  # 11-digit NDC
    proprietary_name: Mapped[str]          # Brand name
    nonproprietary_name: Mapped[str]       # Generic name
    dosage_form: Mapped[str]               # "TABLET", "CAPSULE", "SOLUTION"
    route: Mapped[str]                     # "ORAL", "INJECTABLE", "TOPICAL"
    substance_name: Mapped[str | None]
    dea_schedule: Mapped[str | None]       # "CII", "CIII", "CIV", "CV"
    therapeutic_class: Mapped[str | None]
    avg_wholesale_price: Mapped[Decimal | None]  # AWP benchmark
    unit_price: Mapped[Decimal | None]


class CPTReference(Base):
    """CPT/HCPCS code reference with CMS fee schedule benchmarks"""
    __tablename__ = "cpt_reference"

    id: Mapped[int]
    cpt_code: Mapped[str]
    description: Mapped[str]
    category: Mapped[str]                  # "E&M", "Surgery", "Radiology", "Lab", "Medicine"
    facility_price: Mapped[Decimal | None]     # CMS facility rate
    non_facility_price: Mapped[Decimal | None] # CMS non-facility rate
    rvu_work: Mapped[Decimal | None]       # Work RVU
    rvu_practice: Mapped[Decimal | None]   # Practice expense RVU
    rvu_malpractice: Mapped[Decimal | None]
    global_period: Mapped[str | None]      # "000", "010", "090", "XXX", "ZZZ"
    # Bundling relationships
    bundled_codes: Mapped[dict | None]     # JSONB — codes that should be bundled with this one


class ICDReference(Base):
    """ICD-10-CM diagnosis code reference"""
    __tablename__ = "icd_reference"

    id: Mapped[int]
    icd_code: Mapped[str]                  # e.g. "E11.9"
    description: Mapped[str]               # e.g. "Type 2 diabetes mellitus without complications"
    category: Mapped[str]                  # Chapter/category
    is_billable: Mapped[bool]              # Can be used on a claim
    # Valid CPT associations for medical necessity
    valid_cpt_codes: Mapped[dict | None]   # JSONB — CPT codes valid for this diagnosis
    gender_specific: Mapped[str | None]    # "M" | "F" | None (for clinical appropriateness)
    age_range_min: Mapped[int | None]      # Minimum appropriate age
    age_range_max: Mapped[int | None]      # Maximum appropriate age
```

### Acceptance Criteria
- `alembic upgrade head` creates all tables in PostgreSQL
- All models have proper foreign keys and relationships
- JSONB columns work for flexible data (thresholds, evidence, details)
- Audit log table has an INSERT-only policy (no UPDATE/DELETE)

---

## PHASE 2: Synthetic Data Generator

### Objective
Generate realistic, scenario-driven synthetic data that exercises all 29 fraud rules. This data is the backbone of every demo and test. Without it, nothing else is demonstrable.

### Data Volume Targets
| Entity | Count | Notes |
|--------|-------|-------|
| Providers | 200 | Mix of specialties, ~15 are "bad actors" |
| Pharmacies | 50 | Mix of retail, mail-order, specialty, compounding |
| Members | 2,000 | Mix of ages, genders, plan types |
| Medical Claims | 15,000 | ~12 months of claims, ~20% have fraud signals |
| Pharmacy Claims | 20,000 | ~12 months, ~20% have fraud signals |
| NDC Reference | 500 | Top drugs by claims volume |
| CPT Reference | 300 | Common E&M, surgery, radiology, lab codes |
| ICD-10 Reference | 400 | Common diagnosis codes |

### Fraud Scenario Injection (Critical)
For each rule, we inject **specific known fraud patterns** into the data so the rule engine has something to detect.

#### Medical Fraud Scenarios to Inject:

| Rule | Scenario | How Injected |
|------|----------|--------------|
| **M1: Upcoding** | Provider bills 99215 (high-complexity office visit) but diagnosis is simple (E11.9 diabetes check). Billed $350 when CMS expects $145. | 5 providers systematically bill highest E&M code. ~200 claims with billed > 2x CMS rate. |
| **M2: Unbundling** | Provider bills CPT 80048 (basic metabolic panel) as 8 separate tests (82310, 82374, 82435, etc.) | 3 lab providers split panel codes across 2-3 claims on same date of service. ~80 claim clusters. |
| **M3: Duplicate Billing** | Same provider, same patient, same CPT, same date — submitted twice with different claim IDs. | 4 providers have ~100 duplicate claim pairs (exact match on member+provider+CPT+date). |
| **M4: Phantom Billing** | Claims for services on dates when provider had no other activity. Patient had no other claims that week. No corroborating evidence. | 2 "ghost" providers with claims but no pattern of real practice. ~60 phantom claims. |
| **M5: Kickback/Self-Referral** | Provider A refers exclusively to Provider B (lab). >90% of Provider A's referrals go to one entity. | 3 provider pairs with >85% referral concentration. ~150 claims in referral network. |
| **M6: Medically Unnecessary** | Knee MRI (73721) ordered for diagnosis of common cold (J00). CPT-ICD mismatch. | 4 providers order expensive imaging for unrelated diagnoses. ~100 claims. |
| **M7: Provider Collusion** | Two providers billing for same patient on same day for overlapping services. Possible coordinated billing. | 2 provider pairs bill complementary codes for shared patients on same dates. ~40 claim pairs. |
| **M8: Modifier Misuse** | Modifier 25 (separately identifiable E&M) used on >80% of claims. Industry norm is ~30%. | 3 providers overuse modifier 25 or 59 beyond statistical norms. ~120 claims. |
| **M9: Copay Waiver** | Provider's billed amounts always equal allowed amounts (never collects copay). Pattern over 6+ months. | 2 providers with amount_billed == amount_allowed on 95%+ of claims. ~180 claims. |
| **M10: IP/OP Misclass** | Inpatient admission (place_of_service=21) with length_of_stay=0 or 1 day for procedures normally done outpatient. | 2 facilities have short-stay inpatient claims for common outpatient procedures. ~50 claims. |
| **M11: DME Fraud** | DME supplier billing expensive power wheelchairs (K0856) for patients who also have claims for running/gym visits. | 1 DME supplier with high-cost equipment claims for mobile patients. ~30 claims. |
| **M12: Lab/Diagnostic Abuse** | Provider orders full blood panel for every single visit regardless of diagnosis. >95% of visits have lab orders. | 3 providers with lab claim on >90% of office visits. ~200 claims. |
| **M13: Provider Ghosting** | Provider NPI is inactive/expired in NPPES but claims are still being submitted. | 2 providers with is_active=False but claims within last 3 months. ~40 claims. |
| **M14: Double Dipping** | Same service billed to two different payers (Medicare + Commercial) for same patient and date. | 1 provider billing claims with overlapping payer submissions. ~25 claims. |
| **M15: Telehealth Fraud** | Telehealth visit (place_of_service=02) billed at in-person rates. Volume of telehealth visits exceeds capacity (>50/day). | 2 providers with >40 telehealth claims/day and in-person pricing. ~100 claims. |
| **M16: Chart Padding** | Excessive diagnosis codes per claim (>8 ICD-10 codes per encounter). Inflating complexity. | 2 providers with avg 6+ dx codes when specialty norm is 2-3. ~80 claims. |

#### Pharmacy Fraud Scenarios to Inject:

| Rule | Scenario | How Injected |
|------|----------|--------------|
| **P1: Prescription Forgery** | Prescriber NPI on claim doesn't match any known prescriber. Or prescriber is deceased/inactive. | 30 claims with non-existent or inactive prescriber NPIs. |
| **P2: Doctor Shopping** | Member visits 5+ different prescribers in 90 days for same controlled substance (opioids). | 10 members with 5+ unique prescribers for Schedule II drugs in rolling 90-day window. ~80 claims. |
| **P3: Pharmacy Shopping** | Member fills same drug at 4+ different pharmacies in 60 days. | 8 members using 4+ pharmacies for same medication. ~60 claims. |
| **P4: Early Refill** | 30-day supply filled, then refill requested at day 15 (50% of days_supply). | 200 pharmacy claims where days_since_last_fill < 75% of days_supply. |
| **P5: Controlled Substance Diversion** | Single prescriber writing >90% controlled substance Rx. Normal is ~15-25%. | 3 prescribers where >80% of their Rx claims are Schedule II-III. ~150 claims. |
| **P6: Phantom Claims** | Pharmacy bills for drugs dispensed to member who has no medical claims (never visits a doctor) and no active eligibility. | 1 pharmacy billing for 20 members with no medical claim history. ~60 phantom Rx claims. |
| **P7: High-Cost Substitution** | Pharmacy dispenses brand-name drug (is_generic=False) but a generic equivalent exists and costs 80% less. | 2 pharmacies consistently dispensing brand over generic. ~100 claims. |
| **P8: Kickback/Split Billing** | Provider refers >80% of prescriptions to single pharmacy. | 3 prescriber-pharmacy pairs with referral concentration >80%. ~120 claims. |
| **P9: Invalid Prescriber** | Prescriber NPI not licensed for controlled substances (no DEA) but prescribing Schedule II. | 20 claims where prescriber lacks DEA registration for controlled substance. |
| **P10: Stockpiling** | Member accumulates 6+ months supply of a drug in a 3-month window. | 10 members with cumulative days_supply > 2x the calendar days. ~50 claims. |
| **P11: Compound Drug Fraud** | Compounding pharmacy billing $5,000+ per claim for compound drugs. Top 1% by cost. | 1 compounding pharmacy with avg claim >$3,000. ~25 claims. |
| **P12: Phantom Members** | Claims submitted for members with eligibility_end in the past. | 15 members with expired eligibility but pharmacy claims after eligibility_end. ~40 claims. |
| **P13: Pharmacy-Provider Collusion** | Same pharmacy and same provider generate abnormally high claim volume relative to peers. | 2 pharmacy-provider pairs with 3x the avg claim volume. ~80 claims. |

### Generator Architecture
- `backend/app/seed/synthetic_data.py` — Master orchestrator: calls all sub-generators, injects fraud, seeds DB
- `backend/app/seed/reference_data.py` — Realistic NDC, CPT, ICD-10 codes with prices
- `backend/app/seed/providers.py` — 200 providers with specialties, NPIs, DEA, some flagged
- `backend/app/seed/members.py` — 2,000 members with demographic distributions
- `backend/app/seed/claims_medical.py` — 15K claims, injecting M1-M16 scenarios
- `backend/app/seed/claims_pharmacy.py` — 20K claims, injecting P1-P13 scenarios
- `backend/app/seed/fraud_scenarios.py` — Configuration of all fraud patterns (which providers, which members, what volumes)

### CLI Command
```bash
python -m app.seed.synthetic_data          # Seed everything
python -m app.seed.synthetic_data --clean  # Drop + re-seed
```

### Acceptance Criteria
- All 7 entity types populated with target counts
- Each of the 29 rules has at least one detectable fraud scenario in the data
- Clean (non-fraudulent) claims outnumber fraudulent ~4:1
- Reference data (NDC, CPT, ICD) is realistic enough for demo
- Seed process is idempotent (re-runnable)
- Takes < 60 seconds to generate all data

---

## PHASE 3: Data Ingestion Pipeline

### Objective
Build the service that takes raw claims data (CSV upload or batch) and loads them into the database with validation, deduplication, and audit logging.

### `backend/app/services/ingestion.py`

**Core Functions:**
```
async def ingest_medical_claims(file_or_records, batch_id) -> IngestionResult
async def ingest_pharmacy_claims(file_or_records, batch_id) -> IngestionResult
async def validate_claim(claim_data, claim_type) -> list[ValidationError]
async def deduplicate(claim_data, claim_type) -> bool  # True if duplicate
```

**Validation Rules:**
- Required fields present (claim_id, member_id, provider_id, service_date, amount_billed, cpt_code/ndc_code)
- Amount fields are positive numbers
- Date fields are valid dates and not in the future
- CPT/NDC codes exist in reference tables
- Member exists and has active eligibility on service date
- Provider/pharmacy exists

**Deduplication:**
- Hash on (member_id + provider_id + service_date + cpt_code/ndc_code + amount_billed)
- If duplicate found, skip and log

**Audit:**
- Log every batch: batch_id, count, success_count, error_count, timestamp
- Log validation errors with claim details

### API Endpoint
```
POST /api/claims/ingest
  Body: { "claim_type": "medical"|"pharmacy", "data": [...] }
  Response: { "batch_id": "...", "total": N, "ingested": N, "errors": [...] }

POST /api/claims/upload
  Body: multipart/form-data with CSV file
  Response: same as above
```

### Acceptance Criteria
- Can ingest 10K claims in < 30 seconds
- Rejects invalid claims with clear error messages
- Deduplicates exact matches
- Every ingestion is audit-logged
- Works with both JSON payload and CSV upload

---

## PHASE 4: Data Enrichment Pipeline

### Objective
After claims are ingested, enrich them with reference data lookups and cross-references needed by the rule engine.

### `backend/app/services/enrichment.py`

**Enrichment Steps (run in sequence per claim):**

1. **CPT/NDC Lookup**: Match claim's procedure/drug code to reference table → attach description, expected cost, category
2. **ICD-10 Lookup**: Match diagnosis code → attach description, gender/age appropriateness, valid CPT associations
3. **Provider Enrichment**: Look up provider → attach specialty, active status, OIG exclusion status, DEA registration
4. **Member Enrichment**: Look up member → verify eligibility on service date, attach demographics
5. **Historical Context**: Query previous claims for same member+provider:
   - Last claim date (for duplicate/frequency detection)
   - Total claims in last 30/90/365 days
   - Total $ billed in last 30/90/365 days
   - Unique providers visited (for doctor shopping)
   - Unique pharmacies used (for pharmacy shopping)
   - Last fill date for same NDC (for early refill)
   - Cumulative days_supply for same NDC in last 90 days (for stockpiling)
6. **Provider Pattern Stats**: Aggregated stats for the billing provider:
   - Total claims in period
   - Avg claims per day
   - Modifier usage rate (% of claims with modifier 25, 59)
   - Referral concentration (% of referrals to single entity)
   - Controlled substance Rx rate (for prescribers)
   - Telehealth volume per day

**Output:** `EnrichedClaim` dataclass with all original fields + enrichment fields attached

### Acceptance Criteria
- Enrichment runs in < 100ms per claim (batch: < 30s for 10K)
- All 6 enrichment steps produce data needed by rules
- Historical lookups are correct (verified against seed data)
- Missing reference data is handled gracefully (flag, don't crash)

---

## PHASE 5: Rule Engine — All 29 Rules

### Objective
Implement every one of the 29 FWA detection rules as a pluggable, configurable class. This is the heart of the system.

### Architecture

#### `backend/app/rules/base.py`
```python
class BaseRule(ABC):
    """Abstract base for all FWA detection rules"""

    rule_id: str           # "M1", "P4", etc.
    category: str
    fraud_type: str        # "Fraud" | "Waste" | "Abuse"
    claim_type: str        # "medical" | "pharmacy"
    default_weight: float
    default_thresholds: dict

    @abstractmethod
    async def evaluate(self, claim: EnrichedClaim, config: RuleConfig) -> RuleEvaluation:
        """
        Evaluate a single enriched claim against this rule.
        Returns RuleEvaluation with: triggered, severity, confidence, evidence, details
        """
        pass

    def calculate_severity(self, deviation: float, thresholds: dict) -> float:
        """Graduated severity: 0.1 to 3.0 based on how far from threshold"""
        pass

    def calculate_confidence(self, claim: EnrichedClaim) -> float:
        """Data completeness factor: 0.3 to 1.0"""
        pass
```

#### `backend/app/services/rule_engine.py`
```python
class RuleEngine:
    """Orchestrates rule evaluation across all registered rules"""

    def __init__(self):
        self.rules: dict[str, BaseRule] = {}   # Loaded at startup
        self.configs: dict[str, RuleConfig] = {}  # From DB (admin-configurable)

    async def load_rules(self):
        """Discover and register all rule implementations"""

    async def load_configs(self):
        """Load rule configs (weights, thresholds, enabled/disabled) from DB"""

    async def evaluate_claim(self, claim: EnrichedClaim) -> list[RuleResult]:
        """Run all enabled rules against a single claim"""

    async def evaluate_batch(self, claims: list[EnrichedClaim]) -> dict[str, list[RuleResult]]:
        """Run all rules against a batch of claims"""
```

### Rule Specifications (All 29)

Below is the **exact detection logic** for each rule. Thresholds are admin-configurable defaults.

---

#### M1: Upcoding (Weight: 9.0)
**Logic:** `amount_billed > CMS_expected_cost × (1 + threshold_percent/100)` AND `amount_billed - CMS_expected_cost > threshold_amount`
**Default Thresholds:** `{"percent_over": 20, "min_dollar_amount": 300, "benchmark": "CMS_fee_schedule"}`
**Severity Calc:** Graduated by overpayment ratio: <10%→0.5, 10-25%→1.0, 25-50%→1.8, >50%→3.0
**Evidence:** `{"billed": X, "expected": Y, "overpayment_pct": Z, "cpt_code": "...", "benchmark_source": "..."}`

#### M2: Unbundling (Weight: 7.5)
**Logic:** Multiple CPT codes billed on same date for same member that should be a single bundled code. Check `cpt_reference.bundled_codes` — if claim A's CPT is in claim B's bundled_codes list (same member, same date, same provider), flag both.
**Default Thresholds:** `{"min_component_count": 2, "lookback_days": 0}` (same day)
**Severity Calc:** By number of components unbundled: 2→1.0, 3→1.5, 4+→2.5
**Evidence:** `{"bundled_code": "80048", "component_codes": ["82310","82374",...], "claims": [...]}`

#### M3: Duplicate Billing (Weight: 8.0)
**Logic:** Two claims with same (member_id + provider_id + cpt_code + service_date) but different claim_ids. Allow modifier exceptions (modifier "76" = repeat procedure — legitimate).
**Default Thresholds:** `{"exact_match": true, "exclude_modifiers": ["76","77"]}`
**Severity Calc:** By dollar amount: <$200→0.5, $200-$1000→1.0, $1000-$5000→2.0, >$5000→3.0
**Evidence:** `{"original_claim": "...", "duplicate_claim": "...", "amount": X, "date": "..."}`

#### M4: Phantom Billing (Weight: 10.0)
**Logic:** Claims from a provider with < N other claims in the same 30-day period AND member has no other claims within 7 days of the service date (no corroborating evidence of actual visit).
**Default Thresholds:** `{"min_provider_claims_period": 5, "corroboration_window_days": 7}`
**Severity Calc:** Always high (2.0) if triggered; 3.0 if provider has NO other claims at all.
**Evidence:** `{"provider_claim_count_30d": N, "member_corroborating_claims": 0, "claim_amount": X}`

#### M5: Kickback/Self-Referral (Weight: 9.5)
**Logic:** Provider A has >X% of their referrals going to a single Provider B. Calculate `referral_concentration = claims_referred_to_B / total_referred_claims`.
**Default Thresholds:** `{"concentration_pct": 80, "min_referral_count": 10}`
**Severity Calc:** By concentration: 80-90%→1.0, 90-95%→2.0, >95%→3.0
**Evidence:** `{"referring_provider": "...", "receiving_provider": "...", "concentration": X, "total_referrals": N}`

#### M6: Medically Unnecessary (Weight: 7.0)
**Logic:** Claim's CPT code is NOT in the `valid_cpt_codes` list for the primary ICD-10 diagnosis in `icd_reference`. Also flag gender mismatches (e.g., prostate exam for female member).
**Default Thresholds:** `{"require_cpt_icd_match": true, "check_gender": true, "check_age": true}`
**Severity Calc:** Gender mismatch→3.0, CPT-ICD mismatch→1.5, Age mismatch→1.0
**Evidence:** `{"cpt_code": "...", "diagnosis": "...", "reason": "CPT not valid for diagnosis", "member_gender": "...", "member_age": N}`

#### M7: Provider Collusion (Weight: 6.5)
**Logic:** Two different providers billing the same member on the same date with overlapping/complementary service codes AND these two providers frequently co-bill (>N shared patients).
**Default Thresholds:** `{"min_shared_patients": 5, "same_day_required": true}`
**Severity Calc:** By shared patient count: 5-10→0.8, 10-20→1.5, >20→2.5
**Evidence:** `{"provider_a": "...", "provider_b": "...", "shared_patients": N, "co_billing_dates": [...]}`

#### M8: Modifier Misuse (Weight: 5.5)
**Logic:** Provider uses modifier 25 or 59 on > X% of their claims. Industry benchmark is ~30% for modifier 25.
**Default Thresholds:** `{"modifier_25_max_pct": 40, "modifier_59_max_pct": 35, "min_claims_for_pattern": 20}`
**Severity Calc:** By overuse: 40-60%→0.8, 60-80%→1.5, >80%→2.5
**Evidence:** `{"modifier": "25", "usage_rate": X, "benchmark_rate": 30, "total_claims": N}`

#### M9: Copay Waiver (Weight: 2.5)
**Logic:** Provider's claims have `amount_billed == amount_allowed` on > X% of claims over a 6+ month period (indicating routine copay waiver).
**Default Thresholds:** `{"waiver_pct": 90, "min_months": 6, "min_claims": 30}`
**Severity Calc:** By waiver rate: 90-95%→0.5, 95-99%→1.0, 100%→1.5
**Evidence:** `{"waiver_rate": X, "total_claims": N, "period_months": M}`

#### M10: Inpatient/Outpatient Misclassification (Weight: 6.0)
**Logic:** Claim has `place_of_service=21` (inpatient) but `length_of_stay <= 1` AND procedure is normally outpatient (defined in CPT reference).
**Default Thresholds:** `{"max_los_for_flag": 1, "outpatient_cpt_list": "from_reference"}`
**Severity Calc:** By cost difference: <$1000→0.5, $1000-$5000→1.5, >$5000→2.5
**Evidence:** `{"place_of_service": "21", "los": N, "procedure": "...", "expected_setting": "outpatient"}`

#### M11: DME Fraud (Weight: 6.0)
**Logic:** DME claim (HCPCS K-codes or E-codes) for high-cost equipment AND member has activity patterns inconsistent with need (e.g., claims showing physical activity).
**Default Thresholds:** `{"min_dme_amount": 1000, "check_contradicting_claims": true}`
**Severity Calc:** By amount: $1K-$5K→1.0, $5K-$15K→2.0, >$15K→3.0
**Evidence:** `{"dme_item": "...", "amount": X, "contradicting_claims": [...]}`

#### M12: Lab/Diagnostic Abuse (Weight: 5.0)
**Logic:** Provider orders lab/diagnostic tests on > X% of office visits (CPT 99201-99215). Industry norm is ~40-50%.
**Default Thresholds:** `{"lab_rate_max_pct": 70, "min_visits_for_pattern": 20}`
**Severity Calc:** By overuse: 70-85%→0.8, 85-95%→1.5, >95%→2.5
**Evidence:** `{"lab_order_rate": X, "benchmark": 45, "total_visits": N, "visits_with_labs": M}`

#### M13: Provider Ghosting (Weight: 7.0)
**Logic:** Provider has `is_active=False` OR `oig_excluded=True` but has claims submitted after their deactivation/exclusion date.
**Default Thresholds:** `{"check_active_status": true, "check_oig_exclusion": true}`
**Severity Calc:** OIG excluded→3.0, Inactive→2.0
**Evidence:** `{"provider_npi": "...", "active_status": false, "exclusion_status": true, "claims_after_date": [...]}`

#### M14: Double Dipping (Weight: 7.0)
**Logic:** Same member + same service_date + same CPT code but submitted with two different `plan_id` values (billing two payers for same service).
**Default Thresholds:** `{"require_same_cpt": true, "require_same_date": true}`
**Severity Calc:** By amount: <$500→1.0, $500-$2000→2.0, >$2000→3.0
**Evidence:** `{"claim_a": "...", "claim_b": "...", "payer_a": "...", "payer_b": "...", "service": "..."}`

#### M15: Telehealth Fraud (Weight: 6.0)
**Logic:** (a) Telehealth visit (`place_of_service=02`) billed at non-facility rate when it should be facility rate. OR (b) Provider has >N telehealth claims per day.
**Default Thresholds:** `{"max_telehealth_per_day": 40, "check_pricing": true}`
**Severity Calc:** Volume >40→1.0, >60→2.0, >80→3.0; Pricing mismatch→1.5
**Evidence:** `{"telehealth_count_day": N, "date": "...", "pricing_issue": true/false}`

#### M16: Chart Padding (Weight: 4.0)
**Logic:** Claim has >N distinct diagnosis codes. Normal is 2-4 per encounter for most specialties.
**Default Thresholds:** `{"max_diagnosis_codes": 6, "specialty_overrides": {"oncology": 8, "internal_medicine": 6}}`
**Severity Calc:** By count over threshold: 1-2 over→0.5, 3-4 over→1.0, 5+→2.0
**Evidence:** `{"diagnosis_count": N, "threshold": M, "codes": [...]}`

---

#### P1: Prescription Forgery (Weight: 8.0)
**Logic:** Prescriber NPI on pharmacy claim does not exist in providers table, OR prescriber `is_active=False`.
**Default Thresholds:** `{"check_active": true, "check_exists": true}`
**Severity Calc:** NPI not found→3.0, Inactive→2.0
**Evidence:** `{"prescriber_npi": "...", "status": "not_found|inactive", "drug": "...", "member": "..."}`

#### P2: Doctor Shopping (Weight: 7.5)
**Logic:** Member has prescriptions from >N unique prescribers for controlled substances (DEA Schedule II-III) within rolling X-day window.
**Default Thresholds:** `{"max_prescribers": 4, "window_days": 90, "dea_schedules": ["CII","CIII"]}`
**Severity Calc:** By prescriber count: 5→1.0, 6-7→1.5, 8+→3.0
**Evidence:** `{"member": "...", "prescriber_count": N, "prescribers": [...], "window": "90d", "drug_class": "..."}`

#### P3: Pharmacy Shopping (Weight: 3.0)
**Logic:** Member fills same drug (same NDC or same generic name) at >N unique pharmacies within X-day window.
**Default Thresholds:** `{"max_pharmacies": 3, "window_days": 60, "match_by": "generic_name"}`
**Severity Calc:** By pharmacy count: 4→0.8, 5-6→1.5, 7+→2.5
**Evidence:** `{"member": "...", "pharmacy_count": N, "pharmacies": [...], "drug": "..."}`

#### P4: Early Refill (Weight: 4.5)
**Logic:** Refill requested when `days_since_last_fill < days_supply × threshold_pct`.
**Default Thresholds:** `{"early_pct": 75}` (refill at 75% or less of expected day)
**Severity Calc:** By how early: borderline (70-75%)→0.3, somewhat (50-70%)→0.8, very (30-50%)→1.5, extreme (<30%)→2.5
**Evidence:** `{"days_supply": N, "days_since_last_fill": M, "expected_refill_day": D, "drug": "..."}`

#### P5: Controlled Substance Diversion (Weight: 9.5)
**Logic:** Prescriber has >X% of their total prescriptions being controlled substances (Schedule II-III). Normal is ~15-25%.
**Default Thresholds:** `{"max_controlled_pct": 60, "min_prescriptions": 20, "dea_schedules": ["CII","CIII"]}`
**Severity Calc:** By rate: 60-75%→1.0, 75-90%→2.0, >90%→3.0
**Evidence:** `{"prescriber_npi": "...", "controlled_rate": X, "total_rx": N, "controlled_rx": M}`

#### P6: Phantom Claims (Pharmacy) (Weight: 10.0)
**Logic:** Pharmacy claim for a member who has ZERO medical claims in the last X days (never visits a doctor but gets drugs) OR member eligibility has expired.
**Default Thresholds:** `{"no_medical_claims_days": 180, "check_eligibility": true}`
**Severity Calc:** No medical claims ever→3.0, No recent claims→2.0, Expired eligibility→2.5
**Evidence:** `{"member": "...", "last_medical_claim": "never|date", "eligibility_end": "...", "pharmacy_claims": N}`

#### P7: High-Cost Substitution/Upcoding (Weight: 5.5)
**Logic:** Pharmacy dispenses brand-name drug (`is_generic=False`) when generic equivalent exists and costs >X% less.
**Default Thresholds:** `{"cost_diff_pct": 50, "require_generic_available": true}`
**Severity Calc:** By cost difference: 50-70%→0.8, 70-85%→1.5, >85%→2.5
**Evidence:** `{"brand_drug": "...", "brand_cost": X, "generic_available": "...", "generic_cost": Y, "savings": Z}`

#### P8: Kickback/Split Billing (Weight: 6.5)
**Logic:** Prescriber sends >X% of prescriptions to a single pharmacy. Calculate referral concentration.
**Default Thresholds:** `{"concentration_pct": 80, "min_prescriptions": 15}`
**Severity Calc:** By concentration: 80-90%→1.0, 90-95%→2.0, >95%→3.0
**Evidence:** `{"prescriber": "...", "pharmacy": "...", "concentration": X, "total_rx": N}`

#### P9: Invalid Prescriber (Weight: 8.5)
**Logic:** Prescriber writes Rx for controlled substance but has no DEA registration OR DEA registration doesn't cover that schedule.
**Default Thresholds:** `{"check_dea": true, "check_schedule_match": true}`
**Severity Calc:** No DEA at all→3.0, Schedule mismatch→2.0
**Evidence:** `{"prescriber_npi": "...", "dea_status": "none|invalid", "drug_schedule": "CII", "drug": "..."}`

#### P10: Stockpiling (Weight: 4.0)
**Logic:** Member's cumulative `days_supply` for a drug over X-day window exceeds the calendar days by factor of Y (e.g., 180 days supply in 90 calendar days).
**Default Thresholds:** `{"window_days": 90, "max_supply_ratio": 1.5}`
**Severity Calc:** By ratio: 1.5-2.0→0.8, 2.0-3.0→1.5, >3.0→2.5
**Evidence:** `{"member": "...", "drug": "...", "cumulative_supply": N, "calendar_days": M, "ratio": R}`

#### P11: Compound Drug Fraud (Weight: 7.0)
**Logic:** Claim from compounding pharmacy (`pharmacy_type=compounding`) with amount > X dollars.
**Default Thresholds:** `{"max_compound_amount": 3000}`
**Severity Calc:** By amount: $3K-$5K→1.0, $5K-$10K→2.0, >$10K→3.0
**Evidence:** `{"pharmacy": "...", "pharmacy_type": "compounding", "amount": X, "drug": "..."}`

#### P12: Phantom Members (Weight: 8.0)
**Logic:** Pharmacy claim for a member whose `eligibility_end < fill_date` (no longer eligible).
**Default Thresholds:** `{"grace_period_days": 0}` (0 = strict, no grace period)
**Severity Calc:** By days past eligibility: 1-30→1.0, 31-90→2.0, >90→3.0
**Evidence:** `{"member": "...", "eligibility_end": "...", "fill_date": "...", "days_past": N}`

#### P13: Pharmacy-Provider Collusion (Weight: 6.0)
**Logic:** A specific (pharmacy, prescriber) pair generates claim volume > X standard deviations above the mean for all (pharmacy, prescriber) pairs.
**Default Thresholds:** `{"std_dev_threshold": 3.0, "min_claims": 20}`
**Severity Calc:** By std deviations: 3-4→1.0, 4-5→2.0, >5→3.0
**Evidence:** `{"pharmacy": "...", "prescriber": "...", "claim_count": N, "mean": M, "std_dev": S, "z_score": Z}`

### Acceptance Criteria
- All 29 rules implemented as classes extending BaseRule
- Each rule's thresholds are loaded from DB (admin-configurable)
- Rule engine evaluates all enabled rules against a claim batch
- Each triggered rule produces structured evidence JSON
- Severity is calculated correctly per rule spec
- Rules that aren't triggered produce no false output
- Unit tests for every rule with known-good and known-bad claims from synthetic data

---

## PHASE 6: Risk Scoring Engine

### Objective
Aggregate triggered rule results into a single 0-100 risk score per claim, classify risk level, and store results.

### `backend/app/services/scoring_engine.py`

**Algorithm (from POC spec):**
```
Total Risk Score (0-100) = Normalized( Σ (Rule_Weight × Severity_Multiplier × Confidence_Factor) )

Where:
  - Rule_Weight: From rule config (1.0 to 10.0)
  - Severity_Multiplier: How severely violated (0.1 to 3.0) — from rule evaluation
  - Confidence_Factor: Data completeness (0.3 to 1.0)

Normalization:
  - max_possible = Σ (Rule_Weight × 3.0) for all triggered rules
  - normalized = (raw_score / max_possible) × 100
  - Clamped to [0, 100]
```

**Risk Level Classification (Admin-Configurable):**
| Score Range | Level | Action |
|-------------|-------|--------|
| 0-30 | Low | Monitor only |
| 31-60 | Medium | Secondary review, batched investigation |
| 61-85 | High | Immediate investigation queue |
| 86-100 | Critical | Auto-escalation to fraud investigator |

**Confidence Factor Calculation:**
```python
def calculate_confidence(claim: EnrichedClaim) -> float:
    confidence = 1.0
    if not claim.diagnosis_code_primary: confidence *= 0.7
    if not claim.cpt_code:              confidence *= 0.6
    if not claim.provider_specialty:    confidence *= 0.8
    if not claim.length_of_stay:        confidence *= 0.9
    # Boost for corroborating evidence
    if claim.multiple_rules_triggered:  confidence *= 1.15
    return max(0.3, min(confidence, 1.0))
```

**Output:** `RiskScore` record per claim: total_score, risk_level, rules_triggered count, per-rule contributions, confidence

### Acceptance Criteria
- Score correctly calculated for claims with 0, 1, and multiple triggered rules
- Risk level thresholds are configurable (not hardcoded)
- Claims with no triggered rules get score 0 ("low")
- Score breakdown shows contribution of each rule
- Batch scoring of 10K claims in < 10 seconds

---

## PHASE 7: Governance Layer (ArqMesh, ArqGuard)

### Objective
Implement the ArqAI governance components: immutable audit trail (ArqMesh), policy enforcement (ArqGuard), and compliance evidence generation.

### 7A: Audit Service (ArqMesh) — `backend/app/services/audit_service.py`

**Core Principle:** Every action in the system is logged. Logs are immutable (append-only, hash-chained).

**Events to Log:**
| Event Type | When | Details |
|-----------|------|---------|
| `claim_ingested` | After ingestion | batch_id, claim_count, source |
| `claim_enriched` | After enrichment | claim_id, enrichment_fields |
| `rule_evaluated` | After each rule runs | claim_id, rule_id, triggered, severity |
| `score_calculated` | After scoring | claim_id, score, risk_level |
| `case_created` | When case auto-created | case_id, claim_id, risk_level |
| `case_updated` | Status change | case_id, old_status, new_status, actor |
| `case_assigned` | Investigator assigned | case_id, assigned_to |
| `rule_config_changed` | Admin changes threshold | rule_id, old_value, new_value, admin |
| `agent_action` | LLM agent performs analysis | case_id, agent_type, action, result |
| `evidence_generated` | Evidence bundle created | case_id, evidence_type |

**Hash Chain:**
```python
def calculate_hash(self, entry: dict) -> str:
    """SHA-256 hash of entry contents + previous hash"""
    content = json.dumps(entry, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()
```

**Integrity Verification:**
```python
async def verify_chain_integrity(self) -> bool:
    """Walk the chain and verify each entry's hash"""
```

### 7B: Evidence Generator — `backend/app/services/evidence_generator.py`

**Generates a compliance evidence bundle for a flagged claim/case:**
```python
async def generate_evidence_bundle(case_id: str) -> EvidenceBundle:
    """
    Returns:
      - claim_summary: Original claim details
      - rules_triggered: List of rules with evidence
      - risk_score_breakdown: How score was calculated
      - benchmark_comparisons: CMS benchmarks vs actual
      - provider_history: Provider's historical pattern
      - member_history: Member's claims history
      - audit_trail: All audit entries for this case
      - generated_at: Timestamp
      - bundle_hash: SHA-256 of entire bundle (for CMS audit)
    """
```

### Acceptance Criteria
- Every system action creates an audit entry
- Audit chain hash integrity is verifiable
- Evidence bundles contain all required data for CMS audit
- No UPDATE or DELETE possible on audit_log table
- Evidence generation completes in < 5 seconds per case

---

## PHASE 8: API Layer (FastAPI Endpoints)

### Objective
Expose all backend functionality through RESTful APIs that the frontend consumes.

### Endpoint Inventory

#### Dashboard Endpoints
```
GET  /api/dashboard/overview
  → { total_claims, total_flagged, total_fraud_amount, active_cases,
      recovery_rate, risk_distribution: {low, medium, high, critical} }

GET  /api/dashboard/trends?period=30d|90d|1y
  → { data: [{date, claims_processed, claims_flagged, fraud_amount}...] }

GET  /api/dashboard/top-providers?limit=10
  → { providers: [{npi, name, specialty, risk_score, flagged_claims, total_amount}...] }

GET  /api/dashboard/rule-effectiveness
  → { rules: [{rule_id, category, times_triggered, avg_severity, total_fraud_amount}...] }
```

#### Claims Endpoints
```
GET  /api/claims?type=medical|pharmacy&status=...&risk_level=...&page=1&size=50
  → Paginated claims list with filters

GET  /api/claims/{claim_id}
  → Full claim detail with enrichment data, rule results, risk score

POST /api/claims/ingest
  → Batch ingest claims (JSON)

POST /api/claims/upload
  → Upload CSV file

POST /api/claims/process-batch
  → Run full pipeline: enrich → evaluate rules → score → create cases
```

#### Rules Endpoints
```
GET  /api/rules
  → All rules with current config

GET  /api/rules/{rule_id}
  → Single rule detail with thresholds

PUT  /api/rules/{rule_id}/config
  → Update rule thresholds/weight/enabled (admin)
  Body: { weight, enabled, thresholds }

GET  /api/rules/{rule_id}/stats
  → Rule performance stats (trigger count, avg severity, false positive rate)
```

#### Cases Endpoints
```
GET  /api/cases?status=open|under_review|resolved|closed&priority=P1|P2&page=1&size=20
  → Investigation queue with filters + sorting

GET  /api/cases/{case_id}
  → Full case detail: claim, rule results, score, evidence, notes, timeline

PUT  /api/cases/{case_id}/status
  → Update status (open → under_review → resolved → closed)
  Body: { status, resolution_path?, resolution_notes? }

PUT  /api/cases/{case_id}/assign
  → Assign to investigator
  Body: { assigned_to }

POST /api/cases/{case_id}/notes
  → Add investigation note
  Body: { content }

GET  /api/cases/{case_id}/evidence
  → Generate and return evidence bundle
```

#### Scoring Endpoints
```
GET  /api/scoring/thresholds
  → Current risk level thresholds

PUT  /api/scoring/thresholds
  → Update thresholds (admin)
  Body: { low_max: 30, medium_max: 60, high_max: 85 }
```

#### Audit Endpoints
```
GET  /api/audit?event_type=...&actor=...&start_date=...&end_date=...&page=1&size=50
  → Paginated audit log

GET  /api/audit/integrity
  → Verify hash chain integrity
  → { valid: true/false, entries_checked: N, first_invalid: null|entry_id }
```

#### Agent Endpoints
```
POST /api/agents/investigate
  → AI agent investigates a case
  Body: { case_id, question? }
  Response: { analysis, findings, recommendations, confidence }

POST /api/agents/chat
  → Free-form agent chat for investigation
  Body: { case_id?, message }
  Response: { response, sources_cited }
```

### Acceptance Criteria
- All endpoints return proper HTTP status codes
- Pagination works on all list endpoints
- Filters work correctly
- Admin endpoints validate input
- All state-changing endpoints create audit log entries
- API docs available at `/api/docs` (Swagger)

---

## PHASE 9: Agent Layer (LLM-Powered Investigation)

### Objective
Build the AI investigation assistant using Ollama (local LLM). The agent can analyze a case, summarize findings, and provide recommendations.

### `backend/app/services/agent_service.py`

**Agent Types:**

1. **Case Investigator Agent** — Given a case, analyze all evidence and provide a narrative summary
   - Input: case_id → fetches claim, enrichment, rule results, score, provider history
   - Output: structured analysis with findings, risk assessment, recommended action
   - Prompt includes: claim data, rule evidence, provider patterns, member history, benchmark comparisons

2. **Chat Agent** — Interactive investigation assistant
   - Can answer questions about a specific case or general FWA patterns
   - Has access to DB queries via tool use (read-only)
   - Uses RAG (ChromaDB) for policy/guideline lookup

3. **Evidence Narrator Agent** — Converts structured evidence into natural language for CMS reports
   - Input: evidence bundle
   - Output: human-readable narrative suitable for compliance report

**LLM Integration:**
```python
class AgentService:
    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL  # "http://ollama:11434" or "http://host.docker.internal:11434"
        self.model = settings.LLM_MODEL        # "llama3.1" or "mistral"

    async def investigate_case(self, case_id: str) -> InvestigationResult:
        # 1. Gather all case data
        # 2. Build prompt with structured data
        # 3. Call Ollama API
        # 4. Parse response into structured findings
        # 5. Log agent action to audit trail

    async def chat(self, message: str, case_id: str | None) -> ChatResponse:
        # 1. If case_id, load case context
        # 2. RAG: query ChromaDB for relevant policies/guidelines
        # 3. Build prompt with context + user message
        # 4. Call Ollama
        # 5. Return response with sources
```

**RAG Setup (ChromaDB):**
- Collection: `fwa_policies` — CMS guidelines, fraud detection best practices, rule descriptions
- Seeded during Phase 2 with policy documents
- Queried during agent interactions for grounded responses

### Acceptance Criteria
- Agent can analyze a case and produce a coherent narrative
- Agent responses reference specific evidence from the case
- Chat agent can answer questions about FWA patterns
- All agent actions are audit-logged
- Works with Ollama running locally (no cloud dependency)
- Graceful fallback if Ollama is unavailable (show "Agent unavailable" in UI)

---

## PHASE 10: Frontend — Next.js Dashboard

### Objective
Build the complete production-quality dashboard with 6 main views.

### 10A: Layout & Navigation

**Sidebar Navigation:**
- Dashboard (home icon) — Executive Overview
- Claims (file icon) — Claims Explorer
- Cases (flag icon) — Investigation Queue
- Rules (settings icon) — Rule Configuration
- Compliance (shield icon) — Audit & Compliance
- AI Assistant (bot icon) — Agent Chat

**Header:**
- ArqAI logo + "FWA Detection & Prevention"
- Notification bell (badge count of critical cases)
- User avatar / role display

### 10B: Executive Overview (`/`)

**Stat Cards Row (4 cards):**
- Total Fraud Identified: `$X.XM` with delta from last period
- Active Cases: `N` with delta
- Claims Processed: `N` (last 30 days)
- Recovery Rate: `X%` with delta

**Charts:**
1. **Fraud Trend Line Chart** — 30/90/365 day view, claims_flagged and fraud_amount over time
2. **Risk Distribution Donut Chart** — Low / Medium / High / Critical claim counts
3. **Top 10 Flagged Providers Table** — NPI, Name, Specialty, Risk Score, Flagged Claims, $ Amount
4. **Rule Effectiveness Bar Chart** — Each rule's trigger count and total $ flagged
5. **Recent Cases Table** — Last 10 cases with status, priority, amount, created date

### 10C: Claims Explorer (`/claims`)

**Filters Bar:**
- Claim Type: Medical | Pharmacy | All
- Risk Level: Low | Medium | High | Critical | All
- Status: Received | Processed | Flagged | All
- Date Range picker
- Search by claim ID, member ID, provider NPI

**Claims Table (TanStack Table):**
- Columns: Claim ID, Type, Member, Provider, Service Date, CPT/NDC, Billed Amount, Risk Score (color-coded badge), Status, Actions
- Sortable on all columns
- Click row → Slide-out drawer with full claim detail

**Claim Detail Drawer:**
- Claim summary (all fields)
- Enrichment data (provider info, member info, reference lookups)
- Rules Triggered (list with severity bars)
- Risk Score breakdown (pie chart of rule contributions)
- "Create Case" button (if not already a case)
- "View Case" button (if case exists)

### 10D: Investigation Queue (`/cases`)

**Filters:**
- Status: Open | Under Review | Resolved | Closed | All
- Priority: P1 | P2 | P3 | P4 | All
- Assigned To filter
- Risk Level filter

**Cases Table:**
- Columns: Case ID, Claim ID, Risk Score, Risk Level (badge), Priority (badge), Status, Assigned To, Estimated Fraud $, Created, SLA Deadline
- Sort by priority, risk score, or created date
- Click row → Navigate to case detail page

### 10E: Case Detail (`/cases/[id]`)

**Layout: Two-column**

**Left Column (60%):**
- Case header: ID, Status badge, Priority badge, Risk Score (large)
- Claim Summary section
- Rules Triggered section — expandable cards showing each rule's evidence
- AI Analysis section — agent's investigation narrative (from Phase 9)
- "Ask AI" button to trigger investigation or ask follow-up questions

**Right Column (40%):**
- Actions panel: Change Status, Assign, Set Resolution Path
- Timeline: Chronological list of all events (created, assigned, notes added, status changes)
- Notes section: Add investigation notes
- Evidence Bundle: Download as JSON or generate report

### 10F: Rule Configuration (`/rules`)

**Two-panel layout:**

**Left Panel — Rule List:**
- Tabs: Medical Rules | Pharmacy Rules
- Table: Rule ID, Category, Fraud Type, Weight, Enabled toggle, Edit button
- Color-coded by implementation priority

**Right Panel — Rule Config Form (appears on Edit click):**
- Rule description (read-only)
- Weight slider (1.0 - 10.0)
- Enabled toggle
- Threshold fields (dynamic based on rule — each rule has different threshold params)
- Benchmark source selector (where applicable)
- Save / Reset to Default / Cancel buttons
- Last Modified info

### 10G: Compliance & Audit (`/compliance`)

**Tabs:**

**Audit Log Tab:**
- Filters: Date range, Event Type, Actor, Resource Type
- Table: Timestamp, Event Type, Actor, Action, Resource, Details (expandable)
- Export to CSV button
- Chain Integrity Check button → shows green check or red alert

**Compliance Report Tab:**
- Generate Report button (date range selector)
- Report shows: total claims processed, flagged count by rule, case resolution stats, evidence completeness
- Export as PDF (stretch goal) / JSON

### 10H: AI Assistant (`/agents`)

**Chat Interface:**
- Full-screen chat layout
- Message input at bottom
- Messages display: user messages (right), agent responses (left)
- Agent responses include:
  - Formatted analysis text
  - Referenced evidence (clickable links to cases/claims)
  - Confidence indicator
- Case selector dropdown at top (optional — scope chat to a specific case)

### Acceptance Criteria
- All 6 pages fully functional
- Data loads from real API endpoints (not mocked)
- Tables paginate, sort, and filter correctly
- Charts render with real data
- Case status updates persist immediately
- Responsive layout (works on 1280px+)
- Sidebar navigation highlights current page
- Loading states and error handling for all API calls

---

## PHASE 11: Investigation Workflow & Case Management

### Objective
Wire up the end-to-end workflow: after scoring, automatically create investigation cases for high/critical risk claims, and support the full case lifecycle.

### `backend/app/services/case_manager.py`

**Auto-Case Creation:**
```python
async def create_cases_from_scores(scores: list[RiskScore]) -> list[InvestigationCase]:
    """
    For each score with risk_level in ["high", "critical"]:
      - Create InvestigationCase
      - Set priority: critical→P1, high→P2
      - Set SLA deadline: P1→48hrs, P2→5 business days
      - Generate initial evidence bundle
      - Create audit log entry
    """
```

**Case Lifecycle:**
```
open → under_review → resolved → closed
                   ↘ escalated
```

**Resolution Paths (from POC spec):**
1. **Provider Accepts** → Claim corrected → Case closed
2. **Provider Disputes** → Rule validity review → May update rule engine
3. **Plan Benefit Issue** → Escalate to plan admin
4. **No Response** → After N attempts → Manual triage
5. **Complex Case** → Manual investigation → Recovery process

### Acceptance Criteria
- Cases auto-created for high/critical risk scores
- Priority and SLA correctly assigned
- Full lifecycle transitions work
- Resolution paths captured
- All state changes audit-logged

---

## PHASE 12: Integration & Full Pipeline Test

### Objective
Run the complete end-to-end pipeline and verify everything works together.

### End-to-End Flow:
```
1. Seed synthetic data (Phase 2)
   ↓
2. Ingest claims batch (Phase 3)
   ↓
3. Enrich claims (Phase 4)
   ↓
4. Run all 29 rules (Phase 5)
   ↓
5. Calculate risk scores (Phase 6)
   ↓
6. Auto-create investigation cases (Phase 11)
   ↓
7. Generate evidence bundles (Phase 7)
   ↓
8. AI agent investigates top cases (Phase 9)
   ↓
9. Dashboard displays everything (Phase 10)
   ↓
10. Investigator reviews, updates status, closes cases (Phase 11)
```

### Pipeline Runner
```
POST /api/pipeline/run-full
  → Triggers steps 2-8 for all seeded claims
  → Returns: { claims_processed, rules_evaluated, cases_created, time_elapsed }
```

### Test Cases:
1. **Happy Path**: 15K medical + 20K pharmacy claims processed, ~7000 flagged, ~1500 high/critical cases created
2. **Each Rule Fires**: Verify every one of the 29 rules triggers on at least one synthetic fraud scenario
3. **Scoring Accuracy**: High-severity fraud (phantom billing, upcoding) scores >80; low-severity (copay waiver) scores <40
4. **Evidence Completeness**: Every case has a complete evidence bundle
5. **Audit Chain**: Verify chain integrity after full pipeline run
6. **Performance**: Full pipeline completes in < 5 minutes

### Acceptance Criteria
- Full pipeline runs end-to-end without errors
- Dashboard populates with real data after pipeline run
- All 29 rules fire on their corresponding synthetic scenarios
- Scores are sensible and risk levels are correct
- Agent can investigate any created case
- Audit trail has thousands of entries, all hash-chain valid

---

## PHASE 13: Docker Compose & Deployment

### Objective
Everything runs with a single `docker compose up`. No manual setup required.

### `docker-compose.yml` Services:

| Service | Image | Ports | Depends On |
|---------|-------|-------|------------|
| `postgres` | postgres:15-alpine | 5432 | — |
| `redis` | redis:7-alpine | 6379 | — |
| `backend` | ./backend (Dockerfile) | 8000 | postgres, redis |
| `frontend` | ./frontend (Dockerfile) | 3000 | backend |
| `nginx` | nginx:alpine | 80, 443 | backend, frontend |

**Note on Ollama:** Ollama runs on the host machine (not in Docker) because it needs GPU access. Backend connects via `OLLAMA_URL=http://host.docker.internal:11434` (Docker Desktop) or `http://172.17.0.1:11434` (Linux).

### Startup Sequence:
1. `docker compose up -d` — starts all services
2. Backend auto-runs `alembic upgrade head` on startup (creates tables)
3. Backend auto-seeds reference data + synthetic data on first run (if DB is empty)
4. Backend auto-runs full pipeline on first run (enrich → rules → score → create cases)
5. Frontend is ready at `http://localhost:3000`

### `.env.example`:
```env
# Database
POSTGRES_DB=arqai_fwa
POSTGRES_USER=arqai
POSTGRES_PASSWORD=arqai_dev_password
DATABASE_URL=postgresql+asyncpg://arqai:arqai_dev_password@postgres:5432/arqai_fwa

# Redis
REDIS_URL=redis://redis:6379/0

# Ollama (runs on host, not in Docker)
OLLAMA_URL=http://host.docker.internal:11434
LLM_MODEL=llama3.1

# App
SECRET_KEY=dev-secret-key-change-in-production
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Acceptance Criteria
- `docker compose up` brings up the entire system
- First-run auto-seeds data and runs pipeline
- Frontend accessible at localhost:3000
- API accessible at localhost:8000/api/docs
- System works without Ollama (agent features gracefully disabled)
- Teardown: `docker compose down -v` cleanly removes everything

---

## Phase Dependency Graph

```
PHASE 0: Scaffolding
   ↓
PHASE 1: Data Models & Migrations
   ↓
PHASE 2: Synthetic Data Generator
   ↓
PHASE 3: Ingestion Pipeline ←──────────┐
   ↓                                    │
PHASE 4: Enrichment Pipeline            │
   ↓                                    │
PHASE 5: Rule Engine (all 29 rules)     │
   ↓                                    │
PHASE 6: Risk Scoring Engine            │
   ↓                                    │
PHASE 7: Governance (Audit, Evidence)   │  (parallel with 8, 9, 10)
   ↓                                    │
PHASE 8: API Layer ←───────────────────────── PHASE 9: Agent Layer (can parallel)
   ↓                                    │
PHASE 10: Frontend Dashboard            │
   ↓                                    │
PHASE 11: Investigation Workflow ───────┘
   ↓
PHASE 12: Integration Test (everything together)
   ↓
PHASE 13: Docker Compose & Deployment
```

**Parallelization Opportunities:**
- Phase 7 (Governance) can be built alongside Phase 5-6
- Phase 9 (Agent) can be built alongside Phase 8 (API)
- Phase 10 (Frontend) pages can be built incrementally as API endpoints land

---

## Rule Weight Reference (Quick Lookup)

| Rule | Category | Type | Weight | Priority |
|------|----------|------|--------|----------|
| M1 | Upcoding | Fraud | 9.0 | HIGH |
| M2 | Unbundling | Fraud | 7.5 | MEDIUM |
| M3 | Duplicate Billing | Fraud | 8.0 | HIGH |
| M4 | Phantom Billing | Fraud | 10.0 | HIGH |
| M5 | Kickback/Self-Referral | Fraud | 9.5 | MEDIUM |
| M6 | Medically Unnecessary | Waste | 7.0 | MEDIUM |
| M7 | Provider Collusion | Fraud | 6.5 | LOW |
| M8 | Modifier Misuse | Fraud | 5.5 | MEDIUM |
| M9 | Copay Waiver | Abuse | 2.5 | LOW |
| M10 | IP/OP Misclass | Fraud | 6.0 | MEDIUM |
| M11 | DME Fraud | Fraud | 6.0 | MEDIUM |
| M12 | Lab/Diagnostic Abuse | Waste | 5.0 | MEDIUM |
| M13 | Provider Ghosting | Fraud | 7.0 | LOW |
| M14 | Double Dipping | Fraud | 7.0 | MEDIUM |
| M15 | Telehealth Fraud | Fraud | 6.0 | MEDIUM |
| M16 | Chart Padding | Abuse/Fraud | 4.0 | LOW |
| P1 | Prescription Forgery | Fraud | 8.0 | MEDIUM |
| P2 | Doctor Shopping | Abuse | 7.5 | MEDIUM |
| P3 | Pharmacy Shopping | Abuse | 3.0 | LOW |
| P4 | Early Refill | Waste/Abuse | 4.5 | HIGH |
| P5 | Controlled Sub Diversion | Fraud/Abuse | 9.5 | MEDIUM |
| P6 | Phantom Claims | Fraud | 10.0 | HIGH |
| P7 | High-Cost Substitution | Fraud | 5.5 | MEDIUM |
| P8 | Kickback/Split Billing | Fraud | 6.5 | MEDIUM |
| P9 | Invalid Prescriber | Fraud | 8.5 | HIGH |
| P10 | Stockpiling | Waste | 4.0 | LOW |
| P11 | Compound Drug Fraud | Fraud | 7.0 | LOW |
| P12 | Phantom Members | Fraud | 8.0 | HIGH |
| P13 | Pharmacy-Provider Collusion | Fraud | 6.0 | LOW |

---

## Recovery Instructions

If context is ever lost, point Claude to:
1. **This file** (`BUILD_PLAN.md`) for the complete build spec
2. **The specific phase** you were working on
3. **The file tree** to see what's already been built vs. what's pending
4. Run `git log --oneline -20` to see what's been committed

Each phase is self-contained enough that work can resume at any phase boundary.
