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
  if (percentile > 90) return "bg-risk-critical-bg text-risk-critical-text border border-risk-critical";
  if (percentile >= 75) return "bg-risk-medium-bg text-risk-medium-text border border-risk-medium";
  return "bg-risk-low-bg text-risk-low-text border border-risk-low";
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
    <div className="animate-pulse card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="h-5 w-40 rounded bg-border" />
        <div className="h-5 w-20 rounded bg-border" />
      </div>
      <div className="h-48 w-full rounded bg-surface-page" />
    </div>
  );
}

function HeaderSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-6 w-64 rounded bg-border" />
      <div className="flex gap-3">
        <div className="h-4 w-32 rounded bg-border" />
        <div className="h-4 w-48 rounded bg-border" />
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
    <div className="rounded-md border border-border bg-surface-card px-3 py-2 text-sm shadow-lg">
      <p className="mb-1 font-medium text-text-primary">{label}</p>
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
        "card p-5 transition-shadow hover:shadow-md",
        metric.anomaly ? "border-risk-critical" : ""
      )}
    >
      {/* Card header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-text-tertiary" />
          <h3 className="text-sm font-semibold text-text-primary">{metric.metric}</h3>
        </div>

        <div className="flex items-center gap-2">
          {metric.anomaly && (
            <span className="badge inline-flex items-center gap-1 bg-risk-critical-bg text-risk-critical-text border border-risk-critical">
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
          <p className="text-text-tertiary">Provider</p>
          <p className="font-semibold text-brand-blue">{formatValue(metric.provider_value)}</p>
        </div>
        <div>
          <p className="text-text-tertiary">Peer Avg</p>
          <p className="font-semibold text-text-secondary">{formatValue(metric.peer_average)}</p>
        </div>
        <div>
          <p className="text-text-tertiary">P75</p>
          <p className="font-semibold text-amber-600">{formatValue(metric.peer_p75)}</p>
        </div>
        <div>
          <p className="text-text-tertiary">P90</p>
          <p className="font-semibold text-risk-critical">{formatValue(metric.peer_p90)}</p>
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
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={[0, maxValue]} tickFormatter={formatValue} fontSize={11} />
            <YAxis type="category" dataKey="name" width={60} fontSize={11} />
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
      <div className="flex flex-col items-center justify-center rounded-lg border border-risk-critical bg-risk-critical-bg px-6 py-12 text-center">
        <AlertTriangle className="mb-3 h-8 w-8 text-risk-critical" />
        <h3 className="text-sm font-semibold text-risk-critical-text">Error Loading Peer Comparison</h3>
        <p className="mt-1 text-xs text-risk-critical">{error}</p>
      </div>
    );
  }

  // ── Empty state ──
  if (!data || data.metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-surface-page px-6 py-12 text-center">
        <Users className="mb-3 h-8 w-8 text-text-quaternary" />
        <h3 className="text-sm font-semibold text-text-secondary">No Peer Comparison Data</h3>
        <p className="mt-1 text-xs text-text-tertiary">
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
          <h2 className="text-[15px] font-semibold text-text-primary tracking-tight">{data.provider.name}</h2>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-tertiary">
            <span>NPI: {data.provider.npi}</span>
            <span className="hidden sm:inline">|</span>
            <span>{data.provider.specialty}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="badge inline-flex items-center gap-1.5 bg-brand-blue/10 text-brand-blue border border-brand-blue/20">
            <Users className="h-3.5 w-3.5" />
            {data.peer_group}
          </span>

          {anomalyCount > 0 && (
            <span className="badge inline-flex items-center gap-1 bg-risk-critical-bg text-risk-critical-text border border-risk-critical">
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
