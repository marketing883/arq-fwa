"use client";

import { useState, useCallback, useRef, DragEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import { useWorkspace } from "@/lib/workspace-context";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

type ClaimType = "medical" | "pharmacy";

interface PreviewResponse {
  file_name: string;
  total_rows: number;
  columns: string[];
  preview_rows: Record<string, string>[];
  suggested_mapping: Record<string, string>;  // csv_col -> internal_field
  target_fields: string[];                    // all available internal field names
  unmapped_required: string[];
}

interface IngestResponse {
  workspace_id: string;
  claim_type: string;
  rows_imported: number;
  rows_skipped: number;
  errors: string[];
}

/* -------------------------------------------------------------------------- */
/*  Step indicator                                                            */
/* -------------------------------------------------------------------------- */

const STEPS = [
  { number: 1, label: "Create Workspace" },
  { number: 2, label: "Column Mapping" },
  { number: 3, label: "Ingest & Results" },
] as const;

function StepIndicator({ current }: { current: number }) {
  return (
    <nav aria-label="Upload steps" className="flex items-center justify-center gap-2">
      {STEPS.map((step, idx) => {
        const isActive = step.number === current;
        const isComplete = step.number < current;
        return (
          <div key={step.number} className="flex items-center gap-2">
            {idx > 0 && (
              <div
                className={cn(
                  "h-px w-10 sm:w-16",
                  isComplete || isActive ? "bg-brand-blue" : "bg-border",
                )}
              />
            )}
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-colors",
                  isComplete
                    ? "bg-brand-blue text-white"
                    : isActive
                      ? "bg-brand-blue text-white ring-4 ring-brand-blue/20"
                      : "bg-border text-text-tertiary",
                )}
              >
                {isComplete ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  step.number
                )}
              </div>
              <span
                className={cn(
                  "hidden text-sm font-medium sm:inline",
                  isActive ? "text-text-primary" : "text-text-tertiary",
                )}
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </nav>
  );
}

/* -------------------------------------------------------------------------- */
/*  Main component                                                            */
/* -------------------------------------------------------------------------- */

export default function UploadPage() {
  const router = useRouter();
  const { refreshWorkspaces, setActiveWorkspace } = useWorkspace();

  // Global wizard state
  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Step 1 state
  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [description, setDescription] = useState("");
  const [claimType, setClaimType] = useState<ClaimType>("medical");
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 2 state (populated after preview call)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

  // Step 3 state
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);

  /* ======================================================================== */
  /*  File handling                                                           */
  /* ======================================================================== */

  const handleFile = useCallback((f: File) => {
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a CSV file.");
      return;
    }
    setFile(f);
    setError(null);
  }, []);

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      const f = e.dataTransfer.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const onFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  /* ======================================================================== */
  /*  Step 1 -> Step 2 transition                                             */
  /* ======================================================================== */

  const submitStep1 = useCallback(async () => {
    if (!name.trim()) {
      setError("Workspace name is required.");
      return;
    }
    if (!file) {
      setError("Please upload a CSV file.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      // 1. Create workspace
      const wsRes = await fetch("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          client_name: clientName.trim() || null,
          description: description.trim() || null,
        }),
      });
      if (!wsRes.ok) {
        const body = await wsRes.json().catch(() => null);
        throw new Error(body?.detail ?? `Failed to create workspace (${wsRes.status})`);
      }
      const wsData = await wsRes.json();
      const wsId: string = wsData.workspace_id;
      setWorkspaceId(wsId);

      // 2. Upload preview
      const form = new FormData();
      form.append("file", file);
      form.append("claim_type", claimType);

      const prevRes = await fetch(`/api/workspaces/${wsId}/upload/preview`, {
        method: "POST",
        body: form,
      });
      if (!prevRes.ok) {
        const body = await prevRes.json().catch(() => null);
        throw new Error(body?.detail ?? `Failed to preview file (${prevRes.status})`);
      }
      const prevData: PreviewResponse = await prevRes.json();
      setPreview(prevData);
      setColumnMapping({ ...prevData.suggested_mapping });

      // Advance
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }, [name, clientName, description, file, claimType]);

  /* ======================================================================== */
  /*  Step 2 -> Step 3 transition                                             */
  /* ======================================================================== */

  const submitStep2 = useCallback(async () => {
    if (!workspaceId || !preview || !file) return;

    setError(null);
    setLoading(true);

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("claim_type", claimType);
      form.append("mapping", JSON.stringify(columnMapping));

      const res = await fetch(`/api/workspaces/${workspaceId}/upload/ingest`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Ingest failed (${res.status})`);
      }
      const data: IngestResponse = await res.json();
      setIngestResult(data);

      // Update workspace context
      await refreshWorkspaces();
      setActiveWorkspace(workspaceId);

      setStep(3);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, preview, file, claimType, columnMapping, refreshWorkspaces, setActiveWorkspace]);

  /* ======================================================================== */
  /*  Column mapping helpers                                                  */
  /* ======================================================================== */

  // All possible internal field names for the mapping dropdown
  const allTargetOptions = preview?.target_fields ?? [];

  const updateMapping = (csvCol: string, target: string) => {
    setColumnMapping((prev) => ({ ...prev, [csvCol]: target }));
  };

  /* ======================================================================== */
  /*  Render                                                                  */
  /* ======================================================================== */

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-[15px] font-semibold text-text-primary tracking-tight">Upload Claims Data</h1>
        <p className="mt-1 text-sm text-text-tertiary">
          Import a CSV of claims into a new workspace for FWA analysis.
        </p>
      </div>

      {/* Step indicator */}
      <div className="card p-4">
        <StepIndicator current={step} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-risk-critical bg-risk-critical-bg px-4 py-3 text-sm text-risk-critical-text">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ================================================================== */}
      {/*  STEP 1 - Create Workspace                                         */}
      {/* ================================================================== */}
      {step === 1 && (
        <div className="card">
          <div className="border-b border-border px-6 py-4">
            <h2 className="text-lg font-semibold text-text-primary">Create Workspace</h2>
            <p className="mt-1 text-sm text-text-tertiary">
              Set up a new workspace and upload your claims CSV file.
            </p>
          </div>

          <div className="px-6 py-6 space-y-5">
            {/* Name */}
            <div>
              <label htmlFor="ws-name" className="block text-sm font-medium text-text-secondary mb-1">
                Workspace Name <span className="text-risk-critical">*</span>
              </label>
              <input
                id="ws-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Q4 2025 Medical Claims"
                className="input block w-full placeholder:text-text-quaternary"
              />
            </div>

            {/* Client name */}
            <div>
              <label htmlFor="ws-client" className="block text-sm font-medium text-text-secondary mb-1">
                Client Name
              </label>
              <input
                id="ws-client"
                type="text"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. Acme Health Plan"
                className="input block w-full placeholder:text-text-quaternary"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="ws-desc" className="block text-sm font-medium text-text-secondary mb-1">
                Description
              </label>
              <textarea
                id="ws-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional notes about this dataset..."
                rows={3}
                className="input block w-full placeholder:text-text-quaternary"
              />
            </div>

            {/* Claim type */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Claim Type <span className="text-risk-critical">*</span>
              </label>
              <div className="flex gap-3">
                {(["medical", "pharmacy"] as const).map((ct) => (
                  <button
                    key={ct}
                    type="button"
                    onClick={() => setClaimType(ct)}
                    className={cn(
                      "px-4 py-2 rounded-md text-sm font-medium transition-colors capitalize",
                      claimType === ct
                        ? "bg-brand-blue text-white"
                        : "bg-surface-card text-text-secondary border border-border hover:bg-surface-page",
                    )}
                  >
                    {ct}
                  </button>
                ))}
              </div>
            </div>

            {/* File upload zone */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                CSV File <span className="text-risk-critical">*</span>
              </label>

              <div
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
                  dragActive
                    ? "border-brand-blue bg-brand-blue/5"
                    : file
                      ? "border-risk-low bg-risk-low-bg"
                      : "border-border bg-surface-page hover:border-text-quaternary hover:bg-surface-page",
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={onFileChange}
                  className="hidden"
                />

                {file ? (
                  <div className="flex flex-col items-center gap-2">
                    <FileSpreadsheet className="h-10 w-10 text-risk-low" />
                    <p className="text-sm font-medium text-text-primary">{file.name}</p>
                    <p className="text-xs text-text-tertiary">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                    <p className="text-xs text-text-quaternary">
                      Click or drag to replace
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="h-10 w-10 text-text-quaternary" />
                    <p className="text-sm font-medium text-text-secondary">
                      Drag and drop your CSV file here
                    </p>
                    <p className="text-xs text-text-tertiary">
                      or click to browse
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Step 1 footer */}
          <div className="flex justify-end border-t border-border px-6 py-4">
            <button
              onClick={submitStep1}
              disabled={loading}
              className={cn(
                "btn-primary",
                loading && "cursor-not-allowed opacity-60",
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  Next: Column Mapping
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ================================================================== */}
      {/*  STEP 2 - Column Mapping                                           */}
      {/* ================================================================== */}
      {step === 2 && preview && (
        <div className="card">
          <div className="border-b border-border px-6 py-4">
            <h2 className="text-lg font-semibold text-text-primary">Column Mapping</h2>
            <p className="mt-1 text-sm text-text-tertiary">
              We detected <span className="font-medium text-text-secondary">{preview.total_rows}</span>{" "}
              rows and <span className="font-medium text-text-secondary">{preview.columns.length}</span>{" "}
              columns. Review and adjust the mapping below.
            </p>
          </div>

          {/* Mapping table */}
          <div className="px-6 py-6">
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th>CSV Column</th>
                    <th>Maps To</th>
                    <th>Sample Values</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {preview.columns.map((col) => {
                    const samples = preview.preview_rows
                      .slice(0, 3)
                      .map((row) => row[col])
                      .filter(Boolean);
                    return (
                      <tr key={col} className="table-row">
                        <td className="font-mono text-xs text-text-primary">
                          {col}
                        </td>
                        <td>
                          <select
                            value={columnMapping[col] ?? ""}
                            onChange={(e) => updateMapping(col, e.target.value)}
                            className="input block w-full"
                          >
                            <option value="">-- skip --</option>
                            {allTargetOptions.map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="text-xs text-text-tertiary truncate max-w-xs">
                          {samples.join(", ") || "--"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Preview table */}
          {preview.preview_rows.length > 0 && (
            <div className="px-6 pb-6">
              <h3 className="text-sm font-semibold text-text-secondary mb-2">Data Preview</h3>
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="table-header">
                      {preview.columns.map((col) => (
                        <th key={col} className="whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {preview.preview_rows.slice(0, 5).map((row, i) => (
                      <tr key={i} className="table-row">
                        {preview.columns.map((col) => (
                          <td
                            key={col}
                            className="whitespace-nowrap max-w-[200px] truncate"
                          >
                            {row[col] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Step 2 footer */}
          <div className="flex justify-between border-t border-border px-6 py-4">
            <button
              onClick={() => {
                setStep(1);
                setError(null);
              }}
              disabled={loading}
              className="btn-secondary"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <button
              onClick={submitStep2}
              disabled={loading}
              className={cn(
                "btn-primary",
                loading && "cursor-not-allowed opacity-60",
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Ingesting...
                </>
              ) : (
                <>
                  Confirm & Ingest
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ================================================================== */}
      {/*  STEP 3 - Ingest & Results                                         */}
      {/* ================================================================== */}
      {step === 3 && ingestResult && (
        <div className="card">
          <div className="border-b border-border px-6 py-4">
            <h2 className="text-lg font-semibold text-text-primary">Ingest Complete</h2>
          </div>

          <div className="px-6 py-8">
            <div className="mx-auto max-w-md text-center space-y-6">
              {/* Success icon */}
              <div className="flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-risk-low-bg">
                  <CheckCircle className="h-8 w-8 text-risk-low" />
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-text-primary">
                  Data Successfully Imported
                </h3>
                <p className="mt-1 text-sm text-text-tertiary">
                  Your claims data has been ingested into workspace{" "}
                  <span className="font-mono font-medium text-text-secondary">
                    {ingestResult.workspace_id}
                  </span>
                  .
                </p>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg bg-surface-page p-4">
                  <p className="text-2xl font-bold text-text-primary">
                    {ingestResult.rows_imported.toLocaleString()}
                  </p>
                  <p className="text-xs text-text-tertiary mt-1">Rows Imported</p>
                </div>
                <div className="rounded-lg bg-surface-page p-4">
                  <p className="text-2xl font-bold text-text-primary">
                    {ingestResult.rows_skipped.toLocaleString()}
                  </p>
                  <p className="text-xs text-text-tertiary mt-1">Rows Skipped</p>
                </div>
                <div className="rounded-lg bg-surface-page p-4">
                  <p className="text-2xl font-bold text-text-primary capitalize">
                    {ingestResult.claim_type}
                  </p>
                  <p className="text-xs text-text-tertiary mt-1">Claim Type</p>
                </div>
              </div>

              {/* Errors */}
              {ingestResult.errors.length > 0 && (
                <div className="rounded-lg border border-risk-medium bg-risk-medium-bg p-4 text-left">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle className="h-4 w-4 text-risk-medium" />
                    <span className="text-sm font-medium text-risk-medium-text">
                      {ingestResult.errors.length} warning{ingestResult.errors.length !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {ingestResult.errors.map((err, i) => (
                      <li key={i} className="text-xs text-risk-medium-text">
                        {err}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-center gap-3 pt-2">
                <button
                  onClick={() => router.push("/claims")}
                  className="btn-primary"
                >
                  View Claims
                  <ArrowRight className="h-4 w-4" />
                </button>
                <button
                  onClick={() => {
                    // Reset wizard for another upload
                    setStep(1);
                    setName("");
                    setClientName("");
                    setDescription("");
                    setClaimType("medical");
                    setFile(null);
                    setWorkspaceId(null);
                    setPreview(null);
                    setColumnMapping({});
                    setIngestResult(null);
                    setError(null);
                  }}
                  className="btn-secondary"
                >
                  Upload Another
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
