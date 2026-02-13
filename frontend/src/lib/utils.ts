import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function riskColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "bg-risk-critical-bg text-risk-critical-text";
    case "high": return "bg-risk-high-bg text-risk-high-text";
    case "medium": return "bg-risk-medium-bg text-risk-medium-text";
    case "low": return "bg-risk-low-bg text-risk-low-text";
    default: return "bg-gray-100 text-text-tertiary";
  }
}

export function riskBorderColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "border-risk-critical";
    case "high": return "border-risk-high";
    case "medium": return "border-risk-medium";
    case "low": return "border-risk-low";
    default: return "border-border";
  }
}

export function riskDotColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "bg-risk-critical";
    case "high": return "bg-risk-high";
    case "medium": return "bg-risk-medium";
    case "low": return "bg-risk-low";
    default: return "bg-text-quaternary";
  }
}

export function priorityColor(priority: string | null | undefined): string {
  switch (priority) {
    case "P1": return "bg-risk-critical-bg text-risk-critical-text";
    case "P2": return "bg-risk-high-bg text-risk-high-text";
    case "P3": return "bg-risk-medium-bg text-risk-medium-text";
    case "P4": return "bg-brand-blue/10 text-brand-blue";
    default: return "bg-gray-100 text-text-tertiary";
  }
}

export function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "open": return "bg-brand-blue/10 text-brand-blue";
    case "under_review": return "bg-risk-medium-bg text-risk-medium-text";
    case "resolved": return "bg-risk-low-bg text-risk-low-text";
    case "closed": return "bg-gray-100 text-text-tertiary";
    default: return "bg-gray-100 text-text-tertiary";
  }
}

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
