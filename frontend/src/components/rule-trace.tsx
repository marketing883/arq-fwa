"use client";

import { useEffect, useState, useMemo } from "react";
import { claims, type RuleTrace, type RuleTraceStep } from "@/lib/api";
import { cn, riskColor } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
} from "lucide-react";

// ── Constants ──

const SEVERITY_COLORS = [
  "bg-green-400",
  "bg-amber-400",
  "bg-orange-500",
  "bg-red-600",
];

const CATEGORY_COLORS: Record<string, string> = {
  billing: "bg-blue-500/20 text-blue-400",
  clinical: "bg-purple-500/20 text-purple-400",
  pharmacy: "bg-teal-500/20 text-teal-400",
  provider: "bg-indigo-500/20 text-indigo-400",
  temporal: "bg-cyan-500/20 text-cyan-400",
  utilization: "bg-pink-500/20 text-pink-400",
};

const FRAUD_TYPE_COLORS: Record<string, string> = {
  upcoding: "bg-red-500/20 text-red-400",
  unbundling: "bg-orange-500/20 text-orange-400",
  phantom_billing: "bg-rose-500/20 text-rose-400",
  duplicate: "bg-yellow-500/20 text-yellow-400",
  doctor_shopping: "bg-amber-500/20 text-amber-400",
  pill_mill: "bg-fuchsia-500/20 text-fuchsia-400",
  kickback: "bg-violet-500/20 text-violet-400",
};

// ── Props ──

interface RuleTraceProps {
  claimId: string;
}

// ── Skeleton ──

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded bg-surface-3", className)} />
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="glass-card rounded-lg border border-white/[0.06] p-6 space-y-4">
        <SkeletonBar className="h-7 w-64" />
        <div className="flex gap-4">
          <SkeletonBar className="h-5 w-40" />
          <SkeletonBar className="h-5 w-32" />
        </div>
        <SkeletonBar className="h-4 w-80" />
      </div>
      {/* Step skeletons */}
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <div className="flex flex-col items-center">
            <SkeletonBar className="h-8 w-8 rounded-full" />
            {i < 4 && <SkeletonBar className="h-16 w-0.5 mt-1" />}
          </div>
          <div className="flex-1 glass-card rounded-lg border border-white/[0.06] p-4 space-y-3">
            <SkeletonBar className="h-5 w-48" />
            <div className="flex gap-2">
              <SkeletonBar className="h-5 w-20" />
              <SkeletonBar className="h-5 w-24" />
            </div>
            <SkeletonBar className="h-4 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Error State ──

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="glass-card rounded-lg border border-red-500/30 p-8 text-center">
      <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-t-primary mb-2">
        Failed to Load Rule Trace
      </h3>
      <p className="text-sm text-t-secondary mb-4">{message}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-md text-sm font-medium bg-arq-blue-500 text-white hover:bg-arq-blue-600 transition-colors"
      >
        Retry
      </button>
    </div>
  );
}

// ── Evidence Panel ──

function EvidencePanel({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence);
  if (entries.length === 0) {
    return (
      <p className="text-xs text-t-muted italic">No evidence data available</p>
    );
  }
  return (
    <pre className="text-xs bg-surface-0 text-gray-100 rounded-md p-3 overflow-x-auto max-h-64 overflow-y-auto">
      {JSON.stringify(evidence, null, 2)}
    </pre>
  );
}

// ── Triggered Step Card ──

function TriggeredStepCard({ step }: { step: RuleTraceStep }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const severity = step.severity ?? 0;
  const severityPct = Math.min((severity / 3) * 100, 100);
  const severityColor =
    SEVERITY_COLORS[Math.min(severity, SEVERITY_COLORS.length - 1)];

  const confidencePct =
    step.confidence != null ? (step.confidence * 100).toFixed(0) : null;

  const categoryClass =
    CATEGORY_COLORS[step.category] ?? "bg-surface-2 text-t-secondary";
  const fraudTypeClass =
    FRAUD_TYPE_COLORS[step.fraud_type] ?? "bg-surface-2 text-t-secondary";

  return (
    <div className="flex-1 glass-card rounded-lg border border-red-500/30 p-4">
      {/* Step header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-t-primary">
              {step.rule_name}
            </span>
          </div>
          <span className="text-xs font-mono text-t-muted">
            {step.rule_id}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block px-2 py-0.5 rounded text-xs font-medium capitalize",
              categoryClass
            )}
          >
            {step.category}
          </span>
          <span
            className={cn(
              "inline-block px-2 py-0.5 rounded text-xs font-medium capitalize",
              fraudTypeClass
            )}
          >
            {step.fraud_type.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-4 mb-3">
        {/* Severity */}
        <div>
          <p className="text-xs text-t-muted mb-1">
            Severity ({severity}/3)
          </p>
          <div className="w-full h-2 bg-surface-3 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", severityColor)}
              style={{ width: `${severityPct}%` }}
            />
          </div>
        </div>

        {/* Confidence */}
        <div>
          <p className="text-xs text-t-muted mb-1">Confidence</p>
          <p className="text-sm font-semibold text-t-primary">
            {confidencePct != null ? `${confidencePct}%` : "\u2014"}
          </p>
        </div>

        {/* Contribution */}
        <div>
          <p className="text-xs text-t-muted mb-1">Contribution</p>
          <p className="text-sm font-semibold text-t-primary">
            {step.contribution != null
              ? `+${step.contribution.toFixed(2)}`
              : "\u2014"}
          </p>
        </div>
      </div>

      {/* Weight */}
      {step.weight != null && (
        <p className="text-xs text-t-muted mb-2">
          Weight: {step.weight.toFixed(2)}
        </p>
      )}

      {/* Explanation */}
      <div className="flex items-start gap-2 bg-red-500/10 rounded-md p-3 mb-3">
        <Info className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
        <p className="text-sm text-red-300">{step.explanation}</p>
      </div>

      {/* Evidence toggle */}
      <button
        onClick={() => setEvidenceOpen(!evidenceOpen)}
        className="flex items-center gap-1.5 text-xs font-medium text-t-secondary hover:text-t-primary transition-colors"
      >
        {evidenceOpen ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
        Evidence
      </button>
      {evidenceOpen && (
        <div className="mt-2">
          <EvidencePanel evidence={step.evidence} />
        </div>
      )}
    </div>
  );
}

// ── Passed Step Row ──

function PassedStepRow({ step }: { step: RuleTraceStep }) {
  const categoryClass =
    CATEGORY_COLORS[step.category] ?? "bg-surface-2 text-t-secondary";

  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-md hover:bg-surface-2 transition-colors">
      <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
      <span className="text-sm font-mono text-t-muted w-20 shrink-0">
        {step.rule_id}
      </span>
      <span className="text-sm text-t-secondary flex-1">{step.rule_name}</span>
      <span
        className={cn(
          "inline-block px-2 py-0.5 rounded text-xs font-medium capitalize",
          categoryClass
        )}
      >
        {step.category}
      </span>
    </div>
  );
}

// ── Main Component ──

export function RuleTraceView({ claimId }: RuleTraceProps) {
  const [trace, setTrace] = useState<RuleTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPassed, setShowPassed] = useState(false);

  const loadTrace = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await claims.ruleTrace(claimId);
      setTrace(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await claims.ruleTrace(claimId);
        if (!cancelled) setTrace(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "An unexpected error occurred"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  const triggeredSteps = useMemo(
    () => (trace?.steps ?? []).filter((s) => s.triggered),
    [trace]
  );

  const passedSteps = useMemo(
    () => (trace?.steps ?? []).filter((s) => !s.triggered),
    [trace]
  );

  // ── Loading ──
  if (loading) return <LoadingSkeleton />;

  // ── Error ──
  if (error) return <ErrorState message={error} onRetry={loadTrace} />;

  // ── No data ──
  if (!trace) {
    return (
      <div className="glass-card rounded-lg border border-white/[0.06] p-8 text-center">
        <Info className="w-10 h-10 text-t-muted mx-auto mb-3" />
        <p className="text-sm text-t-muted">No rule trace data available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="glass-card rounded-lg border border-white/[0.06] p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-t-primary">
              Rule Evaluation Trace
            </h2>
            <p className="text-sm text-t-muted mt-1">
              Claim{" "}
              <span className="font-mono text-t-secondary">{trace.claim_id}</span>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs text-t-muted uppercase tracking-wider">
                Total Score
              </p>
              <p className="text-2xl font-bold text-t-primary">
                {trace.total_score.toFixed(1)}
              </p>
            </div>
            <span
              className={cn(
                "inline-block px-3 py-1.5 rounded-md text-sm font-semibold capitalize",
                riskColor(trace.risk_level)
              )}
            >
              {trace.risk_level}
            </span>
          </div>
        </div>

        {/* Score calculation summary */}
        <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-t-muted uppercase tracking-wider">
              Formula
            </span>
            <code className="text-xs bg-surface-2 text-t-secondary px-2 py-1 rounded font-mono">
              {trace.score_calculation.formula}
            </code>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-t-secondary">
              <span className="font-semibold text-red-400">
                {trace.score_calculation.rules_triggered}
              </span>{" "}
              triggered
            </span>
            <span className="text-white/10">|</span>
            <span className="text-t-secondary">
              <span className="font-semibold text-green-400">
                {trace.score_calculation.rules_passed}
              </span>{" "}
              passed
            </span>
          </div>
        </div>
      </div>

      {/* ── Triggered Steps Timeline ── */}
      {triggeredSteps.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wider mb-4">
            Triggered Rules ({triggeredSteps.length})
          </h3>
          <div className="space-y-0">
            {triggeredSteps.map((step, idx) => (
              <div key={step.rule_id} className="flex gap-4">
                {/* Timeline connector */}
                <div className="flex flex-col items-center">
                  {/* Step indicator */}
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-red-500/20 border-2 border-red-400 shrink-0">
                    <XCircle className="w-4 h-4 text-red-400" />
                  </div>
                  {/* Vertical line */}
                  {idx < triggeredSteps.length - 1 && (
                    <div className="w-0.5 flex-1 bg-red-500/30 min-h-[16px]" />
                  )}
                </div>

                {/* Step card */}
                <div className="flex-1 pb-6">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-t-muted">
                      Step {step.step}
                    </span>
                  </div>
                  <TriggeredStepCard step={step} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Passed Rules Section ── */}
      {passedSteps.length > 0 && (
        <div className="glass-card rounded-lg border border-white/[0.06]">
          <button
            onClick={() => setShowPassed(!showPassed)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-2 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span className="text-sm font-medium text-t-secondary">
                Show passed rules ({passedSteps.length})
              </span>
            </div>
            {showPassed ? (
              <ChevronDown className="w-4 h-4 text-t-muted" />
            ) : (
              <ChevronRight className="w-4 h-4 text-t-muted" />
            )}
          </button>
          {showPassed && (
            <div className="px-4 pb-3 border-t border-white/[0.06]">
              <div className="divide-y divide-white/[0.04]">
                {passedSteps.map((step) => (
                  <PassedStepRow key={step.rule_id} step={step} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
