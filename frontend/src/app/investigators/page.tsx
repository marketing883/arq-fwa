"use client";
import { useEffect, useState } from "react";
import { investigators, type InvestigatorSummary, type AssignmentRuleSummary } from "@/lib/api";

type TabId = "investigators" | "rules";

export default function InvestigatorsPage() {
  const [tab, setTab] = useState<TabId>("investigators");
  const [invList, setInvList] = useState<InvestigatorSummary[]>([]);
  const [rulesList, setRulesList] = useState<AssignmentRuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formSpecialty, setFormSpecialty] = useState("both");
  const [formSeniority, setFormSeniority] = useState("standard");
  const [formMaxCaseload, setFormMaxCaseload] = useState(20);

  // Rule create form state
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [ruleName, setRuleName] = useState("");
  const [ruleDescription, setRuleDescription] = useState("");
  const [rulePriority, setRulePriority] = useState(100);
  const [ruleStrategy, setRuleStrategy] = useState("round_robin");

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([investigators.list(), investigators.rules()])
      .then(([inv, rules]) => {
        setInvList(inv.investigators);
        setRulesList(rules.rules);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  async function handleCreateInvestigator(e: React.FormEvent) {
    e.preventDefault();
    try {
      await investigators.create({
        name: formName,
        email: formEmail || undefined,
        specialty: formSpecialty,
        seniority: formSeniority,
        max_caseload: formMaxCaseload,
      });
      setShowCreate(false);
      setFormName("");
      setFormEmail("");
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleToggleAvailability(inv: InvestigatorSummary) {
    try {
      await investigators.update(inv.investigator_id, {
        is_available: !inv.is_available,
      });
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleCreateRule(e: React.FormEvent) {
    e.preventDefault();
    try {
      await investigators.createRule({
        name: ruleName,
        description: ruleDescription || undefined,
        priority: rulePriority,
        strategy: ruleStrategy,
        conditions: {},
        target_filter: {},
      });
      setShowCreateRule(false);
      setRuleName("");
      setRuleDescription("");
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleToggleRule(rule: AssignmentRuleSummary) {
    try {
      await investigators.updateRule(rule.rule_id, {
        is_enabled: !rule.is_enabled,
      });
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-t-primary">Investigators</h1>
          <p className="text-sm text-t-muted mt-1">
            Manage investigators and case assignment rules
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface-1 rounded-lg p-1 w-fit">
        {(["investigators", "rules"] as TabId[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t
                ? "bg-surface-3 text-t-primary"
                : "text-t-muted hover:text-t-secondary"
            }`}
          >
            {t === "investigators" ? "Investigators" : "Assignment Rules"}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-t-muted text-sm">Loading...</div>
      )}

      {/* Investigators Tab */}
      {!loading && tab === "investigators" && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-4 py-2 bg-arq-blue-500 text-white rounded-lg text-sm font-medium hover:bg-arq-blue-600 transition-colors"
            >
              Add Investigator
            </button>
          </div>

          {showCreate && (
            <form
              onSubmit={handleCreateInvestigator}
              className="mb-6 p-4 bg-surface-1 border border-white/[0.06] rounded-lg grid grid-cols-2 gap-4"
            >
              <input
                placeholder="Name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <input
                placeholder="Email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <select
                value={formSpecialty}
                onChange={(e) => setFormSpecialty(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              >
                <option value="both">Both</option>
                <option value="medical">Medical</option>
                <option value="pharmacy">Pharmacy</option>
              </select>
              <select
                value={formSeniority}
                onChange={(e) => setFormSeniority(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              >
                <option value="junior">Junior</option>
                <option value="standard">Standard</option>
                <option value="senior">Senior</option>
              </select>
              <input
                type="number"
                placeholder="Max Caseload"
                value={formMaxCaseload}
                onChange={(e) => setFormMaxCaseload(Number(e.target.value))}
                min={1}
                max={200}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <div className="flex gap-2">
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

          <div className="bg-surface-1 border border-white/[0.06] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Name</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Specialty</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Seniority</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Caseload</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Utilization</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {invList.map((inv) => (
                  <tr key={inv.investigator_id} className="border-b border-white/[0.04] hover:bg-surface-2/50">
                    <td className="px-4 py-3">
                      <div className="text-t-primary font-medium">{inv.name}</div>
                      {inv.email && <div className="text-t-muted text-xs">{inv.email}</div>}
                    </td>
                    <td className="px-4 py-3 text-t-secondary capitalize">{inv.specialty}</td>
                    <td className="px-4 py-3 text-t-secondary capitalize">{inv.seniority}</td>
                    <td className="px-4 py-3 text-t-secondary">
                      {inv.active_cases} / {inv.max_caseload}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-2 bg-surface-3 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              inv.utilization > 80
                                ? "bg-red-500"
                                : inv.utilization > 60
                                ? "bg-yellow-500"
                                : "bg-arq-lime-500"
                            }`}
                            style={{ width: `${Math.min(inv.utilization, 100)}%` }}
                          />
                        </div>
                        <span className="text-t-muted text-xs">{inv.utilization}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleAvailability(inv)}
                        className={`px-3 py-1 rounded-full text-xs font-medium ${
                          inv.is_available
                            ? "bg-arq-lime-500/20 text-arq-lime-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {inv.is_available ? "Available" : "Unavailable"}
                      </button>
                    </td>
                  </tr>
                ))}
                {invList.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-t-muted">
                      No investigators yet. Add one to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Rules Tab */}
      {!loading && tab === "rules" && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setShowCreateRule(!showCreateRule)}
              className="px-4 py-2 bg-arq-blue-500 text-white rounded-lg text-sm font-medium hover:bg-arq-blue-600 transition-colors"
            >
              Add Rule
            </button>
          </div>

          {showCreateRule && (
            <form
              onSubmit={handleCreateRule}
              className="mb-6 p-4 bg-surface-1 border border-white/[0.06] rounded-lg grid grid-cols-2 gap-4"
            >
              <input
                placeholder="Rule Name"
                value={ruleName}
                onChange={(e) => setRuleName(e.target.value)}
                required
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <input
                placeholder="Description"
                value={ruleDescription}
                onChange={(e) => setRuleDescription(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <input
                type="number"
                placeholder="Priority (lower = higher)"
                value={rulePriority}
                onChange={(e) => setRulePriority(Number(e.target.value))}
                min={1}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              />
              <select
                value={ruleStrategy}
                onChange={(e) => setRuleStrategy(e.target.value)}
                className="bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-t-primary"
              >
                <option value="round_robin">Round Robin</option>
                <option value="workload_balanced">Workload Balanced</option>
                <option value="skill_matched">Skill Matched</option>
              </select>
              <div className="flex gap-2 col-span-2">
                <button
                  type="submit"
                  className="px-4 py-2 bg-arq-lime-500 text-black rounded-lg text-sm font-medium hover:bg-arq-lime-400 transition-colors"
                >
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateRule(false)}
                  className="px-4 py-2 bg-surface-2 text-t-muted rounded-lg text-sm hover:bg-surface-3 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          <div className="bg-surface-1 border border-white/[0.06] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Priority</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Name</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Strategy</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Conditions</th>
                  <th className="px-4 py-3 text-left text-t-muted font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rulesList.map((rule) => (
                  <tr key={rule.rule_id} className="border-b border-white/[0.04] hover:bg-surface-2/50">
                    <td className="px-4 py-3 text-t-primary font-mono">{rule.priority}</td>
                    <td className="px-4 py-3">
                      <div className="text-t-primary font-medium">{rule.name}</div>
                      {rule.description && (
                        <div className="text-t-muted text-xs">{rule.description}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-t-secondary">
                      {rule.strategy.replace("_", " ")}
                    </td>
                    <td className="px-4 py-3 text-t-muted text-xs font-mono">
                      {Object.keys(rule.conditions).length > 0
                        ? JSON.stringify(rule.conditions)
                        : "Catch-all"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleRule(rule)}
                        className={`px-3 py-1 rounded-full text-xs font-medium ${
                          rule.is_enabled
                            ? "bg-arq-lime-500/20 text-arq-lime-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {rule.is_enabled ? "Enabled" : "Disabled"}
                      </button>
                    </td>
                  </tr>
                ))}
                {rulesList.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-t-muted">
                      No assignment rules. Add one to enable auto-assignment.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
