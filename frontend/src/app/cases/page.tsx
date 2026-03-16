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
      <h1 className="text-2xl font-bold text-t-primary mb-6">Investigation Queue</h1>

      {/* Filter Bar */}
      <div className="glass-card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-6">
          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-t-muted">Status:</span>
            <div className="flex gap-1">
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    statusFilter === s
                      ? "bg-arq-blue-500 text-white"
                      : "bg-surface-2 text-t-secondary hover:bg-surface-3"
                  )}
                >
                  {STATUS_LABELS[s] || s}
                </button>
              ))}
            </div>
          </div>

          {/* Priority filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-t-muted">Priority:</span>
            <div className="flex gap-1">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter(p)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    priorityFilter === p
                      ? "bg-arq-blue-500 text-white"
                      : "bg-surface-2 text-t-secondary hover:bg-surface-3"
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
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mb-6 text-red-400">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-t-muted">Loading cases...</div>
      )}

      {/* Cases Table */}
      {!loading && data && (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="dark-table w-full text-sm">
              <thead>
                <tr>
                  <th className="text-left px-4 py-3">Case ID</th>
                  <th className="text-left px-4 py-3">Claim ID</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-right px-4 py-3">Risk Score</th>
                  <th className="text-left px-4 py-3">Risk Level</th>
                  <th className="text-left px-4 py-3">Priority</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Assigned To</th>
                  <th className="text-left px-4 py-3">SLA Deadline</th>
                  <th className="text-left px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-t-muted">
                      No cases found.
                    </td>
                  </tr>
                ) : (
                  data.items.map((c: CaseSummary) => {
                    const pastSla = isPastDeadline(c.sla_deadline);
                    return (
                      <tr
                        key={c.id}
                        className="border-b border-white/[0.06] hover:bg-surface-2/40 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/cases/${c.case_id}`}
                            className="text-arq-blue-400 hover:underline font-medium"
                          >
                            {c.case_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-t-secondary">{c.claim_id}</td>
                        <td className="px-4 py-3 text-t-secondary capitalize">{c.claim_type}</td>
                        <td className="px-4 py-3 text-right font-mono font-semibold">
                          {c.risk_score.toFixed(1)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "px-2 py-0.5 rounded-full text-xs font-medium capitalize",
                              riskColor(c.risk_level)
                            )}
                          >
                            {c.risk_level}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "px-2 py-0.5 rounded-full text-xs font-medium",
                              priorityColor(c.priority)
                            )}
                          >
                            {c.priority || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "px-2 py-0.5 rounded-full text-xs font-medium",
                              statusColor(c.status)
                            )}
                          >
                            {c.status.replace("_", " ")}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-t-secondary">
                          {c.assigned_to || <span className="text-t-muted">Unassigned</span>}
                        </td>
                        <td
                          className={cn(
                            "px-4 py-3",
                            pastSla ? "text-red-400 font-semibold" : "text-t-secondary"
                          )}
                        >
                          {c.sla_deadline ? formatDateTime(c.sla_deadline) : "—"}
                          {pastSla && <span className="ml-1 text-xs">(overdue)</span>}
                        </td>
                        <td className="px-4 py-3 text-t-muted">
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
            <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.06] bg-surface-2/40">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page <= 1
                    ? "bg-surface-2 text-t-muted cursor-not-allowed"
                    : "bg-surface-2 border border-white/[0.06] text-t-secondary hover:bg-surface-3"
                )}
              >
                Previous
              </button>
              <span className="text-sm text-t-secondary">
                Page {data.page} of {data.pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page >= data.pages
                    ? "bg-surface-2 text-t-muted cursor-not-allowed"
                    : "bg-surface-2 border border-white/[0.06] text-t-secondary hover:bg-surface-3"
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
