"use client";
import { useEffect, useState } from "react";
import {
  dashboard,
  governance,
  type DashboardOverview,
  type GovernanceHealth,
} from "@/lib/api";
import type {
  TopProviderItem,
  RuleEffectivenessItem,
} from "@/lib/api";
import {
  cn,
  riskColor,
  formatCurrency,
  formatNumber,
} from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  FileText,
  AlertTriangle,
  DollarSign,
  Briefcase,
  Shield,
  Activity,
  Eye,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import Link from "next/link";
import { useWorkspace } from "@/lib/workspace-context";

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-md bg-gray-100", className)} />
  );
}

function StatCardSkeleton() {
  return (
    <div className="stat-card">
      <SkeletonBar className="h-3 w-24 mb-3" />
      <SkeletonBar className="h-7 w-32" />
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaUp?: boolean;
  accentColor: string;
}

function StatCard({ label, value, delta, deltaUp, accentColor }: StatCardProps) {
  return (
    <div className="stat-card group">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {delta && (
        <div className="flex items-center justify-between mt-3.5 pt-3.5 border-t border-border-subtle">
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[11.5px] font-medium",
              deltaUp ? "text-risk-low-text" : "text-risk-critical-text"
            )}
          >
            {deltaUp ? (
              <TrendingUp size={12} />
            ) : (
              <TrendingDown size={12} />
            )}
            {delta}
          </span>
          <span className="text-[10.5px] text-text-quaternary">vs last 30d</span>
        </div>
      )}
      <div
        className="absolute bottom-0 left-0 right-0 h-[3px] rounded-b-lg"
        style={{
          background: `linear-gradient(90deg, ${accentColor}, transparent)`,
        }}
      />
    </div>
  );
}

export default function DashboardPage() {
  const { activeWorkspace } = useWorkspace();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [providers, setProviders] = useState<TopProviderItem[] | null>(null);
  const [ruleEffectiveness, setRuleEffectiveness] = useState<
    RuleEffectivenessItem[] | null
  >(null);
  const [govHealth, setGovHealth] = useState<GovernanceHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let retryCount = 0;
    const MAX_RETRIES = 3;

    async function load() {
      setLoading(true);
      while (retryCount <= MAX_RETRIES && !cancelled) {
        try {
          const [overviewData, providerData, ruleData] = await Promise.all([
            dashboard.overview(activeWorkspace),
            dashboard.topProviders(10, activeWorkspace),
            dashboard.ruleEffectiveness(activeWorkspace),
          ]);
          if (!cancelled) {
            setOverview(overviewData);
            setProviders(providerData.providers);
            setRuleEffectiveness(ruleData.rules);
          }
          break;
        } catch (err) {
          retryCount++;
          if (retryCount <= MAX_RETRIES && !cancelled) {
            await new Promise((r) => setTimeout(r, retryCount * 2000));
          }
        }
      }
      if (!cancelled) setLoading(false);
    }
    load();
    governance
      .health()
      .then((h) => {
        if (!cancelled) setGovHealth(h);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace]);

  const riskDistData = overview
    ? [
        { name: "Low", value: overview.risk_distribution.low, color: "#1CA855", pct: 0 },
        { name: "Medium", value: overview.risk_distribution.medium, color: "#E5A800", pct: 0 },
        { name: "High", value: overview.risk_distribution.high, color: "#ED6C02", pct: 0 },
        { name: "Critical", value: overview.risk_distribution.critical, color: "#E5243B", pct: 0 },
      ].map((d) => ({
        ...d,
        pct: overview.total_claims > 0 ? ((d.value / overview.total_claims) * 100) : 0,
      }))
    : [];

  const topRules = ruleEffectiveness
    ? [...ruleEffectiveness]
        .sort((a, b) => b.times_triggered - a.times_triggered)
        .slice(0, 8)
    : [];

  const maxTriggered = topRules.length > 0 ? topRules[0].times_triggered : 1;

  return (
    <div className="space-y-5 max-w-[1440px]">
      {/* Page Header */}
      <div>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle mt-0.5">Executive Overview</p>
      </div>

      {/* Stat Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
      ) : overview ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <StatCard
            label="Claims Processed"
            value={formatNumber(overview.total_claims)}
            delta="12.3%"
            deltaUp
            accentColor="#0055F2"
          />
          <StatCard
            label="Claims Flagged"
            value={formatNumber(overview.total_flagged)}
            delta="8.1%"
            deltaUp
            accentColor="#ED6C02"
          />
          <StatCard
            label="Fraud Identified"
            value={formatCurrency(overview.total_fraud_amount)}
            delta="23.4%"
            deltaUp
            accentColor="#C8E616"
          />
          <StatCard
            label="Active Cases"
            value={formatNumber(overview.active_cases)}
            delta="5.2%"
            deltaUp={false}
            accentColor="#7C5CFC"
          />
        </div>
      ) : (
        <p className="text-risk-critical text-sm">Failed to load overview data.</p>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
        {/* Risk Distribution */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Risk Distribution</div>
              <div className="card-subtitle">
                {overview ? `Across ${formatNumber(overview.total_claims)} scored claims` : "Loading\u2026"}
              </div>
            </div>
            <Link href="/claims" className="link">
              View all &rarr;
            </Link>
          </div>
          <div className="card-body">
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4].map((i) => (
                  <SkeletonBar key={i} className="h-5 w-full" />
                ))}
              </div>
            ) : riskDistData.length > 0 ? (
              <div className="space-y-4">
                {riskDistData.map((d) => (
                  <div key={d.name} className="flex items-center gap-3">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: d.color }}
                    />
                    <span className="text-[12.5px] font-medium text-text-secondary w-14">
                      {d.name}
                    </span>
                    <div className="flex-1 h-1.5 rounded-full bg-surface-page overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-1000"
                        style={{
                          width: `${d.pct}%`,
                          backgroundColor: d.color,
                          opacity: 0.75,
                        }}
                      />
                    </div>
                    <span className="text-[12.5px] font-semibold text-text-primary w-12 text-right tabular-nums">
                      {formatNumber(d.value)}
                    </span>
                    <span className="text-[11px] text-text-quaternary w-10 text-right">
                      {d.pct.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-text-quaternary text-center py-12 text-sm">
                No risk distribution data
              </p>
            )}
          </div>
        </div>

        {/* Rule Effectiveness */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Top Rules by Triggers</div>
              <div className="card-subtitle">Last 30 days</div>
            </div>
            <Link href="/rules" className="link">
              All rules &rarr;
            </Link>
          </div>
          <div className="card-body">
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <SkeletonBar key={i} className="h-4 w-full" />
                ))}
              </div>
            ) : topRules.length > 0 ? (
              <div className="space-y-2.5">
                {topRules.map((rule) => (
                  <div key={rule.rule_id} className="flex items-center gap-2.5">
                    <span className="text-[11px] font-medium text-text-tertiary w-7 font-mono tracking-tight">
                      {rule.rule_id.replace("RULE-MED-0", "M").replace("RULE-RX-0", "P").replace("RULE-MED-", "M").replace("RULE-RX-", "P")}
                    </span>
                    <div className="flex-1 h-[5px] rounded-full bg-surface-page overflow-hidden">
                      <div
                        className="h-full rounded-full bg-brand-blue/80 transition-all duration-700"
                        style={{
                          width: `${(rule.times_triggered / maxTriggered) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-[11.5px] font-semibold text-text-primary w-8 text-right tabular-nums">
                      {rule.times_triggered}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-text-quaternary text-center py-12 text-sm">
                No rule data
              </p>
            )}
          </div>
        </div>
      </div>

      {/* AI Governance Health */}
      {govHealth && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
          {/* ArqFlow */}
          <div className="card relative overflow-hidden">
            <div className="absolute top-0 left-0 w-[3px] h-full bg-brand-blue" />
            <div className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-text-primary">ArqFlow</span>
                <span className="text-[9.5px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-brand-blue/10 text-brand-blue">
                  TAO
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-0.5">Trust-Aware Orchestration</p>
              <div className="mt-4">
                <span className="text-[28px] font-bold text-text-primary tracking-tight leading-none">
                  {govHealth.tao.avg_trust_score != null
                    ? `${(govHealth.tao.avg_trust_score * 100).toFixed(0)}%`
                    : "N/A"}
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-1">Avg Trust Score</p>
              <div className="flex items-center gap-1.5 mt-4 pt-3.5 border-t border-border-subtle">
                <span className="w-[5px] h-[5px] rounded-full bg-brand-lime" />
                <span className={cn("text-[11px] font-medium", govHealth.tao.hitl_pending > 0 ? "text-risk-medium-text" : "text-risk-low-text")}>
                  {govHealth.tao.hitl_pending} HITL Pending
                </span>
              </div>
            </div>
          </div>

          {/* ArqGuard */}
          <div className="card relative overflow-hidden">
            <div className="absolute top-0 left-0 w-[3px] h-full bg-brand-lime" />
            <div className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-text-primary">ArqGuard</span>
                <span className="text-[9.5px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-brand-lime/15 text-[#5A7A00]">
                  CAPC
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-0.5">Compliance Engine</p>
              <div className="mt-4">
                <span className="text-[28px] font-bold text-text-primary tracking-tight leading-none">
                  {govHealth.capc.evidence_packets > 0
                    ? `${(((govHealth.capc.evidence_packets - govHealth.capc.policy_violations) / govHealth.capc.evidence_packets) * 100).toFixed(1)}%`
                    : "N/A"}
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-1">Compliance Rate</p>
              <div className="flex items-center gap-1.5 mt-4 pt-3.5 border-t border-border-subtle">
                <span className="w-[5px] h-[5px] rounded-full bg-brand-lime" />
                <span className={cn("text-[11px] font-medium", govHealth.capc.policy_violations > 0 ? "text-risk-critical-text" : "text-risk-low-text")}>
                  {govHealth.capc.policy_violations} Violations
                </span>
              </div>
            </div>
          </div>

          {/* ArqSight */}
          <div className="card relative overflow-hidden">
            <div className="absolute top-0 left-0 w-[3px] h-full bg-risk-medium" />
            <div className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-text-primary">ArqSight</span>
                <span className="text-[9.5px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-risk-medium/10 text-risk-medium-text">
                  RAG
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-0.5">Adaptive Retrieval</p>
              <div className="mt-4">
                <span className="text-[28px] font-bold text-text-primary tracking-tight leading-none">
                  {govHealth.oda_rag.signals_24h}
                </span>
              </div>
              <p className="text-[11px] text-text-tertiary mt-1">Signals (24h)</p>
              <div className="flex items-center gap-1.5 mt-4 pt-3.5 border-t border-border-subtle">
                <span className="w-[5px] h-[5px] rounded-full bg-brand-lime animate-glow" />
                <span className={cn("text-[11px] font-medium", govHealth.oda_rag.signals_24h > 0 ? "text-risk-low-text" : "text-text-quaternary")}>
                  {govHealth.oda_rag.signals_24h > 0 ? "Active" : "Idle"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top Flagged Providers */}
      <div className="card">
        <div className="card-header border-b border-border">
          <div>
            <div className="card-title">Top Flagged Providers</div>
            <div className="card-subtitle">Ranked by average risk score</div>
          </div>
          <Link href="/cases" className="link">
            View all &rarr;
          </Link>
        </div>
        {loading ? (
          <div className="p-5 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <SkeletonBar key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : providers && providers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="table-header">
                  <th style={{ width: 48 }}>#</th>
                  <th>NPI</th>
                  <th>Provider</th>
                  <th>Specialty</th>
                  <th className="text-right">Risk</th>
                  <th className="text-right">Flagged</th>
                  <th className="text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p, idx) => (
                  <tr key={p.provider_id} className="table-row">
                    <td>
                      <span className="text-[12px] font-semibold text-text-quaternary tabular-nums">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                    </td>
                    <td className="font-mono text-[11.5px] text-text-tertiary tracking-tight">
                      {p.npi}
                    </td>
                    <td className="text-text-primary font-medium">{p.name}</td>
                    <td className="text-[12px] text-text-tertiary">
                      {p.specialty || "\u2014"}
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          "badge",
                          p.risk_score >= 85
                            ? "badge-critical"
                            : p.risk_score >= 60
                            ? "badge-high"
                            : p.risk_score >= 30
                            ? "badge-medium"
                            : "badge-low"
                        )}
                      >
                        {p.risk_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="text-right tabular-nums">
                      {formatNumber(p.flagged_claims)}
                    </td>
                    <td className="text-right text-text-primary font-medium tabular-nums tracking-tight">
                      {formatCurrency(p.total_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-text-quaternary text-sm">
            No provider data available
          </div>
        )}
      </div>
    </div>
  );
}
