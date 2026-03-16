import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/* ── Risk ── */

export function riskColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "bg-red-500/20 text-red-400 border border-red-500/30";
    case "high":     return "bg-orange-500/20 text-orange-400 border border-orange-500/30";
    case "medium":   return "bg-amber-500/20 text-amber-400 border border-amber-500/30";
    case "low":      return "bg-green-500/20 text-green-400 border border-green-500/30";
    default:         return "bg-surface-3 text-t-muted";
  }
}

export function riskBorderColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "border-red-500/40";
    case "high":     return "border-orange-500/40";
    case "medium":   return "border-amber-500/40";
    case "low":      return "border-green-500/40";
    default:         return "border-white/[0.06]";
  }
}

/* ── Priority ── */

export function priorityColor(priority: string | null | undefined): string {
  switch (priority) {
    case "P1": return "bg-red-500/20 text-red-400 border border-red-500/30";
    case "P2": return "bg-orange-500/20 text-orange-400 border border-orange-500/30";
    case "P3": return "bg-amber-500/20 text-amber-300 border border-amber-500/30";
    case "P4": return "bg-blue-500/20 text-blue-400 border border-blue-500/30";
    default:   return "bg-surface-3 text-t-muted";
  }
}

/* ── Status ── */

export function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "open":         return "bg-blue-500/20 text-blue-400 border border-blue-500/30";
    case "under_review": return "bg-amber-500/20 text-amber-400 border border-amber-500/30";
    case "resolved":     return "bg-green-500/20 text-green-400 border border-green-500/30";
    case "closed":       return "bg-surface-3 text-t-muted border border-white/[0.06]";
    default:             return "bg-surface-3 text-t-muted";
  }
}

/* ── Recharts dark theme ── */

export const CHART_COLORS = {
  blue: "#4F7AEF",
  lime: "#A3E635",
  indigo: "#818CF8",
  pink: "#F472B6",
  cyan: "#22D3EE",
  amber: "#FBBF24",
};

export const RISK_CHART_COLORS = ["#22c55e", "#f59e0b", "#ef4444", "#991b1b"];

export const DARK_TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: "#111827",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 8,
    color: "#F1F5F9",
    fontSize: 12,
  },
  labelStyle: { color: "#94A3B8" },
};

export const DARK_GRID = { stroke: "#1A2235", strokeDasharray: "3 3" };

export const DARK_AXIS = {
  stroke: "#243044",
  tick: { fill: "#94A3B8", fontSize: 11 },
};

/* ── Formatting ── */

export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return "\u2014";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
