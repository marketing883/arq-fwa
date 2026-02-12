import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function riskColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "bg-red-900 text-white";
    case "high": return "bg-red-500 text-white";
    case "medium": return "bg-amber-500 text-white";
    case "low": return "bg-green-500 text-white";
    default: return "bg-gray-300 text-gray-800";
  }
}

export function riskBorderColor(level: string | null | undefined): string {
  switch (level) {
    case "critical": return "border-red-900";
    case "high": return "border-red-500";
    case "medium": return "border-amber-500";
    case "low": return "border-green-500";
    default: return "border-gray-300";
  }
}

export function priorityColor(priority: string | null | undefined): string {
  switch (priority) {
    case "P1": return "bg-red-600 text-white";
    case "P2": return "bg-orange-500 text-white";
    case "P3": return "bg-yellow-500 text-black";
    case "P4": return "bg-blue-500 text-white";
    default: return "bg-gray-300 text-gray-800";
  }
}

export function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "open": return "bg-blue-100 text-blue-800";
    case "under_review": return "bg-yellow-100 text-yellow-800";
    case "resolved": return "bg-green-100 text-green-800";
    case "closed": return "bg-gray-100 text-gray-800";
    default: return "bg-gray-100 text-gray-800";
  }
}

export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(d: string | null | undefined): string {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
