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
  "bg-risk-low",
  "bg-risk-medium",
  "bg-risk-high",
  "bg-risk-critical",
];

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded bg-border", className)}
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
          ? "bg-brand-blue text-white"
          : "bg-surface-card text-text-secondary border border-border hover:bg-surface-page"
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
        <h1 className="text-[15px] font-semibold text-text-primary tracking-tight">Claims Explorer</h1>
      </div>

      {/* Filter Bar */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-6">
          {/* Type Filter */}
          <div>
            <p className="section-label mb-1.5">
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
            <p className="section-label mb-1.5">
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
            <p className="section-label mb-1.5">
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
      <div className="card">
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
                <thead className="table-header">
                  <tr>
                    <th>Claim ID</th>
                    <th>Type</th>
                    <th>Member ID</th>
                    <th>Service Date</th>
                    <th
                      className="text-right cursor-pointer select-none hover:text-brand-blue"
                      onClick={toggleSort}
                    >
                      Amount Billed
                      {sortDir === "asc" && " \u2191"}
                      {sortDir === "desc" && " \u2193"}
                      {sortDir === null && " \u2195"}
                    </th>
                    <th className="text-right">
                      Risk Score
                    </th>
                    <th>Risk Level</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedItems.map((claim) => (
                    <tr
                      key={claim.id}
                      className={cn(
                        "table-row cursor-pointer",
                        selectedClaimId === claim.claim_id && "bg-brand-blue/5"
                      )}
                      onClick={() => setSelectedClaimId(claim.claim_id)}
                    >
                      <td className="font-mono text-xs text-brand-blue">
                        {claim.claim_id}
                      </td>
                      <td className="text-text-secondary capitalize">
                        {claim.claim_type}
                      </td>
                      <td className="text-text-secondary">
                        {claim.member_id}
                      </td>
                      <td className="text-text-tertiary">
                        {formatDate(claim.service_date || claim.fill_date)}
                      </td>
                      <td className="text-right text-text-primary font-medium">
                        {formatCurrency(claim.amount_billed)}
                      </td>
                      <td className="text-right text-text-secondary">
                        {claim.risk_score != null
                          ? claim.risk_score.toFixed(1)
                          : "\u2014"}
                      </td>
                      <td>
                        {claim.risk_level ? (
                          <span
                            className={cn(
                              "badge capitalize",
                              riskColor(claim.risk_level)
                            )}
                          >
                            {claim.risk_level}
                          </span>
                        ) : (
                          <span className="text-text-quaternary">\u2014</span>
                        )}
                      </td>
                      <td>
                        <span className="badge bg-surface-page text-text-secondary capitalize">
                          {claim.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-border">
              <p className="text-sm text-text-tertiary">
                {formatNumber(data.total)} total claims
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                    page <= 1
                      ? "bg-surface-page text-text-quaternary cursor-not-allowed"
                      : "btn-secondary"
                  )}
                >
                  Previous
                </button>
                <span className="text-sm text-text-secondary">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() =>
                    setPage((p) => Math.min(totalPages, p + 1))
                  }
                  disabled={page >= totalPages}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                    page >= totalPages
                      ? "bg-surface-page text-text-quaternary cursor-not-allowed"
                      : "btn-secondary"
                  )}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="p-12 text-center text-text-quaternary">
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
          <div className="fixed top-0 right-0 h-full w-96 bg-surface-card shadow-lg z-50 overflow-y-auto border-l border-border">
            {/* Header */}
            <div className="sticky top-0 bg-surface-card border-b border-border px-6 py-4 flex items-center justify-between z-10">
              <h2 className="text-[15px] font-semibold text-text-primary tracking-tight">
                Claim Detail
              </h2>
              <button
                onClick={() => setSelectedClaimId(null)}
                className="p-1 rounded-md hover:bg-surface-page transition-colors"
              >
                <X className="w-5 h-5 text-text-tertiary" />
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
                  <h3 className="section-label mb-3">
                    Summary
                  </h3>
                  <dl className="space-y-2">
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Claim ID</dt>
                      <dd className="text-sm font-mono text-text-primary">
                        {claimDetail.claim_id}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Type</dt>
                      <dd className="text-sm text-text-primary capitalize">
                        {claimDetail.claim_type}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Member ID</dt>
                      <dd className="text-sm text-text-primary">
                        {claimDetail.member_member_id ?? claimDetail.member_id}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Status</dt>
                      <dd className="text-sm text-text-primary capitalize">
                        {claimDetail.status}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Service Date</dt>
                      <dd className="text-sm text-text-primary">
                        {formatDate(
                          claimDetail.service_date || claimDetail.fill_date
                        )}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Amount Billed</dt>
                      <dd className="text-sm font-medium text-text-primary">
                        {formatCurrency(claimDetail.amount_billed)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Amount Allowed</dt>
                      <dd className="text-sm text-text-primary">
                        {formatCurrency(claimDetail.amount_allowed)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-text-tertiary">Amount Paid</dt>
                      <dd className="text-sm text-text-primary">
                        {formatCurrency(claimDetail.amount_paid)}
                      </dd>
                    </div>
                    {claimDetail.provider_name && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">Provider</dt>
                        <dd className="text-sm text-text-primary">
                          {claimDetail.provider_name}
                        </dd>
                      </div>
                    )}
                    {claimDetail.provider_npi && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">Provider NPI</dt>
                        <dd className="text-sm font-mono text-text-primary">
                          {claimDetail.provider_npi}
                        </dd>
                      </div>
                    )}
                    {claimDetail.cpt_code && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">CPT Code</dt>
                        <dd className="text-sm font-mono text-text-primary">
                          {claimDetail.cpt_code}
                        </dd>
                      </div>
                    )}
                    {claimDetail.diagnosis_code_primary && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">Dx Code</dt>
                        <dd className="text-sm font-mono text-text-primary">
                          {claimDetail.diagnosis_code_primary}
                        </dd>
                      </div>
                    )}
                    {claimDetail.drug_name && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">Drug</dt>
                        <dd className="text-sm text-text-primary">
                          {claimDetail.drug_name}
                        </dd>
                      </div>
                    )}
                    {claimDetail.ndc_code && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">NDC Code</dt>
                        <dd className="text-sm font-mono text-text-primary">
                          {claimDetail.ndc_code}
                        </dd>
                      </div>
                    )}
                    {claimDetail.days_supply != null && (
                      <div className="flex justify-between">
                        <dt className="text-sm text-text-tertiary">Days Supply</dt>
                        <dd className="text-sm text-text-primary">
                          {claimDetail.days_supply}
                        </dd>
                      </div>
                    )}
                  </dl>
                </section>

                {/* Risk Score */}
                {claimDetail.risk_score && (
                  <section>
                    <h3 className="section-label mb-3">
                      Risk Score
                    </h3>
                    <div className="bg-surface-page rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-text-tertiary">
                          Total Score
                        </span>
                        <span className="text-xl font-bold text-text-primary">
                          {claimDetail.risk_score.total_score.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-text-tertiary">
                          Risk Level
                        </span>
                        <span
                          className={cn(
                            "badge capitalize",
                            riskColor(claimDetail.risk_score.risk_level)
                          )}
                        >
                          {claimDetail.risk_score.risk_level}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-text-tertiary">
                          Rules Triggered
                        </span>
                        <span className="text-sm font-medium text-text-primary">
                          {claimDetail.risk_score.rules_triggered}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-text-tertiary">
                          Confidence
                        </span>
                        <span className="text-sm font-medium text-text-primary">
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
                      <h3 className="section-label mb-3">
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
                                className="bg-surface-page rounded-lg p-3"
                              >
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="text-sm font-medium text-text-primary font-mono">
                                    {rule.rule_id}
                                  </span>
                                  <span className="text-xs text-text-tertiary">
                                    Severity: {severity}/3
                                  </span>
                                </div>
                                {/* Severity bar */}
                                <div className="w-full h-2 bg-border rounded-full overflow-hidden">
                                  <div
                                    className={cn(
                                      "h-full rounded-full transition-all",
                                      colorClass
                                    )}
                                    style={{ width: `${severityPct}%` }}
                                  />
                                </div>
                                {rule.details && (
                                  <p className="text-xs text-text-tertiary mt-1.5">
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
                          <p className="text-sm text-text-quaternary">
                            No rules triggered
                          </p>
                        )}
                      </div>
                    </section>
                  )}
              </div>
            ) : (
              <div className="p-6 text-center text-text-quaternary">
                Failed to load claim details.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
