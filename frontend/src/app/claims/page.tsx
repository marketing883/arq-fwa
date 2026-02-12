"use client";
import { useEffect, useState, useMemo, useCallback } from "react";
import {
  dashboard,
  claims,
  type DashboardOverview,
  type ClaimSummary,
  type PaginatedClaims,
  type ClaimDetail,
} from "@/lib/api";
import {
  cn,
  riskColor,
  formatCurrency,
  formatNumber,
  formatDate,
} from "@/lib/utils";
import { X } from "lucide-react";
import { useWorkspace } from "@/lib/workspace-context";
import { ConfidenceBadge } from "@/components/confidence-indicator";

type ClaimTypeFilter = "" | "medical" | "pharmacy";
type RiskLevelFilter = "" | "low" | "medium" | "high" | "critical";
type SortDir = "asc" | "desc";

const CLAIM_TYPES: { label: string; value: ClaimTypeFilter }[] = [
  { label: "All", value: "" },
  { label: "Medical", value: "medical" },
  { label: "Pharmacy", value: "pharmacy" },
];

const RISK_LEVELS: { label: string; value: RiskLevelFilter }[] = [
  { label: "All", value: "" },
  { label: "Low", value: "low" },
  { label: "Medium", value: "medium" },
  { label: "High", value: "high" },
  { label: "Critical", value: "critical" },
];

const PAGE_SIZES = [25, 50, 100];

const SEVERITY_COLORS = [
  "bg-green-400",
  "bg-amber-400",
  "bg-orange-500",
  "bg-red-600",
];

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded bg-gray-200", className)}
    />
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
        active
          ? "bg-blue-600 text-white"
          : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
      )}
    >
      {children}
    </button>
  );
}

export default function ClaimsPage() {
  const { activeWorkspace } = useWorkspace();
  // Filter state
  const [typeFilter, setTypeFilter] = useState<ClaimTypeFilter>("");
  const [riskFilter, setRiskFilter] = useState<RiskLevelFilter>("");
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);

  // Data state
  const [data, setData] = useState<PaginatedClaims | null>(null);
  const [loading, setLoading] = useState(true);

  // Sort state (client-side on amount_billed)
  const [sortDir, setSortDir] = useState<SortDir | null>(null);

  // Detail slide-out state
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [claimDetail, setClaimDetail] = useState<ClaimDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch claims list
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const result = await claims.list({
          type: typeFilter || undefined,
          risk_level: riskFilter || undefined,
          page,
          size: pageSize,
          workspace_id: activeWorkspace,
        });
        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        console.error("Failed to load claims:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [typeFilter, riskFilter, page, pageSize, activeWorkspace]);

  // Fetch claim detail when selected
  useEffect(() => {
    if (!selectedClaimId) {
      setClaimDetail(null);
      return;
    }
    let cancelled = false;
    async function loadDetail() {
      setDetailLoading(true);
      try {
        const detail = await claims.detail(selectedClaimId!);
        if (!cancelled) setClaimDetail(detail);
      } catch (err) {
        console.error("Failed to load claim detail:", err);
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedClaimId]);

  // Client-side sort on amount_billed
  const sortedItems = useMemo(() => {
    if (!data?.items) return [];
    if (!sortDir) return data.items;
    return [...data.items].sort((a, b) =>
      sortDir === "asc"
        ? a.amount_billed - b.amount_billed
        : b.amount_billed - a.amount_billed
    );
  }, [data?.items, sortDir]);

  const toggleSort = useCallback(() => {
    setSortDir((prev) => {
      if (prev === null) return "desc";
      if (prev === "desc") return "asc";
      return null;
    });
  }, []);

  // Reset to page 1 when filters change
  const handleTypeFilter = (v: ClaimTypeFilter) => {
    setTypeFilter(v);
    setPage(1);
  };
  const handleRiskFilter = (v: RiskLevelFilter) => {
    setRiskFilter(v);
    setPage(1);
  };
  const handlePageSize = (size: number) => {
    setPageSize(size);
    setPage(1);
  };

  const totalPages = data?.pages ?? 1;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Claims Explorer</h1>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-6">
          {/* Type Filter */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">
              Type
            </p>
            <div className="flex gap-1">
              {CLAIM_TYPES.map((ct) => (
                <FilterButton
                  key={ct.value}
                  active={typeFilter === ct.value}
                  onClick={() => handleTypeFilter(ct.value)}
                >
                  {ct.label}
                </FilterButton>
              ))}
            </div>
          </div>

          {/* Risk Level Filter */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">
              Risk Level
            </p>
            <div className="flex gap-1">
              {RISK_LEVELS.map((rl) => (
                <FilterButton
                  key={rl.value}
                  active={riskFilter === rl.value}
                  onClick={() => handleRiskFilter(rl.value)}
                >
                  {rl.label}
                </FilterButton>
              ))}
            </div>
          </div>

          {/* Page Size */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">
              Page Size
            </p>
            <div className="flex gap-1">
              {PAGE_SIZES.map((size) => (
                <FilterButton
                  key={size}
                  active={pageSize === size}
                  onClick={() => handlePageSize(size)}
                >
                  {size}
                </FilterButton>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Claims Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonBar key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : data && sortedItems.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600 border-b border-gray-200">
                    <th className="px-4 py-3 font-medium">Claim ID</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Member ID</th>
                    <th className="px-4 py-3 font-medium">Service Date</th>
                    <th
                      className="px-4 py-3 font-medium text-right cursor-pointer select-none hover:text-blue-600"
                      onClick={toggleSort}
                    >
                      Amount Billed
                      {sortDir === "asc" && " \u2191"}
                      {sortDir === "desc" && " \u2193"}
                      {sortDir === null && " \u2195"}
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Risk Score
                    </th>
                    <th className="px-4 py-3 font-medium">Risk Level</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sortedItems.map((claim) => (
                    <tr
                      key={claim.id}
                      className={cn(
                        "hover:bg-gray-50 transition-colors cursor-pointer",
                        selectedClaimId === claim.claim_id && "bg-blue-50"
                      )}
                      onClick={() => setSelectedClaimId(claim.claim_id)}
                    >
                      <td className="px-4 py-3 font-mono text-xs text-blue-600">
                        {claim.claim_id}
                      </td>
                      <td className="px-4 py-3 text-gray-700 capitalize">
                        {claim.claim_type}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {claim.member_id}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {formatDate(claim.service_date || claim.fill_date)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-900 font-medium">
                        {formatCurrency(claim.amount_billed)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {claim.risk_score != null
                          ? claim.risk_score.toFixed(1)
                          : "\u2014"}
                      </td>
                      <td className="px-4 py-3">
                        {claim.risk_level ? (
                          <span
                            className={cn(
                              "inline-block px-2 py-0.5 rounded text-xs font-semibold capitalize",
                              riskColor(claim.risk_level)
                            )}
                          >
                            {claim.risk_level}
                          </span>
                        ) : (
                          <span className="text-gray-400">\u2014</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 capitalize">
                          {claim.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
              <p className="text-sm text-gray-600">
                {formatNumber(data.total)} total claims
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className={cn(
                    "px-3 py-1.5 rounded text-sm font-medium transition-colors",
                    page <= 1
                      ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                      : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                  )}
                >
                  Previous
                </button>
                <span className="text-sm text-gray-700">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() =>
                    setPage((p) => Math.min(totalPages, p + 1))
                  }
                  disabled={page >= totalPages}
                  className={cn(
                    "px-3 py-1.5 rounded text-sm font-medium transition-colors",
                    page >= totalPages
                      ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                      : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                  )}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="p-12 text-center text-gray-400">
            No claims found matching the current filters.
          </div>
        )}
      </div>

      {/* Claim Detail Slide-out */}
      {selectedClaimId && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20 z-40"
            onClick={() => setSelectedClaimId(null)}
          />

          {/* Panel */}
          <div className="fixed top-0 right-0 h-full w-96 bg-white shadow-xl z-50 overflow-y-auto border-l border-gray-200">
            {/* Header */}
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
              <h2 className="text-lg font-semibold text-gray-900">
                Claim Detail
              </h2>
              <button
                onClick={() => setSelectedClaimId(null)}
                className="p-1 rounded hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {detailLoading ? (
              <div className="p-6 space-y-4">
                <SkeletonBar className="h-6 w-48" />
                <SkeletonBar className="h-4 w-full" />
                <SkeletonBar className="h-4 w-full" />
                <SkeletonBar className="h-4 w-3/4" />
                <SkeletonBar className="h-20 w-full mt-6" />
                <SkeletonBar className="h-20 w-full" />
              </div>
            ) : claimDetail ? (
              <div className="p-6 space-y-6">
                {/* Claim Summary */}
                <section>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Summary
                  </h3>
                  <dl className="space-y-2">
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Claim ID</dt>
                      <dd className="text-sm font-mono text-gray-900">
                        {claimDetail.claim_id}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Type</dt>
                      <dd className="text-sm text-gray-900 capitalize">
                        {claimDetail.claim_type}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Member ID</dt>
                      <dd className="text-sm text-gray-900">
                        {claimDetail.member_member_id ?? claimDetail.member_id}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Status</dt>
                      <dd className="text-sm text-gray-900 capitalize">
                        {claimDetail.status}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Service Date</dt>
                      <dd className="text-sm text-gray-900">
                        {formatDate(
                          claimDetail.service_date || claimDetail.fill_date
                        )}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Amount Billed</dt>
                      <dd className="text-sm font-medium text-gray-900">
                        {formatCurrency(claimDetail.amount_billed)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Amount Allowed</dt>
                      <dd className="text-sm text-gray-900">
                        {formatCurrency(claimDetail.amount_allowed)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500">Amount Paid</dt>
                      <dd className="text-sm text-gray-900">
                        {formatCurrency(claimDetail.amount_paid)}
                      </dd>
                    </div>
                    {claimDetail.provider_name && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">Provider</dt>
                        <dd className="text-sm text-gray-900">
                          {claimDetail.provider_name}
                        </dd>
                      </div>
                    )}
                    {claimDetail.provider_npi && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">Provider NPI</dt>
                        <dd className="text-sm font-mono text-gray-900">
                          {claimDetail.provider_npi}
                        </dd>
                      </div>
                    )}
                    {claimDetail.cpt_code && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">CPT Code</dt>
                        <dd className="text-sm font-mono text-gray-900">
                          {claimDetail.cpt_code}
                        </dd>
                      </div>
                    )}
                    {claimDetail.diagnosis_code_primary && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">Dx Code</dt>
                        <dd className="text-sm font-mono text-gray-900">
                          {claimDetail.diagnosis_code_primary}
                        </dd>
                      </div>
                    )}
                    {claimDetail.drug_name && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">Drug</dt>
                        <dd className="text-sm text-gray-900">
                          {claimDetail.drug_name}
                        </dd>
                      </div>
                    )}
                    {claimDetail.ndc_code && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">NDC Code</dt>
                        <dd className="text-sm font-mono text-gray-900">
                          {claimDetail.ndc_code}
                        </dd>
                      </div>
                    )}
                    {claimDetail.days_supply != null && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-gray-500">Days Supply</dt>
                        <dd className="text-sm text-gray-900">
                          {claimDetail.days_supply}
                        </dd>
                      </div>
                    )}
                  </dl>
                </section>

                {/* Risk Score */}
                {claimDetail.risk_score && (
                  <section>
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                      Risk Score
                    </h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">
                          Total Score
                        </span>
                        <span className="text-xl font-bold text-gray-900">
                          {claimDetail.risk_score.total_score.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">
                          Risk Level
                        </span>
                        <span
                          className={cn(
                            "inline-block px-2.5 py-1 rounded text-xs font-semibold capitalize",
                            riskColor(claimDetail.risk_score.risk_level)
                          )}
                        >
                          {claimDetail.risk_score.risk_level}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">
                          Rules Triggered
                        </span>
                        <span className="text-sm font-medium text-gray-900">
                          {claimDetail.risk_score.rules_triggered}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">
                          Confidence
                        </span>
                        <span className="text-sm font-medium text-gray-900">
                          {(
                            claimDetail.risk_score.confidence_factor * 100
                          ).toFixed(0)}
                          %
                        </span>
                      </div>
                    </div>
                  </section>
                )}

                {/* Rule Results */}
                {claimDetail.rule_results &&
                  claimDetail.rule_results.length > 0 && (
                    <section>
                      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                        Rule Results
                      </h3>
                      <div className="space-y-3">
                        {claimDetail.rule_results
                          .filter((r) => r.triggered)
                          .map((rule) => {
                            const severity = rule.severity ?? 0;
                            const severityPct = Math.min(
                              (severity / 3) * 100,
                              100
                            );
                            const colorClass =
                              SEVERITY_COLORS[
                                Math.min(severity, SEVERITY_COLORS.length - 1)
                              ];
                            return (
                              <div
                                key={rule.rule_id}
                                className="bg-gray-50 rounded-lg p-3"
                              >
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="text-sm font-medium text-gray-900 font-mono">
                                    {rule.rule_id}
                                  </span>
                                  <span className="text-xs text-gray-500">
                                    Severity: {severity}/3
                                  </span>
                                </div>
                                {/* Severity bar */}
                                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div
                                    className={cn(
                                      "h-full rounded-full transition-all",
                                      colorClass
                                    )}
                                    style={{ width: `${severityPct}%` }}
                                  />
                                </div>
                                {rule.details && (
                                  <p className="text-xs text-gray-600 mt-1.5">
                                    {rule.details}
                                  </p>
                                )}
                                {rule.confidence != null && (
                                  <div className="mt-1">
                                    <ConfidenceBadge confidence={rule.confidence} />
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        {claimDetail.rule_results.filter((r) => r.triggered)
                          .length === 0 && (
                          <p className="text-sm text-gray-400">
                            No rules triggered
                          </p>
                        )}
                      </div>
                    </section>
                  )}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-400">
                Failed to load claim details.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
