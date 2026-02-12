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
  if (percentile > 90) return "bg-red-100 text-red-800 border border-red-300";
  if (percentile >= 75) return "bg-amber-100 text-amber-800 border border-amber-300";
  return "bg-green-100 text-green-800 border border-green-300";
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
    <div className="animate-pulse rounded-lg border border-gray-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="h-5 w-40 rounded bg-gray-200" />
        <div className="h-5 w-20 rounded bg-gray-200" />
      </div>
      <div className="h-48 w-full rounded bg-gray-100" />
    </div>
  );
}

function HeaderSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-6 w-64 rounded bg-gray-200" />
      <div className="flex gap-3">
        <div className="h-4 w-32 rounded bg-gray-200" />
        <div className="h-4 w-48 rounded bg-gray-200" />
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
    <div className="rounded-md border border-gray-200 bg-white px-3 py-2 text-sm shadow-lg">
      <p className="mb-1 font-medium text-gray-900">{label}</p>
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
        "rounded-lg border bg-white p-5 shadow-sm transition-shadow hover:shadow-md",
        metric.anomaly ? "border-red-300" : "border-gray-200"
      )}
    >
      {/* Card header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-900">{metric.metric}</h3>
        </div>

        <div className="flex items-center gap-2">
          {metric.anomaly && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 border border-red-300">
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
          <p className="text-gray-500">Provider</p>
          <p className="font-semibold text-blue-600">{formatValue(metric.provider_value)}</p>
        </div>
        <div>
          <p className="text-gray-500">Peer Avg</p>
          <p className="font-semibold text-gray-600">{formatValue(metric.peer_average)}</p>
        </div>
        <div>
          <p className="text-gray-500">P75</p>
          <p className="font-semibold text-amber-600">{formatValue(metric.peer_p75)}</p>
        </div>
        <div>
          <p className="text-gray-500">P90</p>
          <p className="font-semibold text-red-600">{formatValue(metric.peer_p90)}</p>
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
      <div className="flex flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50 px-6 py-12 text-center">
        <AlertTriangle className="mb-3 h-8 w-8 text-red-500" />
        <h3 className="text-sm font-semibold text-red-800">Error Loading Peer Comparison</h3>
        <p className="mt-1 text-xs text-red-600">{error}</p>
      </div>
    );
  }

  // ── Empty state ──
  if (!data || data.metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-gray-50 px-6 py-12 text-center">
        <Users className="mb-3 h-8 w-8 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">No Peer Comparison Data</h3>
        <p className="mt-1 text-xs text-gray-500">
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
          <h2 className="text-lg font-bold text-gray-900">{data.provider.name}</h2>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            <span>NPI: {data.provider.npi}</span>
            <span className="hidden sm:inline">|</span>
            <span>{data.provider.specialty}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800 border border-blue-200">
            <Users className="h-3.5 w-3.5" />
            {data.peer_group}
          </span>

          {anomalyCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800 border border-red-300">
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
