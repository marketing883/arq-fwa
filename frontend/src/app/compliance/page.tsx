"use client";
import { useEffect, useState } from "react";
import { audit, type AuditEntry, type PaginatedAudit } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";
import { Shield, CheckCircle, XCircle, RefreshCw } from "lucide-react";

const EVENT_TYPES = [
  "all",
  "claim_processed",
  "case_created",
  "case_updated",
  "rule_triggered",
  "rule_config_changed",
  "integrity_check",
  "user_action",
];

const RESOURCE_TYPES = [
  "all",
  "claim",
  "case",
  "rule",
  "audit",
  "provider",
  "member",
];

type Tab = "audit" | "integrity";

interface IntegrityResult {
  valid: boolean;
  entries_checked: number;
  first_invalid: string | null;
}

export default function CompliancePage() {
  // ── Tab state ──
  const [activeTab, setActiveTab] = useState<Tab>("audit");

  // ── Audit Log state ──
  const [auditData, setAuditData] = useState<PaginatedAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(true);
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  // ── Integrity Check state ──
  const [integrityResult, setIntegrityResult] =
    useState<IntegrityResult | null>(null);
  const [integrityLoading, setIntegrityLoading] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<Date | null>(null);

  // ── Fetch audit log ──
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setAuditLoading(true);
      try {
        const data = await audit.list({
          event_type: eventTypeFilter === "all" ? undefined : eventTypeFilter,
          resource_type:
            resourceTypeFilter === "all" ? undefined : resourceTypeFilter,
          page,
          size: 20,
        });
        if (!cancelled) setAuditData(data);
      } catch (err) {
        console.error("Failed to load audit log:", err);
      } finally {
        if (!cancelled) setAuditLoading(false);
      }
    }
    if (activeTab === "audit") load();
    return () => {
      cancelled = true;
    };
  }, [activeTab, eventTypeFilter, resourceTypeFilter, page]);

  // ── Integrity check handler ──
  async function runIntegrityCheck() {
    setIntegrityLoading(true);
    setIntegrityResult(null);
    try {
      const result = await audit.integrity();
      setIntegrityResult(result);
      setLastCheckTime(new Date());
    } catch (err) {
      console.error("Integrity check failed:", err);
      setIntegrityResult({
        valid: false,
        entries_checked: 0,
        first_invalid: "Error running integrity check",
      });
      setLastCheckTime(new Date());
    } finally {
      setIntegrityLoading(false);
    }
  }

  // ── Reset page when filters change ──
  function handleEventTypeChange(value: string) {
    setEventTypeFilter(value);
    setPage(1);
    setExpandedRow(null);
  }

  function handleResourceTypeChange(value: string) {
    setResourceTypeFilter(value);
    setPage(1);
    setExpandedRow(null);
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Compliance &amp; Audit
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Audit trail and blockchain-style integrity verification
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          <button
            onClick={() => setActiveTab("audit")}
            className={cn(
              "pb-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === "audit"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            Audit Log
          </button>
          <button
            onClick={() => setActiveTab("integrity")}
            className={cn(
              "pb-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === "integrity"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            Integrity Check
          </button>
        </nav>
      </div>

      {/* ── Audit Log Tab ── */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label
                htmlFor="event-type"
                className="text-sm font-medium text-gray-700"
              >
                Event Type
              </label>
              <select
                id="event-type"
                value={eventTypeFilter}
                onChange={(e) => handleEventTypeChange(e.target.value)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t === "all" ? "All Types" : t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label
                htmlFor="resource-type"
                className="text-sm font-medium text-gray-700"
              >
                Resource Type
              </label>
              <select
                id="resource-type"
                value={resourceTypeFilter}
                onChange={(e) => handleResourceTypeChange(e.target.value)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              >
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t === "all" ? "All Resources" : t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Audit Table */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            {auditLoading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="animate-pulse rounded bg-gray-200 h-10 w-full"
                  />
                ))}
              </div>
            ) : auditData && auditData.items.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-left text-gray-600">
                        <th className="px-4 py-3 font-medium">Timestamp</th>
                        <th className="px-4 py-3 font-medium">Event Type</th>
                        <th className="px-4 py-3 font-medium">Actor</th>
                        <th className="px-4 py-3 font-medium">Action</th>
                        <th className="px-4 py-3 font-medium">Resource</th>
                        <th className="px-4 py-3 font-medium">Hash</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {auditData.items.map((entry) => (
                        <AuditRow
                          key={entry.id}
                          entry={entry}
                          expanded={expandedRow === entry.id}
                          onToggle={() =>
                            setExpandedRow(
                              expandedRow === entry.id ? null : entry.id
                            )
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className={cn(
                      "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                      page <= 1
                        ? "text-gray-400 cursor-not-allowed"
                        : "text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-600">
                    Page {auditData.page} of {auditData.pages}
                  </span>
                  <button
                    onClick={() =>
                      setPage((p) => Math.min(auditData.pages, p + 1))
                    }
                    disabled={page >= auditData.pages}
                    className={cn(
                      "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                      page >= auditData.pages
                        ? "text-gray-400 cursor-not-allowed"
                        : "text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    Next
                  </button>
                </div>
              </>
            ) : (
              <div className="p-12 text-center text-gray-400">
                No audit entries found.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Integrity Check Tab ── */}
      {activeTab === "integrity" && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-8 shadow-sm flex flex-col items-center gap-6">
            <Shield className="w-16 h-16 text-gray-300" />
            <div className="text-center">
              <h2 className="text-lg font-semibold text-gray-900">
                Chain Integrity Verification
              </h2>
              <p className="text-sm text-gray-500 mt-1 max-w-md">
                Verify the hash chain of all audit entries to ensure no records
                have been tampered with.
              </p>
            </div>
            <button
              onClick={runIntegrityCheck}
              disabled={integrityLoading}
              className={cn(
                "inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium transition-colors",
                integrityLoading
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              )}
            >
              {integrityLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Shield className="w-4 h-4" />
              )}
              {integrityLoading
                ? "Verifying..."
                : "Verify Chain Integrity"}
            </button>

            {lastCheckTime && (
              <p className="text-xs text-gray-400">
                Last checked:{" "}
                {lastCheckTime.toLocaleString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </p>
            )}
          </div>

          {/* Integrity Result */}
          {integrityResult && (
            <div
              className={cn(
                "bg-white rounded-lg border shadow-sm p-8 flex flex-col items-center gap-4",
                integrityResult.valid
                  ? "border-green-300"
                  : "border-red-300"
              )}
            >
              {integrityResult.valid ? (
                <>
                  <CheckCircle className="w-20 h-20 text-green-500" />
                  <h3 className="text-xl font-bold text-green-700">
                    Chain integrity verified.
                  </h3>
                  <p className="text-sm text-gray-600">
                    {integrityResult.entries_checked} entries checked. All hashes
                    are consistent.
                  </p>
                </>
              ) : (
                <>
                  <XCircle className="w-20 h-20 text-red-500" />
                  <h3 className="text-xl font-bold text-red-700">
                    Chain integrity broken
                  </h3>
                  <p className="text-sm text-gray-600">
                    {integrityResult.first_invalid
                      ? `Chain broken at entry: ${integrityResult.first_invalid}`
                      : "Unable to verify chain integrity."}
                  </p>
                  {integrityResult.entries_checked > 0 && (
                    <p className="text-xs text-gray-400">
                      {integrityResult.entries_checked} entries were checked
                      before the break was found.
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Audit Row Component ──

function AuditRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: AuditEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="hover:bg-gray-50 cursor-pointer transition-colors"
      >
        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
          {formatDateTime(entry.created_at)}
        </td>
        <td className="px-4 py-3">
          <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
            {entry.event_type.replace(/_/g, " ")}
          </span>
        </td>
        <td className="px-4 py-3 text-gray-700">{entry.actor}</td>
        <td className="px-4 py-3 text-gray-700">{entry.action}</td>
        <td className="px-4 py-3 text-gray-600">
          {entry.resource_type && (
            <span className="text-xs">
              {entry.resource_type}
              {entry.resource_id ? ` #${entry.resource_id}` : ""}
            </span>
          )}
          {!entry.resource_type && (
            <span className="text-gray-400">--</span>
          )}
        </td>
        <td className="px-4 py-3">
          <code className="font-mono text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
            {entry.current_hash.slice(0, 12)}
          </code>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={6} className="px-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Details
                </h4>
                <pre className="text-xs bg-gray-100 rounded p-3 overflow-x-auto max-h-48 text-gray-700 font-mono">
                  {JSON.stringify(entry.details, null, 2)}
                </pre>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Hash Information
                </h4>
                <div className="space-y-2">
                  <div>
                    <span className="text-xs text-gray-500">Event ID: </span>
                    <code className="font-mono text-xs text-gray-700">
                      {entry.event_id}
                    </code>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Full Hash: </span>
                    <code className="font-mono text-xs text-gray-700 break-all">
                      {entry.current_hash}
                    </code>
                  </div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
