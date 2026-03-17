"use client";
import { useEffect, useState } from "react";
import { ingestion, type DataSourceSummary, type IngestionRunItem } from "@/lib/api";

export default function DataSourcesPage() {
  const [sources, setSources] = useState<DataSourceSummary[]>([]);
  const [runs, setRuns] = useState<IngestionRunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState("watched_folder");
  const [formClaimType, setFormClaimType] = useState("medical");
  const [formPath, setFormPath] = useState("");
  const [formPattern, setFormPattern] = useState("*.csv");
  const [formInterval, setFormInterval] = useState(3600);

  // Detail view
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [sourceRuns, setSourceRuns] = useState<IngestionRunItem[]>([]);
  const [testResult, setTestResult] = useState<{ status: string; message: string; sample_rows: Record<string, unknown>[] } | null>(null);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([ingestion.sources(), ingestion.runs()])
      .then(([src, r]) => {
        setSources(src.sources);
        setRuns(r.runs);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const connectionConfig: Record<string, string> = {};
      if (formType === "watched_folder") {
        connectionConfig.path = formPath;
        connectionConfig.pattern = formPattern;
      }
      await ingestion.createSource({
        name: formName,
        source_type: formType,
        claim_type: formClaimType,
        connection_config: connectionConfig,
        polling_interval_seconds: formInterval,
      });
      setShowCreate(false);
      setFormName("");
      setFormPath("");
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleToggle(source: DataSourceSummary) {
    try {
      await ingestion.updateSource(source.source_id, {
        is_enabled: !source.is_enabled,
      });
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handlePollNow(sourceId: string) {
    try {
      await ingestion.pollNow(sourceId);
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleTest(sourceId: string) {
    try {
      setTestResult(null);
      const result = await ingestion.testConnection(sourceId);
      setTestResult(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleSelectSource(sourceId: string) {
    setSelectedSource(sourceId === selectedSource ? null : sourceId);
    if (sourceId !== selectedSource) {
      try {
        const result = await ingestion.runs(sourceId);
        setSourceRuns(result.runs);
      } catch {
        setSourceRuns([]);
      }
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case "completed": return "text-arq-lime-400";
      case "running": return "text-arq-blue-400";
      case "failed": return "text-red-400";
      case "no_data": return "text-t-muted";
      default: return "text-t-secondary";
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-t-primary">Data Sources</h1>
          <p className="text-sm text-t-muted mt-1">
            Configure continuous data ingestion from external sources
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {testResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${testResult.status === "ok" ? "bg-arq-lime-500/10 border border-arq-lime-500/20 text-arq-lime-400" : "bg-red-500/10 border border-red-500/20 text-red-400"}`}>
          <strong>Test: </strong>{testResult.message}
          {testResult.sample_rows.length > 0 && (
            <pre className="mt-2 text-xs overflow-auto max-h-40">{JSON.stringify(testResult.sample_rows, null, 2)}</pre>
          )}
          <button onClick={() => setTestResult(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-arq-blue-500 text-white rounded-lg text-sm font-medium hover:bg-arq-blue-600 transition-colors"
        >
          Add Data Source
        </button>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="mb-6 p-4 bg-surface-1 border border-white/[0.06] rounded-lg grid grid-cols-2 gap-4"
        >
          <input
            placeholder="Source Name"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            required
            className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
          />
          <select
            value={formType}
            onChange={(e) => setFormType(e.target.value)}
            className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
          >
            <option value="watched_folder">Watched Folder</option>
            <option value="api_endpoint">API Endpoint</option>
            <option value="database_query">Database Query</option>
          </select>
          <select
            value={formClaimType}
            onChange={(e) => setFormClaimType(e.target.value)}
            className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
          >
            <option value="medical">Medical</option>
            <option value="pharmacy">Pharmacy</option>
          </select>
          <input
            type="number"
            placeholder="Polling Interval (seconds)"
            value={formInterval}
            onChange={(e) => setFormInterval(Number(e.target.value))}
            min={60}
            className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
          />
          {formType === "watched_folder" && (
            <>
              <input
                placeholder="Folder Path"
                value={formPath}
                onChange={(e) => setFormPath(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <input
                placeholder="File Pattern (e.g. *.csv)"
                value={formPattern}
                onChange={(e) => setFormPattern(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
            </>
          )}
          <div className="flex gap-2 col-span-2">
            <button
              type="submit"
              className="px-4 py-2 bg-arq-lime-500 text-black rounded-lg text-sm font-medium hover:bg-arq-lime-400 transition-colors"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-surface-2 text-t-muted rounded-lg text-sm hover:bg-surface-3 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-t-muted text-sm">Loading...</div>
      ) : (
        <div className="space-y-4">
          {sources.map((source) => (
            <div key={source.source_id} className="bg-surface-1 border border-white/[0.06] rounded-lg">
              <div className="px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4 cursor-pointer" onClick={() => handleSelectSource(source.source_id)}>
                  <div>
                    <div className="text-t-primary font-medium">{source.name}</div>
                    <div className="text-t-muted text-xs">
                      {source.source_type.replace("_", " ")} &middot; {source.claim_type} &middot; every {Math.round(source.polling_interval_seconds / 60)}m
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTest(source.source_id)}
                    className="px-3 py-1 bg-surface-2 text-t-muted rounded-lg text-xs hover:bg-surface-3 transition-colors"
                  >
                    Test
                  </button>
                  <button
                    onClick={() => handlePollNow(source.source_id)}
                    className="px-3 py-1 bg-arq-blue-500/20 text-arq-blue-400 rounded-lg text-xs hover:bg-arq-blue-500/30 transition-colors"
                  >
                    Poll Now
                  </button>
                  <button
                    onClick={() => handleToggle(source)}
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      source.is_enabled
                        ? "bg-arq-lime-500/20 text-arq-lime-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {source.is_enabled ? "Enabled" : "Disabled"}
                  </button>
                </div>
              </div>
              {selectedSource === source.source_id && sourceRuns.length > 0 && (
                <div className="border-t border-white/[0.06] px-4 py-3">
                  <h4 className="text-xs font-medium text-t-muted mb-2">Recent Ingestion Runs</h4>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-t-muted">
                        <th className="text-left py-1">Run ID</th>
                        <th className="text-left py-1">Status</th>
                        <th className="text-left py-1">Rows</th>
                        <th className="text-left py-1">Errors</th>
                        <th className="text-left py-1">Duration</th>
                        <th className="text-left py-1">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sourceRuns.slice(0, 10).map((run) => (
                        <tr key={run.run_id} className="border-t border-white/[0.04]">
                          <td className="py-1 font-mono text-t-secondary">{run.run_id}</td>
                          <td className={`py-1 ${statusColor(run.status)}`}>{run.status}</td>
                          <td className="py-1 text-t-secondary">{run.rows_ingested}/{run.rows_found}</td>
                          <td className="py-1 text-t-secondary">{run.error_count}</td>
                          <td className="py-1 text-t-secondary">{run.duration_seconds ? `${run.duration_seconds}s` : "-"}</td>
                          <td className="py-1 text-t-muted">{run.started_at || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
          {sources.length === 0 && (
            <div className="text-center text-t-muted py-8">
              No data sources configured. Add one to enable continuous ingestion.
            </div>
          )}
        </div>
      )}

      {/* Recent Runs Summary */}
      {!loading && runs.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-t-primary mb-4">Recent Ingestion Runs</h2>
          <div className="bg-surface-1 border border-white/[0.06] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Run ID</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Rows Found</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Ingested</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Errors</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Duration</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 20).map((run) => (
                  <tr key={run.run_id} className="border-b border-white/[0.04] hover:bg-surface-2/50">
                    <td className="px-4 py-3 font-mono text-t-secondary text-xs">{run.run_id}</td>
                    <td className={`px-4 py-3 ${statusColor(run.status)}`}>{run.status}</td>
                    <td className="px-4 py-3 text-t-secondary">{run.rows_found}</td>
                    <td className="px-4 py-3 text-t-secondary">{run.rows_ingested}</td>
                    <td className="px-4 py-3 text-t-secondary">{run.error_count}</td>
                    <td className="px-4 py-3 text-t-muted">{run.duration_seconds ? `${run.duration_seconds}s` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
