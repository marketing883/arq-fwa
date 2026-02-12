"use client";

import { useState, useCallback, useRef } from "react";
import {
  Play,
  Loader2,
  CheckCircle,
  Database,
  Cog,
  BarChart3,
  Shield,
  FileSearch,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PipelineMonitorProps {
  workspaceId?: string | null;
  onComplete?: () => void;
}

interface PhaseState {
  key: string;
  label: string;
  icon: React.ElementType;
  progress: number;
  detail: string;
  current: number;
  total: number;
  status: "pending" | "active" | "complete";
}

interface CompleteSummary {
  batch_id: string;
  total_claims: number;
  medical_claims: number;
  pharmacy_claims: number;
  rules_evaluated: number;
  scores_generated: number;
  cases_created: number;
  high_risk: number;
  critical_risk: number;
  elapsed_seconds: number;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const PHASE_DEFINITIONS: { key: string; label: string; icon: React.ElementType }[] = [
  { key: "loading", label: "Loading Claims", icon: Database },
  { key: "enrichment", label: "Enriching Data", icon: FileSearch },
  { key: "rules", label: "Evaluating Rules", icon: Cog },
  { key: "scoring", label: "Calculating Scores", icon: BarChart3 },
  { key: "cases", label: "Creating Cases", icon: Shield },
];

function initialPhases(): PhaseState[] {
  return PHASE_DEFINITIONS.map((d) => ({
    ...d,
    progress: 0,
    detail: "",
    current: 0,
    total: 0,
    status: "pending" as const,
  }));
}

/* ------------------------------------------------------------------ */
/*  SSE line-parser helper                                             */
/* ------------------------------------------------------------------ */

interface SSEEvent {
  event: string;
  data: string;
}

function parseSSEChunk(buffer: string): { events: SSEEvent[]; remainder: string } {
  const events: SSEEvent[] = [];
  const blocks = buffer.split("\n\n");
  // The last segment may be incomplete – keep it as remainder.
  const remainder = blocks.pop() ?? "";

  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data = line.slice(5).trim();
      }
    }
    if (data) {
      events.push({ event, data });
    }
  }

  return { events, remainder };
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function PipelineMonitor({ workspaceId, onComplete }: PipelineMonitorProps) {
  const { activeWorkspace } = useWorkspace();
  const resolvedWorkspace = workspaceId !== undefined ? workspaceId : activeWorkspace;

  const [limit, setLimit] = useState<number>(1000);
  const [running, setRunning] = useState(false);
  const [phases, setPhases] = useState<PhaseState[]>(initialPhases);
  const [summary, setSummary] = useState<CompleteSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Abort controller so the user can (eventually) cancel via unmount.
  const abortRef = useRef<AbortController | null>(null);

  /* ---- stream handler ---- */

  const handleEvent = useCallback(
    (evt: SSEEvent) => {
      try {
        const payload = JSON.parse(evt.data);

        if (evt.event === "phase") {
          setPhases((prev) =>
            prev.map((p) => {
              if (p.key === payload.phase) {
                return {
                  ...p,
                  label: payload.label || p.label,
                  progress: payload.progress ?? p.progress,
                  status: payload.progress >= 100 ? "complete" : "active",
                };
              }
              // Mark earlier phases as complete when a later phase arrives.
              const idx = PHASE_DEFINITIONS.findIndex((d) => d.key === payload.phase);
              const pIdx = PHASE_DEFINITIONS.findIndex((d) => d.key === p.key);
              if (pIdx < idx && p.status !== "complete") {
                return { ...p, status: "complete", progress: 100 };
              }
              return p;
            }),
          );
        }

        if (evt.event === "progress") {
          setPhases((prev) =>
            prev.map((p) => {
              if (p.key === payload.phase) {
                return {
                  ...p,
                  progress: payload.progress ?? p.progress,
                  current: payload.current ?? p.current,
                  total: payload.total ?? p.total,
                  detail: payload.detail ?? p.detail,
                  status: (payload.progress ?? 0) >= 100 ? "complete" : "active",
                };
              }
              // Mark earlier phases as complete.
              const idx = PHASE_DEFINITIONS.findIndex((d) => d.key === payload.phase);
              const pIdx = PHASE_DEFINITIONS.findIndex((d) => d.key === p.key);
              if (pIdx < idx && p.status !== "complete") {
                return { ...p, status: "complete", progress: 100 };
              }
              return p;
            }),
          );
        }

        if (evt.event === "complete") {
          setSummary(payload as CompleteSummary);
          setPhases((prev) =>
            prev.map((p) => ({ ...p, status: "complete", progress: 100 })),
          );
          setRunning(false);
          onComplete?.();
        }
      } catch {
        // Ignore malformed JSON lines – the stream may send keep-alive comments.
      }
    },
    [onComplete],
  );

  /* ---- run pipeline ---- */

  const runPipeline = useCallback(async () => {
    // Reset state.
    setPhases(initialPhases());
    setSummary(null);
    setError(null);
    setRunning(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/pipeline/run-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit, workspace_id: resolvedWorkspace }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "Unknown error");
        throw new Error(`Pipeline request failed (${res.status}): ${text}`);
      }

      if (!res.body) {
        throw new Error("Response body is not readable.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = "";

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += decoder.decode(value, { stream: true });
        const { events, remainder } = parseSSEChunk(sseBuffer);
        sseBuffer = remainder;

        for (const e of events) {
          handleEvent(e);
        }
      }

      // Process any trailing data remaining in the buffer.
      if (sseBuffer.trim()) {
        const { events } = parseSSEChunk(sseBuffer + "\n\n");
        for (const e of events) {
          handleEvent(e);
        }
      }
    } catch (err: unknown) {
      if ((err as DOMException)?.name === "AbortError") return;
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [limit, resolvedWorkspace, handleEvent]);

  /* ---- helpers ---- */

  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US").format(n);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  return (
    <div className="space-y-6">
      {/* ---- Controls ---- */}
      <div className="flex items-end gap-4">
        <div>
          <label
            htmlFor="claim-limit"
            className="block text-xs font-medium text-gray-500 mb-1"
          >
            Claim limit
          </label>
          <input
            id="claim-limit"
            type="number"
            min={1}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value) || 1)}
            disabled={running}
            className="w-32 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm
                       shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1
                       focus:ring-blue-500 disabled:opacity-50"
          />
        </div>

        <button
          onClick={runPipeline}
          disabled={running}
          className={cn(
            "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium",
            "shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
            running
              ? "cursor-not-allowed bg-gray-300 text-gray-500"
              : "bg-blue-600 text-white hover:bg-blue-700",
          )}
        >
          {running ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Play size={16} />
          )}
          {running ? "Running..." : "Run Pipeline"}
        </button>
      </div>

      {/* ---- Error ---- */}
      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-medium">Pipeline Error</p>
          <p className="mt-1">{error}</p>
        </div>
      )}

      {/* ---- Phase Stepper ---- */}
      {(running || summary || phases.some((p) => p.status !== "pending")) && (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">
              Pipeline Progress
            </h3>
          </div>

          <div className="px-5 py-4 space-y-0">
            {phases.map((phase, idx) => {
              const Icon = phase.icon;
              const isLast = idx === phases.length - 1;

              return (
                <div key={phase.key} className="flex gap-4">
                  {/* ---- Stepper rail ---- */}
                  <div className="flex flex-col items-center">
                    <div
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-500",
                        phase.status === "complete" && "bg-green-100 text-green-600",
                        phase.status === "active" && "bg-blue-100 text-blue-600",
                        phase.status === "pending" && "bg-gray-100 text-gray-400",
                      )}
                    >
                      {phase.status === "complete" ? (
                        <CheckCircle size={18} />
                      ) : phase.status === "active" ? (
                        <Icon size={18} className="animate-pulse" />
                      ) : (
                        <Icon size={18} />
                      )}
                    </div>
                    {!isLast && (
                      <div
                        className={cn(
                          "w-0.5 flex-1 min-h-[24px] transition-colors duration-500",
                          phase.status === "complete"
                            ? "bg-green-300"
                            : "bg-gray-200",
                        )}
                      />
                    )}
                  </div>

                  {/* ---- Phase content ---- */}
                  <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
                    <div className="flex items-center justify-between">
                      <p
                        className={cn(
                          "text-sm font-medium transition-colors duration-300",
                          phase.status === "complete" && "text-green-700",
                          phase.status === "active" && "text-blue-700",
                          phase.status === "pending" && "text-gray-400",
                        )}
                      >
                        {phase.label}
                      </p>
                      {phase.total > 0 && (
                        <span className="text-xs text-gray-500">
                          {fmt(phase.current)} / {fmt(phase.total)}
                        </span>
                      )}
                    </div>

                    {phase.detail && (
                      <p className="mt-0.5 text-xs text-gray-500 truncate max-w-md">
                        {phase.detail}
                      </p>
                    )}

                    {/* Progress bar */}
                    {phase.status !== "pending" && (
                      <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-500 ease-out",
                            phase.status === "complete"
                              ? "bg-green-500"
                              : "bg-blue-500",
                          )}
                          style={{ width: `${Math.min(phase.progress, 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ---- Completion Summary ---- */}
      {summary && (
        <div className="rounded-lg border border-green-200 bg-green-50 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
          <div className="px-5 py-4 border-b border-green-200">
            <div className="flex items-center gap-2">
              <CheckCircle size={18} className="text-green-600" />
              <h3 className="text-sm font-semibold text-green-800">
                Pipeline Complete
              </h3>
              <span className="ml-auto text-xs text-green-600">
                {summary.elapsed_seconds.toFixed(1)}s elapsed
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 px-5 py-4">
            {([
              ["Batch ID", summary.batch_id],
              ["Total Claims", fmt(summary.total_claims)],
              ["Medical Claims", fmt(summary.medical_claims)],
              ["Pharmacy Claims", fmt(summary.pharmacy_claims)],
              ["Rules Evaluated", fmt(summary.rules_evaluated)],
              ["Scores Generated", fmt(summary.scores_generated)],
              ["Cases Created", fmt(summary.cases_created)],
              ["High Risk", fmt(summary.high_risk)],
              ["Critical Risk", fmt(summary.critical_risk)],
            ] as [string, string][]).map(([label, value]) => (
              <div key={label}>
                <p className="text-[11px] font-medium text-green-600 uppercase tracking-wider">
                  {label}
                </p>
                <p
                  className={cn(
                    "mt-0.5 text-sm font-semibold",
                    label === "Critical Risk"
                      ? "text-red-700"
                      : label === "High Risk"
                        ? "text-orange-700"
                        : "text-green-900",
                  )}
                >
                  {value}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
