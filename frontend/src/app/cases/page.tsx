"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { cases, type CaseSummary, type PaginatedCases } from "@/lib/api";
import { cn, riskColor, priorityColor, statusColor, formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

const STATUS_OPTIONS = ["All", "open", "under_review", "resolved", "closed"] as const;
const PRIORITY_OPTIONS = ["All", "P1", "P2"] as const;

const STATUS_LABELS: Record<string, string> = {
  All: "All",
  open: "Open",
  under_review: "Under Review",
  resolved: "Resolved",
  closed: "Closed",
};

function isPastDeadline(slaDeadline: string | null): boolean {
  if (!slaDeadline) return false;
  return new Date(slaDeadline) < new Date();
}

export default function InvestigationQueuePage() {
  const { activeWorkspace } = useWorkspace();
  const [data, setData] = useState<PaginatedCases | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [priorityFilter, setPriorityFilter] = useState<string>("All");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    setError(null);
    cases
      .list({
        status: statusFilter === "All" ? undefined : statusFilter,
        priority: priorityFilter === "All" ? undefined : priorityFilter,
        page,
        size: 20,
        workspace_id: activeWorkspace,
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [statusFilter, priorityFilter, page, activeWorkspace]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [statusFilter, priorityFilter]);

  return (
    <div>
      {/* Page Title */}
      <h1 className="text-[15px] font-semibold text-text-primary tracking-tight mb-6">Investigation Queue</h1>

      {/* Filter Bar */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-6">
          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-tertiary">Status:</span>
            <div className="flex gap-1">
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    statusFilter === s
                      ? "bg-brand-blue text-white"
                      : "bg-surface-page text-text-secondary hover:bg-border"
                  )}
                >
                  {STATUS_LABELS[s] || s}
                </button>
              ))}
            </div>
          </div>

          {/* Priority filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-tertiary">Priority:</span>
            <div className="flex gap-1">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter(p)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    priorityFilter === p
                      ? "bg-brand-blue text-white"
                      : "bg-surface-page text-text-secondary hover:bg-border"
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-risk-critical-bg border border-risk-critical rounded-lg p-4 mb-6 text-risk-critical-text">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-text-tertiary">Loading cases...</div>
      )}

      {/* Cases Table */}
      {!loading && data && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="table-header">
                <tr>
                  <th>Case ID</th>
                  <th>Claim ID</th>
                  <th>Type</th>
                  <th className="text-right">Risk Score</th>
                  <th>Risk Level</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Assigned To</th>
                  <th>SLA Deadline</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-5 py-8 text-center text-text-tertiary">
                      No cases found.
                    </td>
                  </tr>
                ) : (
                  data.items.map((c: CaseSummary) => {
                    const pastSla = isPastDeadline(c.sla_deadline);
                    return (
                      <tr
                        key={c.id}
                        className="table-row"
                      >
                        <td>
                          <Link
                            href={`/cases/${c.case_id}`}
                            className="text-brand-blue hover:underline font-medium"
                          >
                            {c.case_id}
                          </Link>
                        </td>
                        <td className="text-text-secondary">{c.claim_id}</td>
                        <td className="text-text-secondary capitalize">{c.claim_type}</td>
                        <td className="text-right font-mono font-semibold">
                          {c.risk_score.toFixed(1)}
                        </td>
                        <td>
                          <span
                            className={cn(
                              "badge capitalize",
                              riskColor(c.risk_level)
                            )}
                          >
                            {c.risk_level}
                          </span>
                        </td>
                        <td>
                          <span
                            className={cn(
                              "badge",
                              priorityColor(c.priority)
                            )}
                          >
                            {c.priority || "\u2014"}
                          </span>
                        </td>
                        <td>
                          <span
                            className={cn(
                              "badge",
                              statusColor(c.status)
                            )}
                          >
                            {c.status.replace("_", " ")}
                          </span>
                        </td>
                        <td className="text-text-secondary">
                          {c.assigned_to || <span className="text-text-quaternary">Unassigned</span>}
                        </td>
                        <td
                          className={cn(
                            pastSla ? "text-risk-critical-text font-semibold" : "text-text-secondary"
                          )}
                        >
                          {c.sla_deadline ? formatDateTime(c.sla_deadline) : "\u2014"}
                          {pastSla && <span className="ml-1 text-xs">(overdue)</span>}
                        </td>
                        <td className="text-text-tertiary">
                          {formatDate(c.created_at)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-surface-page">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page <= 1
                    ? "bg-surface-page text-text-quaternary cursor-not-allowed"
                    : "btn-secondary"
                )}
              >
                Previous
              </button>
              <span className="text-sm text-text-tertiary">
                Page {data.page} of {data.pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page >= data.pages
                    ? "bg-surface-page text-text-quaternary cursor-not-allowed"
                    : "btn-secondary"
                )}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
