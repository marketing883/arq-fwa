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
      <h1 className="text-2xl font-bold mb-6">Investigation Queue</h1>

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 mb-6">
        <div className="flex flex-wrap items-center gap-6">
          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-600">Status:</span>
            <div className="flex gap-1">
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    statusFilter === s
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  )}
                >
                  {STATUS_LABELS[s] || s}
                </button>
              ))}
            </div>
          </div>

          {/* Priority filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-600">Priority:</span>
            <div className="flex gap-1">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter(p)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md transition-colors",
                    priorityFilter === p
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
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
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-gray-500">Loading cases...</div>
      )}

      {/* Cases Table */}
      {!loading && data && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Case ID</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Claim ID</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Type</th>
                  <th className="text-right px-4 py-3 font-semibold text-gray-600">Risk Score</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Risk Level</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Priority</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Assigned To</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">SLA Deadline</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-gray-500">
                      No cases found.
                    </td>
                  </tr>
                ) : (
                  data.items.map((c: CaseSummary) => {
                    const pastSla = isPastDeadline(c.sla_deadline);
                    return (
                      <tr
                        key={c.id}
                        className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/cases/${c.case_id}`}
                            className="text-blue-600 hover:underline font-medium"
                          >
                            {c.case_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-gray-700">{c.claim_id}</td>
                        <td className="px-4 py-3 text-gray-700 capitalize">{c.claim_type}</td>
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
                        <td className="px-4 py-3 text-gray-700">
                          {c.assigned_to || <span className="text-gray-400">Unassigned</span>}
                        </td>
                        <td
                          className={cn(
                            "px-4 py-3",
                            pastSla ? "text-red-600 font-semibold" : "text-gray-700"
                          )}
                        >
                          {c.sla_deadline ? formatDateTime(c.sla_deadline) : "—"}
                          {pastSla && <span className="ml-1 text-xs">(overdue)</span>}
                        </td>
                        <td className="px-4 py-3 text-gray-500">
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
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page <= 1
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                    : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                )}
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {data.page} of {data.pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className={cn(
                  "px-4 py-2 text-sm rounded-md",
                  page >= data.pages
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                    : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
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
