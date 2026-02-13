# Plan: Make Chat Assistant Fully Workspace-Aware

## Problem

The chat assistant returns data from the **synthetic (ws-default) workspace** even when the user is in a different workspace. This happens because **two entire layers** of the agent service have no workspace filtering:

1. **`_gather_data_context()`** (lines 1020-1125) — the pre-fetched context injected into every LLM prompt. **Zero** workspace filters on any query (claims, cases, risk scores, rules).
2. **`_data_driven_chat()` fallback methods** (lines 1547-1818) — `_answer_stats`, `_answer_top_risk`, `_answer_rules`, `_answer_general`, `_answer_provider`. **All** query the entire database unscoped.
3. **`_tool_pipeline_stats()`** (lines 410-424) — the tool the LLM calls for stats. **No** workspace filter.
4. **`_tool_query_rules()`** (lines 506-513) — the tool the LLM calls for rule stats. **No** workspace filter.
5. **`_tool_query_provider()`** (lines 515-521) — provider lookup. **No** workspace filter.
6. **Risk-level breakdown in `_tool_financial_summary()`** (lines 628-635) — the per-level fraud amount subqueries for `level_med_fraud` and `level_rx_fraud` are **missing** the workspace filter on the claim tables (they filter `RiskScore` but not `MedicalClaim`/`PharmacyClaim`).

The tool methods that DO properly filter (`_tool_query_cases`, `_tool_financial_summary` main queries, `_tool_cases_financial`, `_tool_claims_analysis`, `_gather_case_context`) are fine but not enough — the LLM gets polluted context from unscoped pre-fetch, and when Ollama is unavailable the fallbacks return entirely wrong data.

---

## Changes (all in `backend/app/services/agent_service.py`)

### Step 1: Fix `_gather_data_context()` (lines 1020-1125)

Add `self.workspace_id` filter to every query:
- Medical claim count (line 1025)
- Pharmacy claim count (line 1026)
- Case count (line 1027)
- Active case count (lines 1028-1031)
- Risk-level breakdown (lines 1034-1037)
- Status breakdown (lines 1040-1043)
- Scored count (line 1045)
- Top 10 cases (lines 1059-1061)
- Rule results (lines 1107-1111)

### Step 2: Fix `_tool_pipeline_stats()` (lines 410-424)

Add `self.workspace_id` filter to all 5 queries (med count, rx count, cases, active, risk breakdown).

### Step 3: Fix `_tool_query_rules()` (lines 506-513)

Filter `RuleResult` by `self.workspace_id`.

### Step 4: Fix `_tool_query_provider()` (lines 515-521)

Filter `Provider` by `self.workspace_id`.

### Step 5: Fix `_tool_financial_summary()` risk-level breakdown (lines 628-635)

Add workspace filter to `level_med_fraud` and `level_rx_fraud` claim subqueries.

### Step 6: Fix all `_data_driven_chat` fallback methods

- **`_answer_stats()`** (lines 1637-1650): add workspace filter to all 4 queries
- **`_answer_top_risk()`** (lines 1652-1663): filter cases by workspace
- **`_answer_rules()`** (lines 1665-1680): filter rule_results by workspace
- **`_answer_provider()`** (lines 1786-1798): filter provider by workspace
- **`_answer_general()`** (lines 1814-1818+): filter active case count by workspace

### Step 7: Enrich system prompt with workspace metadata

Currently the system prompt only says `"Scoped to workspace {workspace_id}"` (an integer). Enhance it to include the workspace name and make it clear the LLM must ONLY reference this workspace's data. Query the Workspace model at the start of `chat()` to get the workspace name/metadata.

---

## Out of Scope

- Frontend (already passes `activeWorkspace` correctly)
- `_tool_query_cases`, `_tool_financial_summary` (main queries), `_tool_cases_financial`, `_tool_claims_analysis`, `_gather_case_context` — already workspace-scoped
- Schema/model changes — not needed

## Risk

Low — all changes are additive `WHERE workspace_id = X` clauses. When `workspace_id` is `None` (no workspace selected), behavior remains unchanged (no filter applied = all data = current behavior).
