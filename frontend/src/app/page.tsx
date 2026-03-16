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
  formatCurrency,
  formatNumber,
  RISK_CHART_COLORS,
  DARK_TOOLTIP_STYLE,
  DARK_GRID,
  DARK_AXIS,
  CHART_COLORS,
} from "@/lib/utils";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  FileText,
  AlertTriangle,
  DollarSign,
  Briefcase,
  Shield,
  Activity,
  Eye,
} from "lucide-react";
import Link from "next/link";
import { useWorkspace } from "@/lib/workspace-context";

function SkeletonBar({ className }: { className?: string }) {
  return <div className={cn("skeleton-dark", className)} />;
}

function StatCardSkeleton() {
  return (
    <div className="glass-card p-6">
      <SkeletonBar className="h-4 w-24 mb-3" />
      <SkeletonBar className="h-8 w-32" />
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconBg: string;
}

function StatCard({ label, value, icon, iconBg }: StatCardProps) {
  return (
    <div className="glass-card p-6 flex items-start gap-4 hover:border-white/[0.1] transition-colors">
      <div
        className={cn(
          "flex items-center justify-center w-12 h-12 rounded-lg shrink-0",
          iconBg
        )}
      >
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-t-muted">{label}</p>
        <p className="text-2xl font-bold mt-1 text-t-primary tabular-nums">{value}</p>
      </div>
    </div>
  );
}

const RADIAN = Math.PI / 180;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderCustomLabel(props: any) {
  const { cx, cy, midAngle, innerRadius, outerRadius, value, name } = props;
  const radius = innerRadius + (outerRadius - innerRadius) * 1.4;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text
      x={x}
      y={y}
      fill="#94A3B8"
      textAnchor={x > cx ? "start" : "end"}
      dominantBaseline="central"
      fontSize={12}
    >
      {name}: {value}
    </text>
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
            console.warn(`Dashboard load attempt ${retryCount} failed, retrying in ${retryCount * 2}s...`);
            await new Promise((r) => setTimeout(r, retryCount * 2000));
          } else {
            console.error("Failed to load dashboard data:", err);
          }
        }
      }
      if (!cancelled) setLoading(false);
    }
    load();
    governance.health().then((h) => { if (!cancelled) setGovHealth(h); }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeWorkspace]);

  const riskDistData = overview
    ? [
        { name: "Low", value: overview.risk_distribution.low },
        { name: "Medium", value: overview.risk_distribution.medium },
        { name: "High", value: overview.risk_distribution.high },
        { name: "Critical", value: overview.risk_distribution.critical },
      ]
    : [];

  const topRules = ruleEffectiveness
    ? [...ruleEffectiveness]
        .sort((a, b) => b.times_triggered - a.times_triggered)
        .slice(0, 10)
    : [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-t-primary">
          Executive Overview
        </h1>
        <p className="text-sm text-t-muted mt-1">
          FWA Detection &amp; Prevention Dashboard
        </p>
      </div>

      {/* Stat Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
      ) : overview ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Claims Processed"
            value={formatNumber(overview.total_claims)}
            icon={<FileText className="w-6 h-6 text-arq-blue-400" />}
            iconBg="bg-arq-blue-500/20"
          />
          <StatCard
            label="Claims Flagged"
            value={formatNumber(overview.total_flagged)}
            icon={<AlertTriangle className="w-6 h-6 text-red-400" />}
            iconBg="bg-red-500/20"
          />
          <StatCard
            label="Total Fraud Identified"
            value={formatCurrency(overview.total_fraud_amount)}
            icon={<DollarSign className="w-6 h-6 text-arq-lime-400" />}
            iconBg="bg-arq-lime-400/20"
          />
          <StatCard
            label="Active Cases"
            value={formatNumber(overview.active_cases)}
            icon={<Briefcase className="w-6 h-6 text-purple-400" />}
            iconBg="bg-purple-500/20"
          />
        </div>
      ) : (
        <p className="text-red-400">Failed to load overview data.</p>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Risk Distribution Donut */}
        <div className="lg:col-span-2 glass-card p-6">
          <h2 className="text-lg font-semibold text-t-primary mb-4">
            Risk Distribution
          </h2>
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <SkeletonBar className="h-48 w-48 rounded-full" />
            </div>
          ) : riskDistData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={riskDistData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  label={renderCustomLabel}
                >
                  {riskDistData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={RISK_CHART_COLORS[index]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => formatNumber(value as number)}
                  {...DARK_TOOLTIP_STYLE}
                />
                <Legend
                  wrapperStyle={{ color: "#94A3B8", fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-t-muted text-center py-12">
              No risk distribution data available
            </p>
          )}
        </div>

        {/* Rule Effectiveness Bar Chart */}
        <div className="lg:col-span-2 glass-card p-6">
          <h2 className="text-lg font-semibold text-t-primary mb-4">
            Rule Effectiveness
          </h2>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonBar key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : topRules.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={topRules}
                layout="vertical"
                margin={{ top: 0, right: 20, left: 80, bottom: 0 }}
              >
                <CartesianGrid {...DARK_GRID} />
                <XAxis type="number" {...DARK_AXIS} />
                <YAxis
                  type="category"
                  dataKey="rule_id"
                  width={75}
                  {...DARK_AXIS}
                />
                <Tooltip
                  formatter={(value) => [
                    formatNumber(value as number),
                    "Times Triggered",
                  ]}
                  {...DARK_TOOLTIP_STYLE}
                />
                <Bar
                  dataKey="times_triggered"
                  fill={CHART_COLORS.blue}
                  radius={[0, 4, 4, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-t-muted text-center py-12">
              No rule effectiveness data available
            </p>
          )}
        </div>
      </div>

      {/* AI Governance Health Strip */}
      {govHealth && (
        <div className="glass-card">
          <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Eye className="w-5 h-5 text-arq-blue-400" />
              <h2 className="text-sm font-semibold text-t-primary">
                AI Governance Health
              </h2>
            </div>
            <Link
              href="/governance"
              className="text-xs text-arq-blue-400 hover:text-arq-blue-500 font-medium"
            >
              View Details &rarr;
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-white/[0.06]">
            {/* ArqFlow */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-arq-blue-400" />
                <span className="text-xs font-semibold text-t-secondary">ArqFlow</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-t-muted">Trust Profiles</span>
                  <p className="font-semibold text-t-primary">{govHealth.tao.trust_profiles}</p>
                </div>
                <div>
                  <span className="text-t-muted">Avg Trust</span>
                  <p className="font-semibold text-t-primary">
                    {govHealth.tao.avg_trust_score != null
                      ? `${(govHealth.tao.avg_trust_score * 100).toFixed(0)}%`
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <span className="text-t-muted">HITL Pending</span>
                  <p className={cn("font-semibold", govHealth.tao.hitl_pending > 0 ? "text-amber-400" : "text-green-400")}>
                    {govHealth.tao.hitl_pending}
                  </p>
                </div>
                <div>
                  <span className="text-t-muted">Receipts</span>
                  <p className="font-semibold text-t-primary">{govHealth.tao.audit_receipts}</p>
                </div>
              </div>
            </div>
            {/* ArqGuard */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-green-400" />
                <span className="text-xs font-semibold text-t-secondary">ArqGuard</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-t-muted">Evidence Packets</span>
                  <p className="font-semibold text-t-primary">{govHealth.capc.evidence_packets}</p>
                </div>
                <div>
                  <span className="text-t-muted">Violations</span>
                  <p className={cn("font-semibold", govHealth.capc.policy_violations > 0 ? "text-red-400" : "text-green-400")}>
                    {govHealth.capc.policy_violations}
                  </p>
                </div>
                <div className="col-span-2">
                  <span className="text-t-muted">Compliance</span>
                  <p className="font-semibold text-t-primary">
                    {govHealth.capc.evidence_packets > 0
                      ? `${(((govHealth.capc.evidence_packets - govHealth.capc.policy_violations) / govHealth.capc.evidence_packets) * 100).toFixed(1)}%`
                      : "N/A"}
                  </p>
                </div>
              </div>
            </div>
            {/* ArqSight */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-orange-400" />
                <span className="text-xs font-semibold text-t-secondary">ArqSight</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-t-muted">Signals (24h)</span>
                  <p className="font-semibold text-t-primary">{govHealth.oda_rag.signals_24h}</p>
                </div>
                <div>
                  <span className="text-t-muted">Adaptations</span>
                  <p className="font-semibold text-t-primary">{govHealth.oda_rag.adaptations}</p>
                </div>
                <div>
                  <span className="text-t-muted">Feedback Avg</span>
                  <p className="font-semibold text-t-primary">
                    {govHealth.oda_rag.avg_feedback_quality != null
                      ? `${(govHealth.oda_rag.avg_feedback_quality * 100).toFixed(0)}%`
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <span className="text-t-muted">Status</span>
                  <p className={cn("font-semibold", govHealth.oda_rag.signals_24h > 0 ? "text-green-400" : "text-t-muted")}>
                    {govHealth.oda_rag.signals_24h > 0 ? "Active" : "Idle"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top Flagged Providers Table */}
      <div className="glass-card">
        <div className="p-6 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-t-primary">
            Top Flagged Providers
          </h2>
        </div>
        {loading ? (
          <div className="p-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonBar key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : providers && providers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm dark-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>NPI</th>
                  <th>Name</th>
                  <th>Specialty</th>
                  <th className="text-right">Avg Risk Score</th>
                  <th className="text-right">Flagged Claims</th>
                  <th className="text-right">Total Amount</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p, idx) => (
                  <tr key={p.provider_id}>
                    <td className="font-medium text-t-primary">
                      {idx + 1}
                    </td>
                    <td className="font-mono text-xs">
                      {p.npi}
                    </td>
                    <td className="text-t-primary font-medium">
                      {p.name}
                    </td>
                    <td>
                      {p.specialty || "\u2014"}
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          "inline-block px-2 py-0.5 rounded text-xs font-semibold",
                          p.risk_score >= 75
                            ? "bg-red-500/20 text-red-400"
                            : p.risk_score >= 50
                            ? "bg-amber-500/20 text-amber-400"
                            : "bg-green-500/20 text-green-400"
                        )}
                      >
                        {p.risk_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="text-right">
                      {formatNumber(p.flagged_claims)}
                    </td>
                    <td className="text-right">
                      {formatCurrency(p.total_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-t-muted">
            No provider data available
          </div>
        )}
      </div>

      {/* Recent Cases Link */}
      <div className="glass-card p-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-t-primary">
            Recent Cases
          </h2>
          <p className="text-sm text-t-muted mt-1">
            View and manage active fraud investigation cases
          </p>
        </div>
        <Link
          href="/cases"
          className="inline-flex items-center gap-2 px-4 py-2 bg-arq-blue-500 text-white rounded-lg text-sm font-medium hover:bg-arq-blue-600 transition-colors shadow-glow"
        >
          View All Cases
          <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </div>
  );
}
