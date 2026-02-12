# Build Plan: Client Workspaces + Transparency Features

## Overview

Two major capabilities:
1. **Client Workspaces** — Isolated data environments with CSV upload + column mapping
2. **Transparency Layer** — Rule Trace, Live Pipeline, Peer Comparison, Confidence Indicators

Build order is chosen so that each phase is independently testable and nothing breaks existing functionality.

---

## Phase 1: Workspace Database Foundation

**Goal:** Add workspace isolation to the data model without breaking anything existing.

### 1A. New migration: `workspaces` table

```sql
CREATE TABLE workspaces (
    id SERIAL PRIMARY KEY,
    workspace_id VARCHAR(32) UNIQUE NOT NULL,   -- "ws-abc123"
    name VARCHAR(100) NOT NULL,                 -- "Acme Insurance Demo"
    client_name VARCHAR(100),                   -- "Acme Insurance"
    description TEXT,
    data_source VARCHAR(20) DEFAULT 'upload',   -- "synthetic" | "upload"
    status VARCHAR(20) DEFAULT 'active',        -- "active" | "archived"
    claim_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 1B. Add `workspace_id` to existing tables

Add nullable `workspace_id INTEGER REFERENCES workspaces(id)` to:
- `medical_claims`
- `pharmacy_claims`
- `members`
- `providers`
- `pharmacies`
- `risk_scores`
- `rule_results`
- `investigation_cases`

**Strategy:** Nullable column first → backfill existing rows to a "default" workspace → keep nullable (upload flows will always set it).

### 1C. Create default workspace + backfill

Data migration step:
1. Insert default workspace: `workspace_id="ws-default", name="Synthetic Demo", data_source="synthetic"`
2. UPDATE all existing rows to point to default workspace

### 1D. New model: `Workspace` in `app/models/workspace.py`

### 1E. Add `workspace_id` field to existing models

Add the column + FK relationship to: MedicalClaim, PharmacyClaim, Member, Provider, Pharmacy, RiskScore, RuleResult, InvestigationCase.

### Files touched:
- `backend/app/models/workspace.py` (NEW)
- `backend/app/models/claim.py` (add workspace_id FK)
- `backend/app/models/provider.py` (add workspace_id FK)
- `backend/app/models/member.py` (add workspace_id FK)
- `backend/app/models/scoring.py` (add workspace_id FK)
- `backend/app/models/case.py` (add workspace_id FK)
- `backend/alembic/versions/` (NEW migration)

### How to test:
```bash
alembic upgrade head
# Verify: psql → SELECT count(*) FROM workspaces; → 1 (default)
# Verify: SELECT DISTINCT workspace_id FROM medical_claims; → all point to default
# Verify: All existing API endpoints still work unchanged
```

---

## Phase 2: Workspace API + Upload Engine

**Goal:** CRUD for workspaces, CSV upload with preview + column mapping, data ingestion.

### 2A. Upload mapping config: `app/upload/column_maps.py`

Define expected schema for medical and pharmacy claims:
```python
MEDICAL_REQUIRED = {
    "claim_id": ["claim_id", "claim_number", "claim_no", "clm_id"],
    "member_id": ["member_id", "member_number", "subscriber_id", "mbr_id"],
    "provider_npi": ["npi", "provider_npi", "rendering_npi", "billing_npi"],
    "service_date": ["service_date", "dos", "date_of_service", "svc_date"],
    "cpt_code": ["cpt_code", "cpt", "procedure_code", "proc_code", "hcpcs"],
    "diagnosis_code_primary": ["diagnosis_code", "dx_code", "icd_code", "primary_dx", "dx1"],
    "amount_billed": ["amount_billed", "billed_amount", "charge_amount", "total_charge"],
}

MEDICAL_OPTIONAL = {
    "amount_allowed": [...],
    "amount_paid": [...],
    "place_of_service": [...],
    ...
}
```

Auto-match logic: normalize column names (lowercase, strip spaces/underscores), fuzzy match against known aliases.

### 2B. Upload service: `app/services/upload_service.py`

```python
class UploadService:
    async def preview_csv(file: UploadFile) -> UploadPreview
        # Read first 100 rows, detect columns, auto-map, return preview

    async def validate_mapping(mapping: ColumnMapping, file) -> ValidationResult
        # Check required fields mapped, validate data types, sample parse

    async def ingest(workspace_id, file, mapping, claim_type) -> IngestionResult
        # Parse full file, create members/providers on-the-fly,
        # insert claims, update workspace.claim_count
```

### 2C. Workspace API router: `app/api/workspaces.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workspaces` | List all workspaces |
| POST | `/api/workspaces` | Create new workspace |
| GET | `/api/workspaces/{id}` | Get workspace detail |
| DELETE | `/api/workspaces/{id}` | Archive workspace |
| POST | `/api/workspaces/{id}/upload/preview` | Upload CSV, get column preview |
| POST | `/api/workspaces/{id}/upload/ingest` | Confirm mapping, ingest data |

### 2D. Wire workspace filtering into ALL existing endpoints

Every existing query gets an optional `?workspace_id=` query param.
- If provided → filter to that workspace only
- If omitted → show all (backward compatible)

Touch points:
- `app/api/claims.py` — add workspace filter to list + detail
- `app/api/cases.py` — add workspace filter to list
- `app/api/dashboard.py` — add workspace filter to overview, trends, providers
- `app/api/pipeline.py` — add workspace filter to run-full + status
- `app/api/audit.py` — no change (audit is global)
- `app/api/rules.py` — no change (rules are global, shared across workspaces)

Implementation pattern (minimal, DRY):
```python
# app/api/deps.py — new helper
def workspace_filter(query, model, workspace_id: str | None):
    if workspace_id:
        ws = await get_workspace(workspace_id)
        return query.where(model.workspace_id == ws.id)
    return query
```

### 2E. Update pipeline to respect workspace

`app/api/pipeline.py` run-full:
- Accept optional `workspace_id` in request body
- Pass through to enrichment, rule engine, scoring, case creation
- All created rule_results, risk_scores, cases get tagged with workspace_id

### Files touched:
- `backend/app/upload/` (NEW directory)
- `backend/app/upload/column_maps.py` (NEW)
- `backend/app/services/upload_service.py` (NEW)
- `backend/app/api/workspaces.py` (NEW)
- `backend/app/api/claims.py` (add workspace_id filter)
- `backend/app/api/cases.py` (add workspace_id filter)
- `backend/app/api/dashboard.py` (add workspace_id filter)
- `backend/app/api/pipeline.py` (add workspace_id to request + filter)
- `backend/app/api/deps.py` (add workspace_filter helper)
- `backend/app/main.py` (register workspace router)
- `backend/app/engine/enrichment.py` (workspace-scoped historical queries)
- `backend/app/engine/case_manager.py` (tag cases with workspace_id)

### How to test:
```bash
# Create workspace
curl -X POST http://localhost:8000/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Client", "client_name": "Test"}'

# Upload preview
curl -X POST http://localhost:8000/api/workspaces/ws-xxx/upload/preview \
  -F "file=@sample_claims.csv" -F "claim_type=medical"

# Ingest
curl -X POST http://localhost:8000/api/workspaces/ws-xxx/upload/ingest \
  -H "Content-Type: application/json" \
  -d '{"mapping": {...}, "claim_type": "medical"}'

# Run pipeline on workspace
curl -X POST http://localhost:8000/api/pipeline/run-full \
  -H "Content-Type: application/json" \
  -d '{"limit": 5000, "workspace_id": "ws-xxx"}'

# Verify dashboard scoped
curl http://localhost:8000/api/dashboard/overview?workspace_id=ws-xxx
```

---

## Phase 3: Frontend — Workspace Switcher + Upload UI

**Goal:** Workspace dropdown in sidebar, upload wizard page, all pages respect active workspace.

### 3A. Workspace context: `src/lib/workspace-context.tsx`

React Context that stores active workspace ID. All API calls include it.

```typescript
// Provider wraps the app in layout.tsx
// useWorkspace() hook returns { activeWorkspace, setActiveWorkspace, workspaces }
```

### 3B. Workspace switcher in sidebar

Dropdown at top of sidebar showing current workspace name.
- Lists all workspaces
- "Synthetic Demo" is default
- "New Workspace" option at bottom → navigates to upload page

### 3C. Update `src/lib/api.ts`

Every API function gets optional `workspaceId` parameter:
```typescript
// Before:
claims.list({ page, size })

// After — workspace auto-injected from context:
claims.list({ page, size, workspace_id: activeWorkspace })
```

### 3D. New page: `/upload` — Data Upload Wizard

Three-step wizard:

**Step 1: Create Workspace**
- Name, client name (text inputs)
- File drop zone (drag-and-drop CSV/XLSX)
- Claim type toggle (Medical / Pharmacy)

**Step 2: Column Mapping**
- Left column: their CSV headers (detected)
- Right column: dropdown of our required fields
- Auto-mapped fields shown in green
- Unmapped required fields shown in red
- Preview table showing first 5 rows with mapped column names

**Step 3: Confirm & Ingest**
- Summary: "Ready to import 12,450 medical claims for Acme Insurance"
- Validation results (X rows valid, Y rows with issues)
- "Start Import" button
- Progress bar during ingestion
- On complete → auto-run pipeline → redirect to dashboard

### 3E. Update sidebar navigation

Add "Upload Data" link with Upload icon between existing nav items.

### Files touched:
- `frontend/src/lib/workspace-context.tsx` (NEW)
- `frontend/src/app/layout.tsx` (wrap with WorkspaceProvider)
- `frontend/src/components/layout/sidebar.tsx` (add workspace dropdown + upload link)
- `frontend/src/lib/api.ts` (add workspace endpoints, update all existing calls)
- `frontend/src/app/upload/page.tsx` (NEW — 3-step wizard)
- `frontend/src/app/upload/` (NEW directory)

### How to test:
1. Open http://localhost:3000 — sidebar shows "Synthetic Demo" as default workspace
2. Switch workspace → all pages refresh with filtered data
3. Click "Upload Data" → wizard appears
4. Upload a sample CSV → auto-mapping works → ingest → pipeline runs → dashboard shows client data

---

## Phase 4: Rule Trace View (Transparency Feature A)

**Goal:** For any flagged claim, show a step-by-step breakdown of exactly which rules fired and why.

### 4A. Backend: Enhanced rule result response

The data already exists in `rule_results.evidence` (JSONB) and `rule_results.details`. We need a dedicated endpoint that returns it in a presentation-friendly format.

New endpoint in `app/api/claims.py`:
```
GET /api/claims/{claim_id}/rule-trace
```

Response:
```json
{
  "claim_id": "MCL-2025-004721",
  "total_score": 87,
  "risk_level": "critical",
  "steps": [
    {
      "step": 1,
      "rule_id": "M3",
      "rule_name": "High Volume Provider",
      "category": "Phantom Billing",
      "triggered": true,
      "severity": 2.4,
      "confidence": 0.92,
      "weight": 8.0,
      "contribution": 30.2,
      "explanation": "Dr. Smith billed 47 patients on Jan 15. Average for Cardiology is 18. This is 2.6x above the threshold of 30.",
      "evidence": {
        "daily_count": 47,
        "specialty_average": 18,
        "threshold": 30,
        "ratio": 2.6
      }
    },
    {
      "step": 2,
      "rule_id": "M1",
      "rule_name": "Upcoding",
      "triggered": true,
      ...
    },
    {
      "step": 3,
      "rule_id": "M12",
      "rule_name": "Weekend Billing",
      "triggered": false,
      "explanation": "Service date was a weekday. No anomaly detected."
    }
  ],
  "score_calculation": {
    "raw_score": 72.3,
    "max_possible": 83.1,
    "normalized_score": 87,
    "formula": "SUM(weight × severity × confidence) / max_possible × 100"
  }
}
```

Implementation: Join rule_results with rules table, format evidence into human-readable explanation strings. The `_explanation_for_rule()` helper maps each rule_id to a template string that fills in evidence values.

### 4B. Frontend: Rule Trace component

New component: `src/components/rule-trace.tsx`

Visual design:
- Vertical stepper / timeline layout
- Each step is a card with:
  - Rule badge (M3, P5, etc.) with color coding
  - Rule name + category
  - TRIGGERED (red) or PASSED (green) badge
  - Human-readable explanation paragraph
  - Expandable "Raw Evidence" section (JSON)
  - Contribution bar showing how much this rule added to final score
- Final "Score Calculation" card at bottom showing the math

### 4C. Integrate into existing pages

- **Claim detail slide-out** (`/claims` page): Replace the current basic rule results list with the Rule Trace component
- **Case detail page** (`/cases/[id]`): Replace "Rules Triggered" section with Rule Trace component

### Files touched:
- `backend/app/api/claims.py` (new `/rule-trace` endpoint)
- `backend/app/services/rule_trace.py` (NEW — explanation generation logic)
- `frontend/src/components/rule-trace.tsx` (NEW)
- `frontend/src/lib/api.ts` (add `claims.ruleTrace(claimId)`)
- `frontend/src/app/claims/page.tsx` (use RuleTrace in detail panel)
- `frontend/src/app/cases/[id]/page.tsx` (use RuleTrace in rules section)

### How to test:
1. Open `/claims`, click a flagged claim → see Rule Trace instead of raw list
2. Open `/cases/CASE-xxx` → see Rule Trace with step-by-step explanations
3. Verify all 29 rules have readable explanation templates
4. Verify score calculation section matches displayed total

---

## Phase 5: Live Pipeline Animation (Transparency Feature B)

**Goal:** When the pipeline runs, show real-time progress with streaming updates.

### 5A. Backend: Server-Sent Events (SSE) endpoint

New endpoint in `app/api/pipeline.py`:
```
POST /api/pipeline/run-stream
```

Returns `text/event-stream` with progress events:
```
event: phase
data: {"phase": "enrichment", "label": "Enriching claims", "progress": 0}

event: progress
data: {"phase": "enrichment", "current": 500, "total": 2000, "progress": 25}

event: progress
data: {"phase": "rules", "current": 14500, "total": 58000, "progress": 25, "detail": "Rule M7 — Upcoding: 45 triggered"}

event: rule_fired
data: {"rule_id": "M3", "claim_id": "MCL-2025-004721", "severity": 2.4}

event: phase
data: {"phase": "scoring", "label": "Calculating risk scores", "progress": 0}

event: complete
data: {"total_claims": 2000, "rules_evaluated": 58000, "cases_created": 312, "elapsed_seconds": 28.1}
```

Implementation: Refactor the existing `run_full_pipeline` to yield progress callbacks. Wrap in an async generator that produces SSE frames.

### 5B. Frontend: Pipeline Monitor page enhancement

Update the dashboard or create a pipeline section accessible from dashboard:

New component: `src/components/pipeline-monitor.tsx`

Visual design:
- "Run Pipeline" button (already exists conceptually)
- On click, shows a full-screen overlay / modal with:
  - Phase indicators (4 phases): Enrich → Evaluate → Score → Create Cases
  - Active phase highlighted with spinner
  - Progress bar per phase (animated fill)
  - Live counter: "14,500 / 58,000 rules evaluated"
  - Scrolling log feed showing individual rule fires (latest 20)
  - Final summary card when complete
- Uses `EventSource` API to consume SSE stream

### 5C. Add "Run Pipeline" button to dashboard

On the dashboard page, add a prominent button that:
- If workspace has unprocessed claims → "Run Pipeline (2,450 unscored claims)"
- On click → opens pipeline monitor
- When complete → dashboard auto-refreshes with new data

### Files touched:
- `backend/app/api/pipeline.py` (new SSE endpoint)
- `backend/app/engine/pipeline_runner.py` (NEW — refactored pipeline with progress callbacks)
- `frontend/src/components/pipeline-monitor.tsx` (NEW)
- `frontend/src/app/page.tsx` (add Run Pipeline button)
- `frontend/src/lib/api.ts` (add pipeline.runStream helper)

### How to test:
1. Upload new client data (unscored)
2. Click "Run Pipeline" on dashboard
3. Watch progress bars fill in real-time
4. See individual rules firing in the log feed
5. Pipeline completes → dashboard auto-refreshes with new numbers

---

## Phase 6: Compare to Peers (Transparency Feature C)

**Goal:** For any flagged provider, show how they compare against specialty peers.

### 6A. Backend: Peer comparison endpoint

New endpoint in `app/api/providers.py` (NEW router):
```
GET /api/providers/{npi}/peer-comparison?workspace_id=ws-xxx
```

Response:
```json
{
  "provider": {
    "npi": "1234567890",
    "name": "Dr. John Smith",
    "specialty": "Cardiology"
  },
  "peer_group": "Cardiology (n=45)",
  "metrics": [
    {
      "metric": "Avg Charge per Visit",
      "provider_value": 487.00,
      "peer_average": 215.00,
      "peer_p75": 280.00,
      "peer_p90": 340.00,
      "percentile": 98,
      "anomaly": true
    },
    {
      "metric": "Daily Patient Volume",
      "provider_value": 47,
      "peer_average": 18,
      "peer_p75": 24,
      "peer_p90": 31,
      "percentile": 99,
      "anomaly": true
    },
    {
      "metric": "99215 (High Complexity) Rate",
      "provider_value": 0.94,
      "peer_average": 0.22,
      "peer_p75": 0.30,
      "peer_p90": 0.38,
      "percentile": 99,
      "anomaly": true
    },
    {
      "metric": "Unique Members per Month",
      "provider_value": 312,
      "peer_average": 95,
      ...
    }
  ]
}
```

Implementation: Aggregate claim statistics per provider, grouped by specialty. Calculate percentiles. Compare target provider against their specialty cohort.

### 6B. Frontend: Peer Comparison component

New component: `src/components/peer-comparison.tsx`

Visual design:
- Horizontal bar chart for each metric
- Three markers on each bar: peer avg (gray line), peer p90 (yellow line), provider (red dot if anomaly, green if normal)
- Provider value labeled explicitly
- Percentile badge on right side
- "98th percentile" in red = clearly anomalous

### 6C. Integrate into existing pages

- **Case detail page**: Add "Provider Profile" section with peer comparison
- **Dashboard top providers table**: Click a provider → expand row to show peer comparison inline
- **Claims detail panel**: Show mini peer comparison for the claim's provider

### Files touched:
- `backend/app/api/providers.py` (NEW router)
- `backend/app/services/peer_comparison.py` (NEW)
- `backend/app/main.py` (register provider router)
- `frontend/src/components/peer-comparison.tsx` (NEW)
- `frontend/src/lib/api.ts` (add providers.peerComparison)
- `frontend/src/app/cases/[id]/page.tsx` (add Provider Profile section)
- `frontend/src/app/page.tsx` (expandable provider rows)

### How to test:
1. Open a case → see Provider Profile section with peer comparison bars
2. Verify anomalous metrics are highlighted in red
3. Verify percentiles are mathematically correct
4. Check with a low-risk provider — bars should show green/normal

---

## Phase 7: Confidence Indicators (Transparency Feature E)

**Goal:** Show how confident the system is in each flag, backed by historical pattern matching.

### 7A. Backend: Pattern matching stats

New service: `app/services/pattern_confidence.py`

For each case, analyze the combination of triggered rules and compare to historical outcomes:
```python
async def calculate_pattern_confidence(case_id: str) -> PatternConfidence:
    # 1. Get the set of triggered rules for this case
    # 2. Find all historical cases with similar rule combinations
    #    (jaccard similarity > 0.6 on triggered rule sets)
    # 3. Of those, how many were resolved as confirmed fraud?
    # 4. Return confidence stats
```

New field on case detail response:
```json
{
  "pattern_confidence": {
    "score": 0.91,
    "similar_cases_count": 847,
    "confirmed_fraud_count": 772,
    "description": "91% of cases with similar patterns (high volume + upcoding) were confirmed fraudulent",
    "matching_patterns": ["High Volume Provider", "Upcoding"],
    "data_basis": "Based on 847 historical cases in this workspace"
  }
}
```

For demo/synthetic data: Pre-compute pattern outcomes during seeding so confidence stats are meaningful. Mark some resolved cases as confirmed fraud during seed.

### 7B. Seed enhancement: Add resolved case outcomes

Update `app/seed/synthetic_data.py` or add `app/seed/case_outcomes.py`:
- After pipeline runs on seed data, auto-resolve ~60% of cases
- Mark ~70% of resolved high/critical as "confirmed_fraud"
- Mark remaining as "false_positive" or "insufficient_evidence"
- This gives the confidence engine historical data to work with

### 7C. Frontend: Confidence indicator component

New component: `src/components/confidence-indicator.tsx`

Visual design:
- Circular gauge (like a speedometer) showing confidence percentage
- Color: green (>80%), yellow (50-80%), red (<50%)
- Text below: "91% — Based on 847 similar cases"
- Expandable detail: "772 of 847 cases with this pattern combination (High Volume + Upcoding) were confirmed fraudulent"

### 7D. Integrate into case detail page

Add Confidence Indicator to the right column of case detail, above the Actions panel. It's the first thing an investigator sees — "how confident should I be that this is real fraud?"

### Files touched:
- `backend/app/services/pattern_confidence.py` (NEW)
- `backend/app/api/cases.py` (add pattern_confidence to case detail response)
- `backend/app/seed/synthetic_data.py` (add case outcome generation)
- `frontend/src/components/confidence-indicator.tsx` (NEW)
- `frontend/src/app/cases/[id]/page.tsx` (add confidence indicator)
- `frontend/src/lib/api.ts` (update CaseDetail interface)

### How to test:
1. Open a case detail → see confidence gauge
2. Verify percentage matches actual similar-case ratio
3. Check a low-risk case → should show lower confidence
4. Check edge case: new workspace with no history → shows "Insufficient history" instead of gauge

---

## Build Order & Dependencies

```
Phase 1 ──→ Phase 2 ──→ Phase 3
  (DB)        (API)      (Frontend)
                           ↓
              Phase 4 (Rule Trace) ← independent, can start after Phase 1
                           ↓
              Phase 5 (Live Pipeline) ← needs Phase 2 pipeline refactor
                           ↓
              Phase 6 (Peer Comparison) ← independent
                           ↓
              Phase 7 (Confidence) ← needs seeded case outcomes
```

Phases 4 and 6 are independent and can be built in parallel.
Phase 5 depends on Phase 2 (pipeline workspace awareness).
Phase 7 depends on Phase 1 (needs case history in DB).

## Total new files: ~15
## Total modified files: ~20
## New DB tables: 1 (workspaces)
## Modified DB tables: 8 (add workspace_id)
## New API endpoints: ~10
## New frontend pages: 1 (/upload)
## New frontend components: 4 (rule-trace, pipeline-monitor, peer-comparison, confidence-indicator)
