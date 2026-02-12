"use client";

import { cn } from "@/lib/utils";

interface ConfidenceIndicatorProps {
  /** Confidence value from 0 to 1 */
  confidence: number;
  /** Optional label (defaults to "Confidence") */
  label?: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

const SIZE_MAP = {
  sm: { outer: 48, stroke: 4, fontSize: 10, labelSize: 8 },
  md: { outer: 72, stroke: 5, fontSize: 16, labelSize: 10 },
  lg: { outer: 96, stroke: 6, fontSize: 20, labelSize: 12 },
};

function getColor(confidence: number): string {
  if (confidence >= 0.8) return "#22c55e"; // green-500
  if (confidence >= 0.6) return "#f59e0b"; // amber-500
  if (confidence >= 0.4) return "#f97316"; // orange-500
  return "#ef4444"; // red-500
}

function getLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.6) return "Moderate";
  if (confidence >= 0.4) return "Low";
  return "Very Low";
}

function getBgClass(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-50 border-green-200";
  if (confidence >= 0.6) return "bg-amber-50 border-amber-200";
  if (confidence >= 0.4) return "bg-orange-50 border-orange-200";
  return "bg-red-50 border-red-200";
}

function getTextClass(confidence: number): string {
  if (confidence >= 0.8) return "text-green-700";
  if (confidence >= 0.6) return "text-amber-700";
  if (confidence >= 0.4) return "text-orange-700";
  return "text-red-700";
}

export function ConfidenceIndicator({
  confidence,
  label = "Confidence",
  size = "md",
}: ConfidenceIndicatorProps) {
  const { outer, stroke, fontSize, labelSize } = SIZE_MAP[size];
  const radius = (outer - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(1, confidence));
  const offset = circumference * (1 - pct);
  const color = getColor(pct);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={outer} height={outer} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={outer / 2}
          cy={outer / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={stroke}
        />
        {/* Progress arc */}
        <circle
          cx={outer / 2}
          cy={outer / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
        {/* Center text */}
        <text
          x={outer / 2}
          y={outer / 2}
          textAnchor="middle"
          dominantBaseline="central"
          className="rotate-90 origin-center"
          fill={color}
          fontSize={fontSize}
          fontWeight="bold"
        >
          {Math.round(pct * 100)}%
        </text>
      </svg>
      <span
        className="text-center font-medium"
        style={{ fontSize: labelSize, color: "#6b7280" }}
      >
        {label}
      </span>
    </div>
  );
}

/** Inline confidence badge for tables and compact views */
export function ConfidenceBadge({
  confidence,
}: {
  confidence: number;
}) {
  const pct = Math.max(0, Math.min(1, confidence));
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border",
        getBgClass(pct),
        getTextClass(pct)
      )}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: getColor(pct) }}
      />
      {Math.round(pct * 100)}% {getLabel(pct)}
    </span>
  );
}
