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
        <label className="text-sm text-gray-700 font-medium">{key}</label>
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(key, e.target.checked)}
          className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
        />
      </div>
    );
  }
  if (typeof value === "number") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-gray-700 font-medium">{key}</label>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(key, parseFloat(e.target.value) || 0)}
          step="any"
          className="w-32 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-right"
        />
      </div>
    );
  }
  if (typeof value === "string") {
    return (
      <div key={key} className="flex items-center justify-between gap-4 py-2">
        <label className="text-sm text-gray-700 font-medium">{key}</label>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(key, e.target.value)}
          className="w-48 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
    );
  }
  // Nested object / array: JSON textarea
  return (
    <div key={key} className="py-2">
      <label className="text-sm text-gray-700 font-medium block mb-1">{key}</label>
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
        className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
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
        <Settings className="w-6 h-6 text-gray-500" />
        Rule Configuration
      </h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===== LEFT PANEL: Rules List ===== */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-gray-200">
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
                    ? "border-b-2 border-blue-600 text-blue-600 bg-blue-50/50"
                    : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Rules table */}
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading rules...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-2.5 font-semibold text-gray-600">Rule ID</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-gray-600">Category</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-gray-600">Fraud Type</th>
                    <th className="text-right px-4 py-2.5 font-semibold text-gray-600">Weight</th>
                    <th className="text-center px-4 py-2.5 font-semibold text-gray-600">Enabled</th>
                    <th className="text-center px-4 py-2.5 font-semibold text-gray-600">Edit</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRules.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                        No rules found for {activeTab} claims.
                      </td>
                    </tr>
                  ) : (
                    filteredRules.map((rule) => (
                      <tr
                        key={rule.rule_id}
                        className={cn(
                          "border-b border-gray-100 transition-colors",
                          selectedRuleId === rule.rule_id
                            ? "bg-blue-50"
                            : "hover:bg-gray-50"
                        )}
                      >
                        <td className="px-4 py-2.5 font-mono text-xs">{rule.rule_id}</td>
                        <td className="px-4 py-2.5 text-gray-700 capitalize">{rule.category}</td>
                        <td className="px-4 py-2.5 text-gray-700 capitalize">
                          {rule.fraud_type.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono">{rule.weight.toFixed(1)}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span
                            className={cn(
                              "inline-block w-3 h-3 rounded-full",
                              rule.enabled ? "bg-green-500" : "bg-red-400"
                            )}
                            title={rule.enabled ? "Enabled" : "Disabled"}
                          />
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button
                            onClick={() => selectRule(rule)}
                            className="text-blue-600 hover:text-blue-800 text-xs font-medium hover:underline"
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
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8 text-center">
              <Settings className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">Select a rule from the list to configure it.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Rule Config Card */}
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
                {/* Header */}
                <div className="mb-6">
                  <h2 className="text-lg font-semibold font-mono">{selectedRule.rule_id}</h2>
                  <p className="text-sm text-gray-500 capitalize">{selectedRule.category}</p>
                </div>

                {/* Description */}
                {selectedRule.description && (
                  <div className="mb-4">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">
                      Description
                    </label>
                    <p className="text-sm text-gray-700 bg-gray-50 rounded-md p-3">
                      {selectedRule.description}
                    </p>
                  </div>
                )}

                {/* Detection Logic */}
                {selectedRule.detection_logic && (
                  <div className="mb-4">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">
                      Detection Logic
                    </label>
                    <p className="text-xs text-gray-600 bg-gray-50 rounded-md p-3 font-mono leading-relaxed">
                      {selectedRule.detection_logic}
                    </p>
                  </div>
                )}

                {/* Weight Slider */}
                <div className="mb-4">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-2">
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
                      className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <span className="w-12 text-center text-sm font-mono font-semibold bg-gray-100 rounded-md px-2 py-1">
                      {editWeight.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Enabled Toggle */}
                <div className="mb-4">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-2">
                    Enabled
                  </label>
                  <button
                    onClick={() => setEditEnabled(!editEnabled)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                      editEnabled
                        ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-red-50 text-red-700 border border-red-200"
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
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-2">
                      Thresholds
                    </label>
                    <div className="border border-gray-200 rounded-md p-3 space-y-1 divide-y divide-gray-100">
                      {Object.entries(editThresholds).map(([key, value]) =>
                        renderThresholdInput(key, value, handleThresholdChange)
                      )}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm rounded-md font-medium transition-colors",
                      saving
                        ? "bg-blue-400 text-white cursor-not-allowed"
                        : "bg-blue-600 text-white hover:bg-blue-700"
                    )}
                  >
                    <Save className="w-4 h-4" />
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 text-sm rounded-md font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Reset to Defaults
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2 text-sm rounded-md font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>

              {/* Stats Section */}
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
                  Rule Statistics
                </h3>
                {statsLoading ? (
                  <p className="text-sm text-gray-500">Loading stats...</p>
                ) : ruleStats ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-gray-900">
                        {ruleStats.times_triggered}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">Times Triggered</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-gray-900">
                        {ruleStats.avg_severity.toFixed(2)}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">Avg Severity</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-gray-900">
                        {(ruleStats.trigger_rate * 100).toFixed(1)}%
                      </p>
                      <p className="text-xs text-gray-500 mt-1">Trigger Rate</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No stats available for this rule.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
