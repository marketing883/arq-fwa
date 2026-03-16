"use client";

import { useEffect, useState } from "react";
import { providers, type PeerComparison, type PeerMetric } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { AlertTriangle, TrendingUp, Users } from "lucide-react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PeerComparisonProps {
  npi: string;
  workspaceId?: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function percentileBadgeClass(percentile: number): string {
  if (percentile > 90) return "bg-red-500/20 text-red-400 border border-red-500/30";
  if (percentile >= 75) return "bg-amber-500/20 text-amber-400 border border-amber-500/30";
  return "bg-green-500/20 text-green-400 border border-green-500/30";
}

function formatValue(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(1);
}

// ---------------------------------------------------------------------------
// Skeleton loader
// ---------------------------------------------------------------------------

function MetricCardSkeleton() {
  return (
    <div className="animate-pulse rounded-lg border border-white/[0.06] glass-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="h-5 w-40 rounded bg-surface-3" />
        <div className="h-5 w-20 rounded bg-surface-3" />
      </div>
      <div className="h-48 w-full rounded bg-surface-2" />
    </div>
  );
}

function HeaderSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-6 w-64 rounded bg-surface-3" />
      <div className="flex gap-3">
        <div className="h-4 w-32 rounded bg-surface-3" />
        <div className="h-4 w-48 rounded bg-surface-3" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom tooltip for the bar chart
// ---------------------------------------------------------------------------

interface ChartPayloadEntry {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string;
}

function MetricTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: ChartPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      className="rounded-lg px-3 py-2 text-sm"
      style={{
        backgroundColor: "#111827",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 8,
        color: "#F1F5F9",
      }}
    >
      <p className="mb-1 font-medium text-t-primary">{label}</p>
      {payload.map((entry, idx) => (
        <p key={idx} style={{ color: entry.color }} className="text-xs">
          {entry.name}: {formatValue(entry.value ?? 0)}
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric card component
// ---------------------------------------------------------------------------

function MetricCard({ metric }: { metric: PeerMetric }) {
  const chartData = [
    {
      name: "Provider",
      value: metric.provider_value,
    },
  ];

  // Determine max domain for the chart
  const maxValue = Math.max(
    metric.provider_value,
    metric.peer_average,
    metric.peer_p75,
    metric.peer_p90
  ) * 1.15;

  return (
    <div
      className={cn(
        "rounded-lg border glass-card p-5 transition-shadow",
        metric.anomaly ? "border-red-500/30" : "border-white/[0.06]"
      )}
    >
      {/* Card header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-t-muted" />
          <h3 className="text-sm font-semibold text-t-primary">{metric.metric}</h3>
        </div>

        <div className="flex items-center gap-2">
          {metric.anomaly && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-2.5 py-0.5 text-xs font-medium text-red-400 border border-red-500/30">
              <AlertTriangle className="h-3 w-3" />
              Above P90
            </span>
          )}
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
              percentileBadgeClass(metric.percentile)
            )}
          >
            P{Math.round(metric.percentile)}
          </span>
        </div>
      </div>

      {/* Value summary row */}
      <div className="mb-3 grid grid-cols-4 gap-2 text-center text-xs">
        <div>
          <p className="text-t-muted">Provider</p>
          <p className="font-semibold text-arq-blue-400">{formatValue(metric.provider_value)}</p>
        </div>
        <div>
          <p className="text-t-muted">Peer Avg</p>
          <p className="font-semibold text-t-secondary">{formatValue(metric.peer_average)}</p>
        </div>
        <div>
          <p className="text-t-muted">P75</p>
          <p className="font-semibold text-amber-400">{formatValue(metric.peer_p75)}</p>
        </div>
        <div>
          <p className="text-t-muted">P90</p>
          <p className="font-semibold text-red-400">{formatValue(metric.peer_p90)}</p>
        </div>
      </div>

      {/* Horizontal bar chart */}
      <div className="h-24">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
          >
            <CartesianGrid stroke="#1A2235" strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, maxValue]}
              tickFormatter={formatValue}
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              stroke="#243044"
            />
            <YAxis
              type="category"
              dataKey="name"
              width={60}
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              stroke="#243044"
            />
            <Tooltip content={<MetricTooltip />} />

            {/* Peer average – solid gray reference line */}
            <ReferenceLine
              x={metric.peer_average}
              stroke="#6b7280"
              strokeWidth={2}
              label={{ value: "Avg", position: "top", fontSize: 10, fill: "#6b7280" }}
            />

            {/* P75 – dashed amber reference line */}
            <ReferenceLine
              x={metric.peer_p75}
              stroke="#d97706"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              label={{ value: "P75", position: "top", fontSize: 10, fill: "#d97706" }}
            />

            {/* P90 – solid red reference line */}
            <ReferenceLine
              x={metric.peer_p90}
              stroke="#dc2626"
              strokeWidth={2}
              label={{ value: "P90", position: "top", fontSize: 10, fill: "#dc2626" }}
            />

            <Bar dataKey="value" name="Provider" barSize={28} radius={[0, 4, 4, 0]}>
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={metric.anomaly ? "#ef4444" : "#3b82f6"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel component
// ---------------------------------------------------------------------------

export function PeerComparisonPanel({ npi, workspaceId }: PeerComparisonProps) {
  const [data, setData] = useState<PeerComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await providers.peerComparison(npi, workspaceId);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load peer comparison data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [npi, workspaceId]);

  // ── Loading state ──
  if (loading) {
    return (
      <div className="space-y-6">
        <HeaderSkeleton />
        <div className="grid gap-4 md:grid-cols-2">
          <MetricCardSkeleton />
          <MetricCardSkeleton />
          <MetricCardSkeleton />
          <MetricCardSkeleton />
        </div>
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 px-6 py-12 text-center">
        <AlertTriangle className="mb-3 h-8 w-8 text-red-400" />
        <h3 className="text-sm font-semibold text-red-400">Error Loading Peer Comparison</h3>
        <p className="mt-1 text-xs text-red-400/80">{error}</p>
      </div>
    );
  }

  // ── Empty state ──
  if (!data || data.metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-white/[0.06] bg-surface-2 px-6 py-12 text-center">
        <Users className="mb-3 h-8 w-8 text-t-muted" />
        <h3 className="text-sm font-semibold text-t-secondary">No Peer Comparison Data</h3>
        <p className="mt-1 text-xs text-t-muted">
          No peer comparison metrics are available for this provider.
        </p>
      </div>
    );
  }

  const anomalyCount = data.metrics.filter((m) => m.anomaly).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-t-primary">{data.provider.name}</h2>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-t-muted">
            <span>NPI: {data.provider.npi}</span>
            <span className="hidden sm:inline">|</span>
            <span>{data.provider.specialty}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-arq-blue-500/20 px-3 py-1 text-xs font-medium text-arq-blue-400 border border-arq-blue-500/30">
            <Users className="h-3.5 w-3.5" />
            {data.peer_group}
          </span>

          {anomalyCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-3 py-1 text-xs font-medium text-red-400 border border-red-500/30">
              <AlertTriangle className="h-3.5 w-3.5" />
              {anomalyCount} anomal{anomalyCount === 1 ? "y" : "ies"}
            </span>
          )}
        </div>
      </div>

      {/* Metric cards grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {data.metrics.map((metric) => (
          <MetricCard key={metric.metric} metric={metric} />
        ))}
      </div>
    </div>
  );
}
