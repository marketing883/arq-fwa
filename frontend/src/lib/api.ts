/**
 * API client for ArqAI FWA Detection backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

/** Append workspace_id to query string if provided */
function wsParam(qs: URLSearchParams, workspaceId?: string | null) {
  if (workspaceId) qs.set("workspace_id", workspaceId);
}

// ── Dashboard ──

export interface RiskDistribution {
  low: number;
  medium: number;
  high: number;
  critical: number;
}

export interface DashboardOverview {
  total_claims: number;
  total_flagged: number;
  total_fraud_amount: number;
  active_cases: number;
  recovery_rate: number;
  risk_distribution: RiskDistribution;
}

export interface TrendDataPoint {
  date: string;
  claims_processed: number;
  claims_flagged: number;
  fraud_amount: number;
}

export interface TopProviderItem {
  provider_id: number;
  npi: string;
  name: string;
  specialty: string | null;
  risk_score: number;
  flagged_claims: number;
  total_amount: number;
}

export interface RuleEffectivenessItem {
  rule_id: string;
  category: string;
  fraud_type: string;
  times_triggered: number;
  avg_severity: number;
  total_fraud_amount: number;
}

export const dashboard = {
  overview: (workspaceId?: string | null) => {
    const qs = new URLSearchParams();
    wsParam(qs, workspaceId);
    const q = qs.toString();
    return fetchAPI<DashboardOverview>(`/dashboard/overview${q ? `?${q}` : ""}`);
  },
  trends: (period: string = "30d", workspaceId?: string | null) => {
    const qs = new URLSearchParams({ period });
    wsParam(qs, workspaceId);
    return fetchAPI<{ period: string; data: TrendDataPoint[] }>(`/dashboard/trends?${qs}`);
  },
  topProviders: (limit: number = 10, workspaceId?: string | null) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    wsParam(qs, workspaceId);
    return fetchAPI<{ providers: TopProviderItem[] }>(`/dashboard/top-providers?${qs}`);
  },
  ruleEffectiveness: (workspaceId?: string | null) => {
    const qs = new URLSearchParams();
    wsParam(qs, workspaceId);
    const q = qs.toString();
    return fetchAPI<{ rules: RuleEffectivenessItem[] }>(`/dashboard/rule-effectiveness${q ? `?${q}` : ""}`);
  },
};

// ── Claims ──

export interface ClaimSummary {
  id: number;
  claim_id: string;
  claim_type: string;
  member_id: number;
  provider_id: number | null;
  pharmacy_id: number | null;
  service_date: string | null;
  fill_date: string | null;
  amount_billed: number;
  amount_paid: number | null;
  status: string;
  risk_score: number | null;
  risk_level: string | null;
  rules_triggered: number;
  batch_id: string | null;
  created_at: string | null;
}

export interface RuleResultDetail {
  rule_id: string;
  triggered: boolean;
  severity: number | null;
  confidence: number | null;
  evidence: Record<string, unknown>;
  details: string | null;
}

export interface RiskScoreDetail {
  total_score: number;
  risk_level: string;
  rules_triggered: number;
  rule_contributions: Record<string, unknown>;
  confidence_factor: number;
}

export interface ClaimDetail {
  id: number;
  claim_id: string;
  claim_type: string;
  member_id: number;
  amount_billed: number;
  amount_allowed: number | null;
  amount_paid: number | null;
  status: string;
  provider_id: number | null;
  service_date: string | null;
  cpt_code: string | null;
  diagnosis_code_primary: string | null;
  pharmacy_id: number | null;
  fill_date: string | null;
  ndc_code: string | null;
  drug_name: string | null;
  days_supply: number | null;
  provider_name: string | null;
  provider_npi: string | null;
  member_member_id: string | null;
  rule_results: RuleResultDetail[];
  risk_score: RiskScoreDetail | null;
}

export interface PaginatedClaims {
  total: number;
  page: number;
  size: number;
  pages: number;
  items: ClaimSummary[];
}

// ── Rule Trace ──

export interface RuleTraceStep {
  step: number;
  rule_id: string;
  rule_name: string;
  category: string;
  fraud_type: string;
  triggered: boolean;
  severity: number | null;
  confidence: number | null;
  weight: number | null;
  contribution: number | null;
  explanation: string;
  evidence: Record<string, unknown>;
}

export interface RuleTrace {
  claim_id: string;
  total_score: number;
  risk_level: string;
  steps: RuleTraceStep[];
  score_calculation: {
    formula: string;
    rules_triggered: number;
    rules_passed: number;
  };
}

export const claims = {
  list: (params: { type?: string; risk_level?: string; status?: string; page?: number; size?: number; workspace_id?: string | null }) => {
    const qs = new URLSearchParams();
    if (params.type) qs.set("type", params.type);
    if (params.risk_level) qs.set("risk_level", params.risk_level);
    if (params.status) qs.set("status", params.status);
    qs.set("page", String(params.page || 1));
    qs.set("size", String(params.size || 50));
    wsParam(qs, params.workspace_id);
    return fetchAPI<PaginatedClaims>(`/claims?${qs}`);
  },
  detail: (claimId: string) => fetchAPI<ClaimDetail>(`/claims/${claimId}`),
  ruleTrace: (claimId: string) => fetchAPI<RuleTrace>(`/claims/${claimId}/rule-trace`),
  processBatch: (body: { limit?: number; claim_type?: string; batch_id?: string }) =>
    fetchAPI<{ batch_id: string; claims_processed: number; rules_evaluated: number; scores_generated: number; cases_created: number; processing_time_seconds: number }>(
      "/claims/process-batch",
      { method: "POST", body: JSON.stringify(body) }
    ),
};

// ── Rules ──

export interface RuleSummary {
  rule_id: string;
  category: string;
  fraud_type: string;
  claim_type: string;
  description: string | null;
  detection_logic: string | null;
  weight: number;
  enabled: boolean;
  thresholds: Record<string, unknown>;
}

export interface RuleStats {
  rule_id: string;
  category: string;
  times_triggered: number;
  avg_severity: number;
  avg_confidence: number;
  total_claims_evaluated: number;
  trigger_rate: number;
}

export const rules = {
  list: () => fetchAPI<{ rules: RuleSummary[]; total: number }>("/rules"),
  detail: (ruleId: string) => fetchAPI<RuleSummary>(`/rules/${ruleId}`),
  updateConfig: (ruleId: string, body: { weight?: number; enabled?: boolean; thresholds?: Record<string, unknown> }) =>
    fetchAPI<RuleSummary>(`/rules/${ruleId}/config`, { method: "PUT", body: JSON.stringify(body) }),
  stats: (ruleId: string) => fetchAPI<RuleStats>(`/rules/${ruleId}/stats`),
};

// ── Cases ──

export interface CaseSummary {
  id: number;
  case_id: string;
  claim_id: string;
  claim_type: string;
  risk_level: string;
  risk_score: number;
  status: string;
  priority: string | null;
  assigned_to: string | null;
  sla_deadline: string | null;
  created_at: string | null;
}

export interface CaseNote {
  id: number;
  content: string;
  author: string;
  created_at: string;
}

export interface CaseDetail extends CaseSummary {
  resolution_path: string | null;
  resolution_notes: string | null;
  updated_at: string | null;
  notes: CaseNote[];
  evidence: { id: number; evidence_type: string; title: string; content: Record<string, unknown>; created_at: string }[];
  claim: ClaimSummary | null;
  rule_results: RuleResultDetail[];
}

export interface PaginatedCases {
  total: number;
  page: number;
  size: number;
  pages: number;
  items: CaseSummary[];
}

export const cases = {
  list: (params: { status?: string; priority?: string; page?: number; size?: number; workspace_id?: string | null }) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.priority) qs.set("priority", params.priority);
    qs.set("page", String(params.page || 1));
    qs.set("size", String(params.size || 20));
    wsParam(qs, params.workspace_id);
    return fetchAPI<PaginatedCases>(`/cases?${qs}`);
  },
  detail: (caseId: string) => fetchAPI<CaseDetail>(`/cases/${caseId}`),
  updateStatus: (caseId: string, body: { status: string; resolution_path?: string; resolution_notes?: string }) =>
    fetchAPI<CaseDetail>(`/cases/${caseId}/status`, { method: "PUT", body: JSON.stringify(body) }),
  assign: (caseId: string, assignedTo: string) =>
    fetchAPI<CaseDetail>(`/cases/${caseId}/assign`, { method: "PUT", body: JSON.stringify({ assigned_to: assignedTo }) }),
  addNote: (caseId: string, content: string, author: string = "admin") =>
    fetchAPI<CaseNote>(`/cases/${caseId}/notes`, { method: "POST", body: JSON.stringify({ content, author }) }),
  evidence: (caseId: string) => fetchAPI<Record<string, unknown>>(`/cases/${caseId}/evidence`),
};

// ── Audit ──

export interface AuditEntry {
  id: number;
  event_id: string;
  event_type: string;
  actor: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  current_hash: string;
  created_at: string | null;
}

export interface PaginatedAudit {
  total: number;
  page: number;
  size: number;
  pages: number;
  items: AuditEntry[];
}

export const audit = {
  list: (params: { event_type?: string; resource_type?: string; page?: number; size?: number }) => {
    const qs = new URLSearchParams();
    if (params.event_type) qs.set("event_type", params.event_type);
    if (params.resource_type) qs.set("resource_type", params.resource_type);
    qs.set("page", String(params.page || 1));
    qs.set("size", String(params.size || 50));
    return fetchAPI<PaginatedAudit>(`/audit?${qs}`);
  },
  integrity: () => fetchAPI<{ valid: boolean; entries_checked: number; first_invalid: string | null }>("/audit/integrity"),
};

// ── Scoring ──

export const scoring = {
  thresholds: () => fetchAPI<{ low_max: number; medium_max: number; high_max: number }>("/scoring/thresholds"),
};

// ── Workspaces ──

export interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  client_name: string | null;
  description: string | null;
  data_source: string;
  status: string;
  claim_count: number;
  created_at: string | null;
}

export const workspaces = {
  list: () => fetchAPI<{ workspaces: WorkspaceSummary[]; total: number }>("/workspaces"),
  create: (body: { name: string; client_name?: string; description?: string }) =>
    fetchAPI<WorkspaceSummary>("/workspaces", { method: "POST", body: JSON.stringify(body) }),
  detail: (id: string) => fetchAPI<WorkspaceSummary>(`/workspaces/${id}`),
  archive: (id: string) => fetch(`${API_BASE}/workspaces/${id}`, { method: "DELETE" }),
};

// ── Pipeline ──

export interface PipelineRunResponse {
  batch_id: string;
  total_claims: number;
  medical_claims: number;
  pharmacy_claims: number;
  rules_evaluated: number;
  scores_generated: number;
  cases_created: number;
  high_risk: number;
  critical_risk: number;
  processing_time_seconds: number;
}

export interface PipelineJobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: PipelineRunResponse;
  error?: string;
  queued_at?: string;
}

export interface PipelineRunRecord {
  run_id: string;
  workspace_id: number | null;
  batch_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  duration_seconds: number | null;
  stats: Record<string, unknown>;
  quality_report: Record<string, unknown> | null;
}

export const pipeline = {
  runFull: (body: { limit?: number; workspace_id?: string | null; force_reprocess?: boolean }) =>
    fetchAPI<PipelineRunResponse>("/pipeline/run-full", { method: "POST", body: JSON.stringify(body) }),
  status: () => fetchAPI<Record<string, number>>("/pipeline/status"),
  enqueue: (body: { limit?: number; workspace_id?: string | null }) =>
    fetchAPI<{ job_id: string; status: string }>("/pipeline/enqueue", { method: "POST", body: JSON.stringify(body) }),
  jobStatus: (jobId: string) => fetchAPI<PipelineJobStatus>(`/pipeline/jobs/${jobId}`),
  runs: (limit: number = 20) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    return fetchAPI<{ runs: PipelineRunRecord[] }>(`/pipeline/runs?${qs}`);
  },
  runDetail: (runId: string) => fetchAPI<PipelineRunRecord>(`/pipeline/runs/${runId}`),
};

// ── Providers ──

export interface PeerMetric {
  metric: string;
  provider_value: number;
  peer_average: number;
  peer_p75: number;
  peer_p90: number;
  percentile: number;
  anomaly: boolean;
}

export interface PeerComparison {
  provider: { npi: string; name: string; specialty: string };
  peer_group: string;
  metrics: PeerMetric[];
}

// ── Agents ──

export interface InvestigateResponse {
  case_id: string;
  summary: string;
  findings: string[];
  risk_assessment: string;
  recommended_actions: string[];
  confidence: number;
  model_used: string;
  generated_at: string;
}

export interface AgentChatResponse {
  response: string;
  sources_cited: string[];
  model_used: string;
  confidence: string;
  session_id?: string;
}

export interface AgentStatus {
  status: "ready" | "loading";
  model: string;
  mode: "slm" | "data-engine";
  detail?: string;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  case_id: string | null;
  message_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChatMessageItem {
  role: "user" | "assistant";
  content: string;
  sources_cited: string[] | null;
  model_used: string | null;
  confidence: string | null;
  created_at: string | null;
}

export const agents = {
  status: () => fetchAPI<AgentStatus>("/agents/status"),
  investigate: (caseId: string, question?: string, workspaceId?: string | null) =>
    fetchAPI<InvestigateResponse>("/agents/investigate", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, question, workspace_id: workspaceId || undefined }),
    }),
  chat: (message: string, caseId?: string | null, sessionId?: string | null, workspaceId?: string | null) =>
    fetchAPI<AgentChatResponse>("/agents/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        case_id: caseId || undefined,
        session_id: sessionId || undefined,
        workspace_id: workspaceId || undefined,
      }),
    }),
  sessions: (workspaceId?: string | null, limit: number = 20) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    wsParam(qs, workspaceId);
    return fetchAPI<{ sessions: ChatSessionSummary[] }>(`/agents/sessions?${qs}`);
  },
  sessionMessages: (sessionId: string, limit: number = 50) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    return fetchAPI<{ session_id: string; messages: ChatMessageItem[] }>(`/agents/sessions/${sessionId}/messages?${qs}`);
  },
  newSession: (workspaceId?: string | null, caseId?: string | null) => {
    const qs = new URLSearchParams();
    wsParam(qs, workspaceId);
    if (caseId) qs.set("case_id", caseId);
    const q = qs.toString();
    return fetchAPI<{ session_id: string }>(`/agents/sessions/new${q ? `?${q}` : ""}`, { method: "POST" });
  },
};

export const providers = {
  peerComparison: (npi: string, workspaceId?: string | null) => {
    const qs = new URLSearchParams();
    wsParam(qs, workspaceId);
    const q = qs.toString();
    return fetchAPI<PeerComparison>(`/providers/${npi}/peer-comparison${q ? `?${q}` : ""}`);
  },
};
