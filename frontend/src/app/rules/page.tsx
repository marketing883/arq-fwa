"use client";
import { useEffect, useState } from "react";
import { rules, type RuleSummary, type RuleStats } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Settings, ToggleLeft, ToggleRight, Save, RotateCcw } from "lucide-react";

type ClaimTypeTab = "medical" | "pharmacy";

function renderThresholdInput(
  key: string,
  value: unknown,
  onChange: (key: string, newValue: unknown) => void
): React.ReactNode {
  if (typeof value === "boolean") {
    return (
      <div key={key} className="flex items-center justify-between py-2">
        <label className="text-sm text-t-secondary font-medium">{key}</label>
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(key, e.target.checked)}
          className="h-4 w-4 text-arq-blue-400 rounded border-surface-3 focus:ring-arq-blue-500 bg-surface-2"
        />
      </div>
    );
  }
  if (typeof value === "number") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-t-secondary font-medium">{key}</label>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(key, parseFloat(e.target.value) || 0)}
          step="any"
          className="w-32 bg-surface-2 border border-surface-3 text-t-primary rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-arq-blue-500 focus:border-transparent text-right"
        />
      </div>
    );
  }
  if (typeof value === "string") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-t-secondary font-medium">{key}</label>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(key, e.target.value)}
          className="w-48 bg-surface-2 border border-surface-3 text-t-primary rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-arq-blue-500 focus:border-transparent"
        />
      </div>
    );
  }
  // Nested object / array: JSON textarea
  return (
    <div key={key} className="py-2">
      <label className="text-sm text-t-secondary font-medium block mb-1">{key}</label>
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
        className="w-full bg-surface-2 border border-surface-3 text-t-primary rounded-md px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-arq-blue-500 focus:border-transparent resize-none"
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
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Settings className="w-6 h-6 text-t-muted" />
        Rule Configuration
      </h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===== LEFT PANEL: Rules List ===== */}
        <div className="glass-card rounded-lg border border-white/[0.06] overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-white/[0.06]">
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
                  "flex-1 px-4 py-3 text-sm font-medium text-center transition-colors capitalize",
                  activeTab === tab
                    ? "border-b-2 border-arq-blue-400 text-arq-blue-400 bg-arq-blue-500/10"
                    : "text-t-muted hover:text-t-secondary hover:bg-surface-2/40"
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Rules table */}
          {loading ? (
            <div className="p-8 text-center text-t-muted">Loading rules...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="dark-table w-full text-sm">
                <thead>
                  <tr className="bg-surface-2 border-b border-white/[0.06]">
                    <th className="text-left px-4 py-2.5 font-semibold text-t-secondary">Rule ID</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-t-secondary">Category</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-t-secondary">Fraud Type</th>
                    <th className="text-right px-4 py-2.5 font-semibold text-t-secondary">Weight</th>
                    <th className="text-center px-4 py-2.5 font-semibold text-t-secondary">Enabled</th>
                    <th className="text-center px-4 py-2.5 font-semibold text-t-secondary">Edit</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRules.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-t-muted">
                        No rules found for {activeTab} claims.
                      </td>
                    </tr>
                  ) : (
                    filteredRules.map((rule) => (
                      <tr
                        key={rule.rule_id}
                        className={cn(
                          "border-b border-white/[0.06] transition-colors",
                          selectedRuleId === rule.rule_id
                            ? "bg-arq-blue-500/10"
                            : "hover:bg-surface-2/40"
                        )}
                      >
                        <td className="px-4 py-2.5 font-mono text-xs">{rule.rule_id}</td>
                        <td className="px-4 py-2.5 text-t-secondary capitalize">{rule.category}</td>
                        <td className="px-4 py-2.5 text-t-secondary capitalize">
                          {rule.fraud_type.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono">{rule.weight.toFixed(1)}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span
                            className={cn(
                              "inline-block w-3 h-3 rounded-full",
                              rule.enabled ? "bg-arq-blue-500" : "bg-red-400"
                            )}
                            title={rule.enabled ? "Enabled" : "Disabled"}
                          />
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button
                            onClick={() => selectRule(rule)}
                            className="text-arq-blue-400 hover:text-arq-blue-300 text-xs font-medium hover:underline"
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
            <div className="glass-card rounded-lg border border-white/[0.06] p-8 text-center">
              <Settings className="w-12 h-12 text-t-muted mx-auto mb-3" />
              <p className="text-t-muted">Select a rule from the list to configure it.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Rule Config Card */}
              <div className="glass-card rounded-lg border border-white/[0.06] p-6">
                {/* Header */}
                <div className="mb-6">
                  <h2 className="text-lg font-semibold font-mono">{selectedRule.rule_id}</h2>
                  <p className="text-sm text-t-muted capitalize">{selectedRule.category}</p>
                </div>

                {/* Description */}
                {selectedRule.description && (
                  <div className="mb-4">
                    <label className="text-xs font-semibold text-t-muted uppercase tracking-wide block mb-1">
                      Description
                    </label>
                    <p className="text-sm text-t-secondary bg-surface-2 rounded-md p-3">
                      {selectedRule.description}
                    </p>
                  </div>
                )}

                {/* Detection Logic */}
                {selectedRule.detection_logic && (
                  <div className="mb-4">
                    <label className="text-xs font-semibold text-t-muted uppercase tracking-wide block mb-1">
                      Detection Logic
                    </label>
                    <p className="text-xs text-t-secondary bg-surface-2 rounded-md p-3 font-mono leading-relaxed">
                      {selectedRule.detection_logic}
                    </p>
                  </div>
                )}

                {/* Weight Slider */}
                <div className="mb-4">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide block mb-2">
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
                      className="flex-1 h-2 bg-surface-3 rounded-lg appearance-none cursor-pointer accent-arq-blue-500"
                    />
                    <span className="w-12 text-center text-sm font-mono font-semibold bg-surface-2 text-t-primary rounded-md px-2 py-1">
                      {editWeight.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Enabled Toggle */}
                <div className="mb-4">
                  <label className="text-xs font-semibold text-t-muted uppercase tracking-wide block mb-2">
                    Enabled
                  </label>
                  <button
                    onClick={() => setEditEnabled(!editEnabled)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                      editEnabled
                        ? "bg-arq-blue-500/10 text-arq-blue-400 border border-arq-blue-500/30"
                        : "bg-red-500/10 text-red-400 border border-red-500/30"
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
                    <label className="text-xs font-semibold text-t-muted uppercase tracking-wide block mb-2">
                      Thresholds
                    </label>
                    <div className="border border-white/[0.06] rounded-md p-3 space-y-1 divide-y divide-white/[0.06]">
                      {Object.entries(editThresholds).map(([key, value]) =>
                        renderThresholdInput(key, value, handleThresholdChange)
                      )}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-4 border-t border-white/[0.06]">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm rounded-md font-medium transition-colors",
                      saving
                        ? "bg-arq-blue-500/50 text-white cursor-not-allowed"
                        : "bg-arq-blue-500 text-white hover:bg-arq-blue-600"
                    )}
                  >
                    <Save className="w-4 h-4" />
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 text-sm rounded-md font-medium bg-surface-2 text-t-secondary border border-white/[0.06] hover:bg-surface-3 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Reset to Defaults
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2 text-sm rounded-md font-medium text-t-muted hover:text-t-secondary hover:bg-surface-2 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>

              {/* Stats Section */}
              <div className="glass-card rounded-lg border border-white/[0.06] p-6">
                <h3 className="text-sm font-semibold text-t-muted uppercase tracking-wide mb-4">
                  Rule Statistics
                </h3>
                {statsLoading ? (
                  <p className="text-sm text-t-muted">Loading stats...</p>
                ) : ruleStats ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-t-primary">
                        {ruleStats.times_triggered}
                      </p>
                      <p className="text-xs text-t-muted mt-1">Times Triggered</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-t-primary">
                        {ruleStats.avg_severity.toFixed(2)}
                      </p>
                      <p className="text-xs text-t-muted mt-1">Avg Severity</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-t-primary">
                        {(ruleStats.trigger_rate * 100).toFixed(1)}%
                      </p>
                      <p className="text-xs text-t-muted mt-1">Trigger Rate</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-t-muted">No stats available for this rule.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
