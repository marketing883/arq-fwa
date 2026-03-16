"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { cases, claims, type CaseDetail, type ClaimDetail } from "@/lib/api";
import { cn, riskColor, priorityColor, statusColor, formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { AlertTriangle, Clock, User, MessageSquare, FileText, ChevronRight } from "lucide-react";
import { RuleTraceView } from "@/components/rule-trace";
import { PeerComparisonPanel } from "@/components/peer-comparison";
import { ConfidenceIndicator, ConfidenceBadge } from "@/components/confidence-indicator";
import { useWorkspace } from "@/lib/workspace-context";

const STATUS_OPTIONS = ["open", "under_review", "resolved", "closed"] as const;
const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  under_review: "Under Review",
  resolved: "Resolved",
  closed: "Closed",
};

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { activeWorkspace } = useWorkspace();

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"rules" | "trace" | "peer">("rules");
  const [providerNpi, setProviderNpi] = useState<string | null>(null);

  // Action states
  const [assignInput, setAssignInput] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Evidence bundle
  const [evidenceData, setEvidenceData] = useState<Record<string, unknown> | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  // Expanded rule evidence
  const [expandedRules, setExpandedRules] = useState<Set<string>>(new Set());

  function loadCase() {
    setLoading(true);
    setError(null);
    cases
      .detail(caseId)
      .then(async (data) => {
        setCaseData(data);
        if (data.assigned_to) setAssignInput(data.assigned_to);
        // Fetch provider NPI from claim detail for peer comparison
        if (data.claim_id && data.claim?.provider_id) {
          try {
            const claimData = await claims.detail(data.claim_id);
            if (claimData.provider_npi) setProviderNpi(claimData.provider_npi);
          } catch { /* ignore — peer comparison just won't be available */ }
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (caseId) loadCase();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  async function handleStatusChange(newStatus: string) {
    if (!caseData || actionLoading) return;
    setActionLoading(true);
    try {
      await cases.updateStatus(caseData.case_id, { status: newStatus });
      loadCase();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAssign() {
    if (!caseData || !assignInput.trim() || actionLoading) return;
    setActionLoading(true);
    try {
      await cases.assign(caseData.case_id, assignInput.trim());
      loadCase();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to assign case");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAddNote() {
    if (!caseData || !noteContent.trim() || actionLoading) return;
    setActionLoading(true);
    try {
      await cases.addNote(caseData.case_id, noteContent.trim());
      setNoteContent("");
      loadCase();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleViewEvidence() {
    if (!caseData) return;
    if (evidenceOpen) {
      setEvidenceOpen(false);
      return;
    }
    try {
      const data = await cases.evidence(caseData.case_id);
      setEvidenceData(data);
      setEvidenceOpen(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to load evidence");
    }
  }

  function toggleRuleEvidence(ruleId: string) {
    setExpandedRules((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) {
        next.delete(ruleId);
      } else {
        next.add(ruleId);
      }
      return next;
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-t-muted text-lg">Loading case...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6 text-red-400">
        <h2 className="font-semibold text-lg mb-2">Error loading case</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!caseData) return null;

  // Build timeline entries
  const timelineEntries: { time: string; icon: React.ReactNode; label: string; detail?: string }[] = [];

  // Created event
  if (caseData.created_at) {
    timelineEntries.push({
      time: caseData.created_at,
      icon: <FileText className="w-4 h-4" />,
      label: "Case Created",
      detail: `Case ${caseData.case_id} created from claim ${caseData.claim_id}`,
    });
  }

  // Notes as timeline items
  if (caseData.notes) {
    caseData.notes.forEach((note) => {
      timelineEntries.push({
        time: note.created_at,
        icon: <MessageSquare className="w-4 h-4" />,
        label: `Note by ${note.author}`,
        detail: note.content,
      });
    });
  }

  // Sort timeline by time
  timelineEntries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-t-muted mb-4">
        <Link href="/cases" className="hover:text-arq-blue-400">Investigation Queue</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-t-primary font-medium">{caseData.case_id}</span>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ===== LEFT COLUMN (3/5) ===== */}
        <div className="lg:col-span-3 space-y-6">
          {/* Case Header */}
          <div className="glass-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold mb-2 text-t-primary">{caseData.case_id}</h1>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium", statusColor(caseData.status))}>
                    {caseData.status.replace("_", " ")}
                  </span>
                  <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium", priorityColor(caseData.priority))}>
                    {caseData.priority || "No Priority"}
                  </span>
                  <span className="text-sm text-t-muted capitalize">{caseData.claim_type}</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-t-muted uppercase tracking-wide mb-1">Risk Score</div>
                <div
                  className={cn(
                    "text-3xl font-bold px-4 py-2 rounded-lg",
                    riskColor(caseData.risk_level)
                  )}
                >
                  {caseData.risk_score.toFixed(1)}
                </div>
                <div className="text-xs mt-1 capitalize text-t-secondary">{caseData.risk_level}</div>
              </div>
            </div>
            {caseData.assigned_to && (
              <div className="mt-4 flex items-center gap-2 text-sm text-t-secondary">
                <User className="w-4 h-4" />
                Assigned to: <span className="font-medium">{caseData.assigned_to}</span>
              </div>
            )}
            {caseData.sla_deadline && (
              <div
                className={cn(
                  "mt-2 flex items-center gap-2 text-sm",
                  new Date(caseData.sla_deadline) < new Date()
                    ? "text-red-400 font-semibold"
                    : "text-t-secondary"
                )}
              >
                <Clock className="w-4 h-4" />
                SLA Deadline: {formatDateTime(caseData.sla_deadline)}
                {new Date(caseData.sla_deadline) < new Date() && (
                  <span className="ml-1 text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
                    OVERDUE
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Claim Summary */}
          {caseData.claim && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-t-primary">
                <FileText className="w-5 h-5 text-t-muted" />
                Claim Summary
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-t-muted">Claim ID</span>
                  <p className="font-medium text-t-primary">{caseData.claim.claim_id}</p>
                </div>
                <div>
                  <span className="text-t-muted">Type</span>
                  <p className="font-medium capitalize text-t-primary">{caseData.claim.claim_type}</p>
                </div>
                <div>
                  <span className="text-t-muted">Member ID</span>
                  <p className="font-medium text-t-primary">{caseData.claim.member_id}</p>
                </div>
                <div>
                  <span className="text-t-muted">Provider ID</span>
                  <p className="font-medium text-t-primary">{caseData.claim.provider_id ?? "—"}</p>
                </div>
                <div>
                  <span className="text-t-muted">Service Date</span>
                  <p className="font-medium text-t-primary">{formatDate(caseData.claim.service_date)}</p>
                </div>
                <div>
                  <span className="text-t-muted">Fill Date</span>
                  <p className="font-medium text-t-primary">{formatDate(caseData.claim.fill_date)}</p>
                </div>
                <div>
                  <span className="text-t-muted">Amount Billed</span>
                  <p className="font-medium text-t-primary">{formatCurrency(caseData.claim.amount_billed)}</p>
                </div>
                <div>
                  <span className="text-t-muted">Amount Paid</span>
                  <p className="font-medium text-t-primary">{formatCurrency(caseData.claim.amount_paid)}</p>
                </div>
                <div>
                  <span className="text-t-muted">Status</span>
                  <p className="font-medium capitalize text-t-primary">{caseData.claim.status}</p>
                </div>
                {caseData.claim.pharmacy_id && (
                  <div>
                    <span className="text-t-muted">Pharmacy ID</span>
                    <p className="font-medium text-t-primary">{caseData.claim.pharmacy_id}</p>
                  </div>
                )}
                <div>
                  <span className="text-t-muted">Rules Triggered</span>
                  <p className="font-medium text-t-primary">{caseData.claim.rules_triggered}</p>
                </div>
                {caseData.claim.risk_level && (
                  <div>
                    <span className="text-t-muted">Risk Level</span>
                    <p>
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize", riskColor(caseData.claim.risk_level))}>
                        {caseData.claim.risk_level}
                      </span>
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Transparency Tabs */}
          <div className="glass-card">
            {/* Tab bar */}
            <div className="flex border-b border-white/[0.06]">
              {[
                { key: "rules" as const, label: "Rules Triggered", icon: <AlertTriangle className="w-4 h-4" /> },
                { key: "trace" as const, label: "Rule Trace", icon: <FileText className="w-4 h-4" /> },
                ...(providerNpi ? [{ key: "peer" as const, label: "Peer Comparison", icon: <User className="w-4 h-4" /> }] : []),
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    "flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
                    activeTab === tab.key
                      ? "border-arq-blue-400 text-arq-blue-400"
                      : "border-transparent text-t-muted hover:text-t-secondary hover:border-white/[0.06]"
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="p-6">
              {activeTab === "rules" && (
                <>
                  {caseData.rule_results.length === 0 ? (
                    <p className="text-t-muted text-sm">No rules triggered for this case.</p>
                  ) : (
                    <div className="space-y-3">
                      {caseData.rule_results
                        .filter((r) => r.triggered)
                        .map((rule) => (
                          <div
                            key={rule.rule_id}
                            className="border border-white/[0.06] rounded-lg p-4"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1">
                                <div className="flex items-center gap-3 mb-2">
                                  <span className="font-mono text-sm font-semibold text-t-primary">
                                    {rule.rule_id}
                                  </span>
                                  {rule.confidence != null && (
                                    <ConfidenceBadge confidence={rule.confidence} />
                                  )}
                                </div>
                                {rule.severity != null && (
                                  <div className="mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-t-muted w-16">Severity</span>
                                      <div className="flex-1 bg-surface-3 rounded-full h-2 max-w-xs">
                                        <div
                                          className={cn(
                                            "h-2 rounded-full",
                                            rule.severity >= 2.5
                                              ? "bg-red-500"
                                              : rule.severity >= 1.5
                                              ? "bg-amber-500"
                                              : "bg-green-500"
                                          )}
                                          style={{
                                            width: `${Math.min(100, (rule.severity / 3.0) * 100)}%`,
                                          }}
                                        />
                                      </div>
                                      <span className="text-xs font-mono text-t-secondary w-8">
                                        {rule.severity.toFixed(1)}
                                      </span>
                                    </div>
                                  </div>
                                )}
                                {rule.details && (
                                  <p className="text-sm text-t-secondary mb-2">{rule.details}</p>
                                )}
                              </div>
                            </div>
                            {rule.evidence && Object.keys(rule.evidence).length > 0 && (
                              <div>
                                <button
                                  onClick={() => toggleRuleEvidence(rule.rule_id)}
                                  className="text-xs text-arq-blue-400 hover:underline flex items-center gap-1 mt-1"
                                >
                                  <ChevronRight
                                    className={cn(
                                      "w-3 h-3 transition-transform",
                                      expandedRules.has(rule.rule_id) && "rotate-90"
                                    )}
                                  />
                                  {expandedRules.has(rule.rule_id) ? "Hide" : "Show"} Evidence
                                </button>
                                {expandedRules.has(rule.rule_id) && (
                                  <pre className="mt-2 bg-surface-2 border border-white/[0.06] rounded p-3 text-xs overflow-x-auto max-h-60 text-t-secondary">
                                    {JSON.stringify(rule.evidence, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </>
              )}

              {activeTab === "trace" && (
                <RuleTraceView claimId={caseData.claim_id} />
              )}

              {activeTab === "peer" && providerNpi && (
                <PeerComparisonPanel
                  npi={providerNpi}
                  workspaceId={activeWorkspace}
                />
              )}
            </div>
          </div>

          {/* Overall Confidence */}
          {caseData.rule_results.filter(r => r.triggered && r.confidence != null).length > 0 && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4 text-t-primary">Detection Confidence</h2>
              <div className="flex items-center gap-8 flex-wrap">
                {caseData.rule_results
                  .filter(r => r.triggered && r.confidence != null)
                  .slice(0, 5)
                  .map((rule) => (
                    <div key={rule.rule_id} className="flex flex-col items-center">
                      <ConfidenceIndicator
                        confidence={rule.confidence!}
                        label={rule.rule_id}
                        size="sm"
                      />
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* ===== RIGHT COLUMN (2/5) ===== */}
        <div className="lg:col-span-2 space-y-6">
          {/* Actions Panel */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wide mb-4">
              Actions
            </h3>

            {/* Status buttons */}
            <div className="mb-4">
              <label className="text-sm font-medium text-t-secondary block mb-2">Update Status</label>
              <div className="flex flex-wrap gap-1.5">
                {STATUS_OPTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    disabled={actionLoading || caseData.status === s}
                    className={cn(
                      "px-3 py-1.5 text-xs rounded-md transition-colors font-medium",
                      caseData.status === s
                        ? "bg-arq-blue-500 text-white cursor-default"
                        : "bg-surface-2 text-t-secondary hover:bg-surface-3",
                      actionLoading && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {STATUS_LABELS[s]}
                  </button>
                ))}
              </div>
            </div>

            {/* Assign */}
            <div>
              <label className="text-sm font-medium text-t-secondary block mb-2">Assign To</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={assignInput}
                  onChange={(e) => setAssignInput(e.target.value)}
                  placeholder="Enter assignee name"
                  className="flex-1 bg-surface-2 border border-surface-3 text-t-primary rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:border-arq-blue-400 focus:ring-arq-blue-400/30"
                />
                <button
                  onClick={handleAssign}
                  disabled={actionLoading || !assignInput.trim()}
                  className={cn(
                    "px-4 py-2 text-sm rounded-md font-medium transition-colors",
                    actionLoading || !assignInput.trim()
                      ? "bg-surface-2 text-t-muted cursor-not-allowed"
                      : "bg-arq-blue-500 text-white hover:bg-arq-blue-600"
                  )}
                >
                  Assign
                </button>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wide mb-4">
              Timeline
            </h3>
            {timelineEntries.length === 0 ? (
              <p className="text-t-muted text-sm">No timeline events.</p>
            ) : (
              <div className="space-y-0">
                {timelineEntries.map((entry, idx) => (
                  <div key={idx} className="flex gap-3 pb-4 relative">
                    {/* Vertical line */}
                    {idx < timelineEntries.length - 1 && (
                      <div className="absolute left-[11px] top-6 bottom-0 w-px bg-surface-3" />
                    )}
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-surface-2 flex items-center justify-center text-t-muted z-10">
                      {entry.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-t-primary">{entry.label}</p>
                      {entry.detail && (
                        <p className="text-sm text-t-secondary mt-0.5 break-words">{entry.detail}</p>
                      )}
                      <p className="text-xs text-t-muted mt-1">{formatDateTime(entry.time)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Add Note */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wide mb-4">
              Add Note
            </h3>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              rows={3}
              placeholder="Enter investigation notes..."
              className="w-full bg-surface-2 border border-surface-3 text-t-primary rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:border-arq-blue-400 focus:ring-arq-blue-400/30 resize-none"
            />
            <button
              onClick={handleAddNote}
              disabled={actionLoading || !noteContent.trim()}
              className={cn(
                "mt-2 w-full px-4 py-2 text-sm rounded-md font-medium transition-colors",
                actionLoading || !noteContent.trim()
                  ? "bg-surface-2 text-t-muted cursor-not-allowed"
                  : "bg-arq-blue-500 text-white hover:bg-arq-blue-600"
              )}
            >
              Add Note
            </button>
          </div>

          {/* Evidence Bundle */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wide mb-4">
              Evidence Bundle
            </h3>
            <button
              onClick={handleViewEvidence}
              className="w-full px-4 py-2 text-sm rounded-md font-medium bg-surface-2 text-t-secondary hover:bg-surface-3 transition-colors"
            >
              {evidenceOpen ? "Hide Evidence" : "View Evidence"}
            </button>
            {evidenceOpen && evidenceData && (
              <pre className="mt-3 bg-surface-2 border border-white/[0.06] rounded-lg p-4 text-xs overflow-x-auto max-h-96 text-t-secondary">
                {JSON.stringify(evidenceData, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
