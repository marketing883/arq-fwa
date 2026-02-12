"""
Pydantic schemas for API request/response models.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Pagination ──

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    size: int
    pages: int


# ── Dashboard ──

class RiskDistribution(BaseModel):
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class DashboardOverview(BaseModel):
    total_claims: int
    total_flagged: int
    total_fraud_amount: float
    active_cases: int
    recovery_rate: float
    risk_distribution: RiskDistribution


class TrendDataPoint(BaseModel):
    date: str
    claims_processed: int
    claims_flagged: int
    fraud_amount: float


class TrendsResponse(BaseModel):
    period: str
    data: list[TrendDataPoint]


class TopProviderItem(BaseModel):
    provider_id: int
    npi: str
    name: str
    specialty: str | None
    risk_score: float
    flagged_claims: int
    total_amount: float


class TopProvidersResponse(BaseModel):
    providers: list[TopProviderItem]


class RuleEffectivenessItem(BaseModel):
    rule_id: str
    category: str
    fraud_type: str
    times_triggered: int
    avg_severity: float
    total_fraud_amount: float


class RuleEffectivenessResponse(BaseModel):
    rules: list[RuleEffectivenessItem]


# ── Claims ──

class ClaimSummary(BaseModel):
    id: int
    claim_id: str
    claim_type: str
    member_id: int
    provider_id: int | None = None
    pharmacy_id: int | None = None
    service_date: date | None = None
    fill_date: date | None = None
    amount_billed: float
    amount_paid: float | None = None
    status: str
    risk_score: float | None = None
    risk_level: str | None = None
    rules_triggered: int = 0
    batch_id: str | None = None
    created_at: datetime | None = None


class ClaimListResponse(PaginatedResponse):
    items: list[ClaimSummary]


class RuleResultDetail(BaseModel):
    rule_id: str
    triggered: bool
    severity: float | None = None
    confidence: float | None = None
    evidence: dict = {}
    details: str | None = None


class RiskScoreDetail(BaseModel):
    total_score: float
    risk_level: str
    rules_triggered: int
    rule_contributions: dict
    confidence_factor: float


class ClaimDetail(BaseModel):
    id: int
    claim_id: str
    claim_type: str
    # Common fields
    member_id: int
    amount_billed: float
    amount_allowed: float | None = None
    amount_paid: float | None = None
    status: str
    batch_id: str | None = None
    # Medical specific
    provider_id: int | None = None
    service_date: date | None = None
    cpt_code: str | None = None
    cpt_modifier: str | None = None
    diagnosis_code_primary: str | None = None
    place_of_service: str | None = None
    # Pharmacy specific
    pharmacy_id: int | None = None
    prescriber_id: int | None = None
    fill_date: date | None = None
    ndc_code: str | None = None
    drug_name: str | None = None
    days_supply: int | None = None
    is_controlled: bool | None = None
    # Enriched context
    provider_name: str | None = None
    provider_npi: str | None = None
    member_member_id: str | None = None
    # Results
    rule_results: list[RuleResultDetail] = []
    risk_score: RiskScoreDetail | None = None
    created_at: datetime | None = None


class ClaimIngestRequest(BaseModel):
    claims: list[dict]
    claim_type: str = Field(..., pattern="^(medical|pharmacy)$")


class ClaimIngestResponse(BaseModel):
    batch_id: str
    claims_received: int
    message: str


class ProcessBatchRequest(BaseModel):
    batch_id: str | None = None
    claim_type: str | None = None
    limit: int = Field(1000, ge=1, le=10000)


class ProcessBatchResponse(BaseModel):
    batch_id: str
    claims_processed: int
    rules_evaluated: int
    scores_generated: int
    cases_created: int
    processing_time_seconds: float


# ── Rules ──

class RuleSummary(BaseModel):
    rule_id: str
    category: str
    fraud_type: str
    claim_type: str
    description: str | None = None
    detection_logic: str | None = None
    weight: float
    enabled: bool
    thresholds: dict


class RuleListResponse(BaseModel):
    rules: list[RuleSummary]
    total: int


class RuleConfigUpdate(BaseModel):
    weight: float | None = None
    enabled: bool | None = None
    thresholds: dict | None = None


class RuleStats(BaseModel):
    rule_id: str
    category: str
    times_triggered: int
    avg_severity: float
    avg_confidence: float
    total_claims_evaluated: int
    trigger_rate: float


# ── Cases ──

class CaseSummary(BaseModel):
    id: int
    case_id: str
    claim_id: str
    claim_type: str
    risk_level: str
    risk_score: float
    status: str
    priority: str | None = None
    assigned_to: str | None = None
    sla_deadline: datetime | None = None
    created_at: datetime | None = None


class CaseListResponse(PaginatedResponse):
    items: list[CaseSummary]


class CaseNoteSchema(BaseModel):
    id: int | None = None
    content: str
    author: str | None = None
    created_at: datetime | None = None


class CaseEvidenceSchema(BaseModel):
    id: int | None = None
    evidence_type: str
    title: str | None = None
    content: dict = {}
    created_at: datetime | None = None


class CaseDetail(BaseModel):
    id: int
    case_id: str
    claim_id: str
    claim_type: str
    risk_level: str
    risk_score: float
    status: str
    priority: str | None = None
    assigned_to: str | None = None
    resolution_path: str | None = None
    resolution_notes: str | None = None
    sla_deadline: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    notes: list[CaseNoteSchema] = []
    evidence: list[CaseEvidenceSchema] = []
    # Associated data
    claim: ClaimSummary | None = None
    rule_results: list[RuleResultDetail] = []


class CaseStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|under_review|resolved|closed)$")
    resolution_path: str | None = None
    resolution_notes: str | None = None


class CaseAssign(BaseModel):
    assigned_to: str


class CaseNoteCreate(BaseModel):
    content: str
    author: str = "system"


# ── Scoring ──

class ScoringThresholds(BaseModel):
    low_max: float = 30.0
    medium_max: float = 60.0
    high_max: float = 85.0


# ── Audit ──

class AuditEntry(BaseModel):
    id: int
    event_id: str
    event_type: str
    actor: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict = {}
    previous_hash: str | None = None
    current_hash: str
    created_at: datetime | None = None


class AuditListResponse(PaginatedResponse):
    items: list[AuditEntry]


class IntegrityCheckResponse(BaseModel):
    valid: bool
    entries_checked: int
    first_invalid: str | None = None
    reason: str | None = None
