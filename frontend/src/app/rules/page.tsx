"use client";
import { useEffect, useState } from "react";
import { rules, type RuleSummary, type RuleStats } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ToggleLeft, ToggleRight, Save, RotateCcw } from "lucide-react";

type ClaimTypeTab = "medical" | "pharmacy";

function SkeletonBar({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-border", className)} />;
}

function renderThresholdInput(
  key: string,
  value: unknown,
  onChange: (key: string, newValue: unknown) => void
): React.ReactNode {
  if (typeof value === "boolean") {
    return (
      <div key={key} className="flex items-center justify-between py-2">
        <label className="text-sm text-text-secondary font-medium">{key}</label>
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(key, e.target.checked)}
          className="h-4 w-4 text-brand-blue rounded border-border focus:ring-brand-blue/20"
        />
      </div>
    );
  }
  if (typeof value === "number") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-text-secondary font-medium">{key}</label>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(key, parseFloat(e.target.value) || 0)}
          step="any"
          className="input w-32 text-right"
        />
      </div>
    );
  }
  if (typeof value === "string") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-text-secondary font-medium">{key}</label>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(key, e.target.value)}
          className="input w-48"
        />
      </div>
    );
  }
  // Nested object / array: JSON textarea
  return (
    <div key={key} className="py-2">
      <label className="text-sm text-text-secondary font-medium block mb-1">{key}</label>
      <textarea
        value={JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            onChange(key, JSON.parse(e.target.value));
          } catch {
            // Allow typing invalid JSON while editing
          }
        }}
        rows={4}
        className="input w-full font-mono resize-none"
      />
    </div>
  );
}

export default function RuleConfigurationPage() {
  // All rules data
  const [allRules, setAllRules] = useState<RuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tabs
  const [activeTab, setActiveTab] = useState<ClaimTypeTab>("medical");

  // Selected rule for editing
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);

  // Edit form state
  const [editWeight, setEditWeight] = useState<number>(1.0);
  const [editEnabled, setEditEnabled] = useState<boolean>(true);
  const [editThresholds, setEditThresholds] = useState<Record<string, unknown>>({});
  const [originalRule, setOriginalRule] = useState<RuleSummary | null>(null);

  // Rule stats
  const [ruleStats, setRuleStats] = useState<RuleStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Saving
  const [saving, setSaving] = useState(false);

  // Load all rules
  useEffect(() => {
    setLoading(true);
    setError(null);
    rules
      .list()
      .then((data) => setAllRules(data.rules))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Filter rules by tab
  const filteredRules = allRules.filter((r) => r.claim_type === activeTab);

  // When a rule is selected, populate edit form and load stats
  function selectRule(rule: RuleSummary) {
    setSelectedRuleId(rule.rule_id);
    setEditWeight(rule.weight);
    setEditEnabled(rule.enabled);
    setEditThresholds({ ...rule.thresholds });
    setOriginalRule(rule);

    // Load stats
    setStatsLoading(true);
    setRuleStats(null);
    rules
      .stats(rule.rule_id)
      .then(setRuleStats)
      .catch(() => setRuleStats(null))
      .finally(() => setStatsLoading(false));
  }

  function handleThresholdChange(key: string, newValue: unknown) {
    setEditThresholds((prev) => ({ ...prev, [key]: newValue }));
  }

  async function handleSave() {
    if (!selectedRuleId || saving) return;
    setSaving(true);
    try {
      const updatedRule = await rules.updateConfig(selectedRuleId, {
        weight: editWeight,
        enabled: editEnabled,
        thresholds: editThresholds,
      });
      // Update the rule in the list
      setAllRules((prev) =>
        prev.map((r) => (r.rule_id === updatedRule.rule_id ? updatedRule : r))
      );
      setOriginalRule(updatedRule);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save rule");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (originalRule) {
      setEditWeight(originalRule.weight);
      setEditEnabled(originalRule.enabled);
      setEditThresholds({ ...originalRule.thresholds });
    }
  }

  function handleCancel() {
    setSelectedRuleId(null);
    setOriginalRule(null);
    setRuleStats(null);
  }

  const selectedRule = allRules.find((r) => r.rule_id === selectedRuleId);

  return (
    <div>
      {/* Page Title */}
      <h1 className="text-[15px] font-semibold text-text-primary tracking-tight mb-6">
        Rule Configuration
      </h1>

      {error && (
        <div className="bg-risk-critical-bg border border-risk-critical rounded-lg p-4 mb-6 text-risk-critical-text">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===== LEFT PANEL: Rules List ===== */}
        <div className="card overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-border">
            {(["medical", "pharmacy"] as ClaimTypeTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab);
                  setSelectedRuleId(null);
                  setOriginalRule(null);
                  setRuleStats(null);
                }}
                className={cn(
                  "tab flex-1 text-center capitalize",
                  activeTab === tab && "tab-active"
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Rules table */}
          {loading ? (
            <div className="p-6 space-y-3">
              <SkeletonBar className="h-4 w-3/4" />
              <SkeletonBar className="h-4 w-full" />
              <SkeletonBar className="h-4 w-5/6" />
              <SkeletonBar className="h-4 w-full" />
              <SkeletonBar className="h-4 w-2/3" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="table-header">
                  <tr>
                    <th className="text-left">Rule ID</th>
                    <th className="text-left">Category</th>
                    <th className="text-left">Fraud Type</th>
                    <th className="text-right">Weight</th>
                    <th className="text-center">Enabled</th>
                    <th className="text-center">Edit</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRules.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-text-tertiary">
                        No rules found for {activeTab} claims.
                      </td>
                    </tr>
                  ) : (
                    filteredRules.map((rule) => (
                      <tr
                        key={rule.rule_id}
                        className={cn(
                          "table-row",
                          selectedRuleId === rule.rule_id && "bg-brand-blue/5"
                        )}
                      >
                        <td className="font-mono text-xs">{rule.rule_id}</td>
                        <td className="capitalize">{rule.category}</td>
                        <td className="capitalize">
                          {rule.fraud_type.replace(/_/g, " ")}
                        </td>
                        <td className="text-right font-mono">{rule.weight.toFixed(1)}</td>
                        <td className="text-center">
                          <span
                            className={cn(
                              "inline-block w-3 h-3 rounded-full",
                              rule.enabled ? "bg-risk-low" : "bg-risk-critical"
                            )}
                            title={rule.enabled ? "Enabled" : "Disabled"}
                          />
                        </td>
                        <td className="text-center">
                          <button
                            onClick={() => selectRule(rule)}
                            className="text-brand-blue hover:text-brand-blue text-xs font-medium hover:underline"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ===== RIGHT PANEL: Rule Config ===== */}
        <div>
          {!selectedRule ? (
            <div className="card p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-surface-page mx-auto mb-3 flex items-center justify-center">
                <svg className="w-6 h-6 text-text-quaternary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
                </svg>
              </div>
              <p className="text-text-tertiary text-sm">Select a rule from the list to configure it.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Rule Config Card */}
              <div className="card p-6">
                {/* Header */}
                <div className="mb-6">
                  <h2 className="card-title font-mono">{selectedRule.rule_id}</h2>
                  <p className="card-subtitle capitalize">{selectedRule.category}</p>
                </div>

                {/* Description */}
                {selectedRule.description && (
                  <div className="mb-4">
                    <label className="section-label block mb-1">
                      Description
                    </label>
                    <p className="text-sm text-text-secondary bg-surface-page rounded-md p-3">
                      {selectedRule.description}
                    </p>
                  </div>
                )}

                {/* Detection Logic */}
                {selectedRule.detection_logic && (
                  <div className="mb-4">
                    <label className="section-label block mb-1">
                      Detection Logic
                    </label>
                    <p className="text-xs text-text-secondary bg-surface-page rounded-md p-3 font-mono leading-relaxed">
                      {selectedRule.detection_logic}
                    </p>
                  </div>
                )}

                {/* Weight Slider */}
                <div className="mb-4">
                  <label className="section-label block mb-2">
                    Weight
                  </label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="1.0"
                      max="10.0"
                      step="0.5"
                      value={editWeight}
                      onChange={(e) => setEditWeight(parseFloat(e.target.value))}
                      className="flex-1 h-2 bg-border rounded-lg appearance-none cursor-pointer accent-brand-blue"
                    />
                    <span className="w-12 text-center text-sm font-mono font-semibold bg-surface-page rounded-md px-2 py-1">
                      {editWeight.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Enabled Toggle */}
                <div className="mb-4">
                  <label className="section-label block mb-2">
                    Enabled
                  </label>
                  <button
                    onClick={() => setEditEnabled(!editEnabled)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                      editEnabled
                        ? "bg-risk-low-bg text-risk-low-text border border-risk-low"
                        : "bg-risk-critical-bg text-risk-critical-text border border-risk-critical"
                    )}
                  >
                    {editEnabled ? (
                      <>
                        <ToggleRight className="w-5 h-5" />
                        Enabled
                      </>
                    ) : (
                      <>
                        <ToggleLeft className="w-5 h-5" />
                        Disabled
                      </>
                    )}
                  </button>
                </div>

                {/* Thresholds */}
                {Object.keys(editThresholds).length > 0 && (
                  <div className="mb-6">
                    <label className="section-label block mb-2">
                      Thresholds
                    </label>
                    <div className="border border-border rounded-md p-3 space-y-1 divide-y divide-border-subtle">
                      {Object.entries(editThresholds).map(([key, value]) =>
                        renderThresholdInput(key, value, handleThresholdChange)
                      )}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-4 border-t border-border">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className={cn(
                      "btn-primary",
                      saving && "opacity-60 cursor-not-allowed"
                    )}
                  >
                    <Save className="w-4 h-4" />
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={saving}
                    className="btn-secondary"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Reset to Defaults
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2 text-sm rounded-md font-medium text-text-tertiary hover:text-text-secondary hover:bg-surface-page transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>

              {/* Stats Section */}
              <div className="card p-6">
                <h3 className="section-label mb-4">
                  Rule Statistics
                </h3>
                {statsLoading ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <SkeletonBar className="h-8 w-16 mx-auto mb-2" />
                      <SkeletonBar className="h-3 w-20 mx-auto" />
                    </div>
                    <div className="text-center">
                      <SkeletonBar className="h-8 w-16 mx-auto mb-2" />
                      <SkeletonBar className="h-3 w-20 mx-auto" />
                    </div>
                    <div className="text-center">
                      <SkeletonBar className="h-8 w-16 mx-auto mb-2" />
                      <SkeletonBar className="h-3 w-20 mx-auto" />
                    </div>
                  </div>
                ) : ruleStats ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-text-primary tracking-tight leading-none" style={{ fontVariantNumeric: "tabular-nums" }}>
                        {ruleStats.times_triggered}
                      </p>
                      <p className="text-[11px] font-medium uppercase tracking-[0.05em] text-text-tertiary mt-2">Times Triggered</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-text-primary tracking-tight leading-none" style={{ fontVariantNumeric: "tabular-nums" }}>
                        {ruleStats.avg_severity.toFixed(2)}
                      </p>
                      <p className="text-[11px] font-medium uppercase tracking-[0.05em] text-text-tertiary mt-2">Avg Severity</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-text-primary tracking-tight leading-none" style={{ fontVariantNumeric: "tabular-nums" }}>
                        {(ruleStats.trigger_rate * 100).toFixed(1)}%
                      </p>
                      <p className="text-[11px] font-medium uppercase tracking-[0.05em] text-text-tertiary mt-2">Trigger Rate</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-text-tertiary">No stats available for this rule.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
