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
  if (confidence >= 0.8) return "#1CA855"; // risk-low
  if (confidence >= 0.6) return "#E5A800"; // risk-medium
  if (confidence >= 0.4) return "#ED6C02"; // risk-high
  return "#E5243B"; // risk-critical
}

function getLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.6) return "Moderate";
  if (confidence >= 0.4) return "Low";
  return "Very Low";
}

function getBgClass(confidence: number): string {
  if (confidence >= 0.8) return "bg-risk-low-bg border-risk-low";
  if (confidence >= 0.6) return "bg-risk-medium-bg border-risk-medium";
  if (confidence >= 0.4) return "bg-risk-high-bg border-risk-high";
  return "bg-risk-critical-bg border-risk-critical";
}

function getTextClass(confidence: number): string {
  if (confidence >= 0.8) return "text-risk-low-text";
  if (confidence >= 0.6) return "text-risk-medium-text";
  if (confidence >= 0.4) return "text-risk-high-text";
  return "text-risk-critical-text";
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
          stroke="rgba(0,0,0,0.06)"
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
        className="text-center font-medium text-text-tertiary"
        style={{ fontSize: labelSize }}
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
