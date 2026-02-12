"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { cases, type CaseDetail } from "@/lib/api";
import { cn, riskColor, priorityColor, statusColor, formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { AlertTriangle, Clock, User, MessageSquare, FileText, ChevronRight } from "lucide-react";

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

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      .then((data) => {
        setCaseData(data);
        if (data.assigned_to) setAssignInput(data.assigned_to);
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
        <div className="text-gray-500 text-lg">Loading case...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
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
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <a href="/cases" className="hover:text-blue-600">Investigation Queue</a>
        <ChevronRight className="w-4 h-4" />
        <span className="text-gray-900 font-medium">{caseData.case_id}</span>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ===== LEFT COLUMN (3/5) ===== */}
        <div className="lg:col-span-3 space-y-6">
          {/* Case Header */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold mb-2">{caseData.case_id}</h1>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium", statusColor(caseData.status))}>
                    {caseData.status.replace("_", " ")}
                  </span>
                  <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium", priorityColor(caseData.priority))}>
                    {caseData.priority || "No Priority"}
                  </span>
                  <span className="text-sm text-gray-500 capitalize">{caseData.claim_type}</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Risk Score</div>
                <div
                  className={cn(
                    "text-3xl font-bold px-4 py-2 rounded-lg",
                    riskColor(caseData.risk_level)
                  )}
                >
                  {caseData.risk_score.toFixed(1)}
                </div>
                <div className="text-xs mt-1 capitalize text-gray-600">{caseData.risk_level}</div>
              </div>
            </div>
            {caseData.assigned_to && (
              <div className="mt-4 flex items-center gap-2 text-sm text-gray-600">
                <User className="w-4 h-4" />
                Assigned to: <span className="font-medium">{caseData.assigned_to}</span>
              </div>
            )}
            {caseData.sla_deadline && (
              <div
                className={cn(
                  "mt-2 flex items-center gap-2 text-sm",
                  new Date(caseData.sla_deadline) < new Date()
                    ? "text-red-600 font-semibold"
                    : "text-gray-600"
                )}
              >
                <Clock className="w-4 h-4" />
                SLA Deadline: {formatDateTime(caseData.sla_deadline)}
                {new Date(caseData.sla_deadline) < new Date() && (
                  <span className="ml-1 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                    OVERDUE
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Claim Summary */}
          {caseData.claim && (
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-gray-500" />
                Claim Summary
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Claim ID</span>
                  <p className="font-medium">{caseData.claim.claim_id}</p>
                </div>
                <div>
                  <span className="text-gray-500">Type</span>
                  <p className="font-medium capitalize">{caseData.claim.claim_type}</p>
                </div>
                <div>
                  <span className="text-gray-500">Member ID</span>
                  <p className="font-medium">{caseData.claim.member_id}</p>
                </div>
                <div>
                  <span className="text-gray-500">Provider ID</span>
                  <p className="font-medium">{caseData.claim.provider_id ?? "—"}</p>
                </div>
                <div>
                  <span className="text-gray-500">Service Date</span>
                  <p className="font-medium">{formatDate(caseData.claim.service_date)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Fill Date</span>
                  <p className="font-medium">{formatDate(caseData.claim.fill_date)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Amount Billed</span>
                  <p className="font-medium">{formatCurrency(caseData.claim.amount_billed)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Amount Paid</span>
                  <p className="font-medium">{formatCurrency(caseData.claim.amount_paid)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Status</span>
                  <p className="font-medium capitalize">{caseData.claim.status}</p>
                </div>
                {caseData.claim.pharmacy_id && (
                  <div>
                    <span className="text-gray-500">Pharmacy ID</span>
                    <p className="font-medium">{caseData.claim.pharmacy_id}</p>
                  </div>
                )}
                <div>
                  <span className="text-gray-500">Rules Triggered</span>
                  <p className="font-medium">{caseData.claim.rules_triggered}</p>
                </div>
                {caseData.claim.risk_level && (
                  <div>
                    <span className="text-gray-500">Risk Level</span>
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

          {/* Rules Triggered */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Rules Triggered
            </h2>
            {caseData.rule_results.length === 0 ? (
              <p className="text-gray-500 text-sm">No rules triggered for this case.</p>
            ) : (
              <div className="space-y-3">
                {caseData.rule_results
                  .filter((r) => r.triggered)
                  .map((rule) => (
                    <div
                      key={rule.rule_id}
                      className="border border-gray-200 rounded-lg p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-mono text-sm font-semibold text-gray-900">
                              {rule.rule_id}
                            </span>
                            {rule.confidence != null && (
                              <span className="text-xs text-gray-500">
                                Confidence: {(rule.confidence * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          {/* Severity bar */}
                          {rule.severity != null && (
                            <div className="mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-500 w-16">Severity</span>
                                <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
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
                                <span className="text-xs font-mono text-gray-600 w-8">
                                  {rule.severity.toFixed(1)}
                                </span>
                              </div>
                            </div>
                          )}
                          {rule.details && (
                            <p className="text-sm text-gray-600 mb-2">{rule.details}</p>
                          )}
                        </div>
                      </div>
                      {/* Collapsible evidence */}
                      {rule.evidence && Object.keys(rule.evidence).length > 0 && (
                        <div>
                          <button
                            onClick={() => toggleRuleEvidence(rule.rule_id)}
                            className="text-xs text-blue-600 hover:underline flex items-center gap-1 mt-1"
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
                            <pre className="mt-2 bg-gray-50 border border-gray-200 rounded p-3 text-xs overflow-x-auto max-h-60">
                              {JSON.stringify(rule.evidence, null, 2)}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        {/* ===== RIGHT COLUMN (2/5) ===== */}
        <div className="lg:col-span-2 space-y-6">
          {/* Actions Panel */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Actions
            </h3>

            {/* Status buttons */}
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700 block mb-2">Update Status</label>
              <div className="flex flex-wrap gap-1.5">
                {STATUS_OPTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    disabled={actionLoading || caseData.status === s}
                    className={cn(
                      "px-3 py-1.5 text-xs rounded-md transition-colors font-medium",
                      caseData.status === s
                        ? "bg-blue-600 text-white cursor-default"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200",
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
              <label className="text-sm font-medium text-gray-700 block mb-2">Assign To</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={assignInput}
                  onChange={(e) => setAssignInput(e.target.value)}
                  placeholder="Enter assignee name"
                  className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={handleAssign}
                  disabled={actionLoading || !assignInput.trim()}
                  className={cn(
                    "px-4 py-2 text-sm rounded-md font-medium transition-colors",
                    actionLoading || !assignInput.trim()
                      ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  )}
                >
                  Assign
                </button>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Timeline
            </h3>
            {timelineEntries.length === 0 ? (
              <p className="text-gray-500 text-sm">No timeline events.</p>
            ) : (
              <div className="space-y-0">
                {timelineEntries.map((entry, idx) => (
                  <div key={idx} className="flex gap-3 pb-4 relative">
                    {/* Vertical line */}
                    {idx < timelineEntries.length - 1 && (
                      <div className="absolute left-[11px] top-6 bottom-0 w-px bg-gray-200" />
                    )}
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 z-10">
                      {entry.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{entry.label}</p>
                      {entry.detail && (
                        <p className="text-sm text-gray-600 mt-0.5 break-words">{entry.detail}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">{formatDateTime(entry.time)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Add Note */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Add Note
            </h3>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              rows={3}
              placeholder="Enter investigation notes..."
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
            <button
              onClick={handleAddNote}
              disabled={actionLoading || !noteContent.trim()}
              className={cn(
                "mt-2 w-full px-4 py-2 text-sm rounded-md font-medium transition-colors",
                actionLoading || !noteContent.trim()
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              )}
            >
              Add Note
            </button>
          </div>

          {/* Evidence Bundle */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Evidence Bundle
            </h3>
            <button
              onClick={handleViewEvidence}
              className="w-full px-4 py-2 text-sm rounded-md font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              {evidenceOpen ? "Hide Evidence" : "View Evidence"}
            </button>
            {evidenceOpen && evidenceData && (
              <pre className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs overflow-x-auto max-h-96">
                {JSON.stringify(evidenceData, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
