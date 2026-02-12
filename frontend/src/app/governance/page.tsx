"use client";

import { useEffect, useState } from "react";
import {
  governance,
  type GovernanceHealth,
  type TrustProfile,
  type HITLRequest,
  type LineageNode,
  type AuditReceiptItem,
  type EvidencePacketSummary,
  type RAGSignalItem,
  type SignalSummaryItem,
  type AdaptationItem,
  type RAGFeedbackItem,
} from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";
import {
  Shield,
  Eye,
  Activity,
  Users,
  GitBranch,
  FileCheck,
  AlertTriangle,
  CheckCircle,
  Clock,
  Zap,
  BarChart3,
  MessageSquare,
  RefreshCw,
} from "lucide-react";

type Tab = "overview" | "tao" | "capc" | "oda-rag";
type TAOSubTab = "trust" | "hitl" | "lineage" | "receipts";
type ODASubTab = "signals" | "adaptations" | "feedback";

function SkeletonBar({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-gray-200", className)} />;
}

function MetricCard({
  label,
  value,
  subtitle,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            {label}
          </p>
          <p className="text-2xl font-bold mt-1 text-gray-900">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
          )}
        </div>
        <div
          className={cn(
            "flex items-center justify-center w-10 h-10 rounded-lg",
            color
          )}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-800",
    denied: "bg-red-100 text-red-800",
    auto_approved: "bg-blue-100 text-blue-800",
  };
  return (
    <span
      className={cn(
        "inline-block px-2 py-0.5 rounded text-xs font-medium",
        colors[status] || "bg-gray-100 text-gray-800"
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

function TrustScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-green-500"
      : pct >= 60
      ? "bg-yellow-500"
      : pct >= 40
      ? "bg-orange-500"
      : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-600 w-10 text-right">
        {pct}%
      </span>
    </div>
  );
}

export default function GovernancePage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [taoSubTab, setTaoSubTab] = useState<TAOSubTab>("trust");
  const [odaSubTab, setOdaSubTab] = useState<ODASubTab>("signals");

  // Data state
  const [health, setHealth] = useState<GovernanceHealth | null>(null);
  const [trustProfiles, setTrustProfiles] = useState<TrustProfile[] | null>(null);
  const [hitlRequests, setHitlRequests] = useState<HITLRequest[] | null>(null);
  const [lineageNodes, setLineageNodes] = useState<LineageNode[] | null>(null);
  const [auditReceipts, setAuditReceipts] = useState<AuditReceiptItem[] | null>(null);
  const [evidencePackets, setEvidencePackets] = useState<EvidencePacketSummary[] | null>(null);
  const [signals, setSignals] = useState<RAGSignalItem[] | null>(null);
  const [signalSummary, setSignalSummary] = useState<SignalSummaryItem[] | null>(null);
  const [adaptations, setAdaptations] = useState<AdaptationItem[] | null>(null);
  const [feedback, setFeedback] = useState<RAGFeedbackItem[] | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Load health data on mount
  useEffect(() => {
    let cancelled = false;
    async function loadHealth() {
      setLoading(true);
      try {
        const data = await governance.health();
        if (!cancelled) setHealth(data);
      } catch (err) {
        console.error("Failed to load governance health:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadHealth();
    return () => { cancelled = true; };
  }, []);

  // Load tab-specific data
  useEffect(() => {
    let cancelled = false;
    async function loadTabData() {
      try {
        if (activeTab === "tao") {
          if (taoSubTab === "trust" && !trustProfiles) {
            const data = await governance.trustProfiles();
            if (!cancelled) setTrustProfiles(data.profiles);
          } else if (taoSubTab === "hitl" && !hitlRequests) {
            const data = await governance.hitlRequests();
            if (!cancelled) setHitlRequests(data.requests);
          } else if (taoSubTab === "lineage" && !lineageNodes) {
            const data = await governance.lineage();
            if (!cancelled) setLineageNodes(data.nodes);
          } else if (taoSubTab === "receipts" && !auditReceipts) {
            const data = await governance.auditReceipts();
            if (!cancelled) setAuditReceipts(data.receipts);
          }
        } else if (activeTab === "capc" && !evidencePackets) {
          const data = await governance.evidencePackets();
          if (!cancelled) setEvidencePackets(data.packets);
        } else if (activeTab === "oda-rag") {
          if (odaSubTab === "signals" && !signalSummary) {
            const [sigData, summData] = await Promise.all([
              governance.signals(),
              governance.signalSummary(),
            ]);
            if (!cancelled) {
              setSignals(sigData.signals);
              setSignalSummary(summData.summary);
            }
          } else if (odaSubTab === "adaptations" && !adaptations) {
            const data = await governance.adaptations();
            if (!cancelled) setAdaptations(data.adaptations);
          } else if (odaSubTab === "feedback" && !feedback) {
            const data = await governance.feedback();
            if (!cancelled) setFeedback(data.feedback);
          }
        }
      } catch (err) {
        console.error("Failed to load tab data:", err);
      }
    }
    loadTabData();
    return () => { cancelled = true; };
  }, [activeTab, taoSubTab, odaSubTab, trustProfiles, hitlRequests, lineageNodes, auditReceipts, evidencePackets, signalSummary, adaptations, feedback]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      // Sync governance data from pipeline results, then reload
      await governance.sync();
      const data = await governance.health();
      setHealth(data);
      // Clear cached tab data so it reloads
      setTrustProfiles(null);
      setHitlRequests(null);
      setLineageNodes(null);
      setAuditReceipts(null);
      setEvidencePackets(null);
      setSignals(null);
      setSignalSummary(null);
      setAdaptations(null);
      setFeedback(null);
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setRefreshing(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "Overview", icon: <Eye size={16} /> },
    { id: "tao", label: "ArqFlow (TAO)", icon: <Shield size={16} /> },
    { id: "capc", label: "ArqGuard (CAPC)", icon: <FileCheck size={16} /> },
    { id: "oda-rag", label: "ArqSight (ODA-RAG)", icon: <Activity size={16} /> },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            AI Governance
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Patent methodology monitoring — ArqFlow, ArqGuard, ArqSight
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            refreshing
              ? "bg-gray-200 text-gray-400 cursor-not-allowed"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          )}
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2",
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Overview Tab ── */}
      {activeTab === "overview" && (
        <OverviewTab health={health} loading={loading} />
      )}

      {/* ── TAO Tab ── */}
      {activeTab === "tao" && (
        <TAOTab
          health={health}
          subTab={taoSubTab}
          setSubTab={setTaoSubTab}
          trustProfiles={trustProfiles}
          hitlRequests={hitlRequests}
          lineageNodes={lineageNodes}
          auditReceipts={auditReceipts}
        />
      )}

      {/* ── CAPC Tab ── */}
      {activeTab === "capc" && (
        <CAPCTab health={health} evidencePackets={evidencePackets} />
      )}

      {/* ── ODA-RAG Tab ── */}
      {activeTab === "oda-rag" && (
        <ODARAGTab
          health={health}
          subTab={odaSubTab}
          setSubTab={setOdaSubTab}
          signals={signals}
          signalSummary={signalSummary}
          adaptations={adaptations}
          feedback={feedback}
        />
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Overview Tab
// ════════════════════════════════════════════════════════════════════════════

function OverviewTab({
  health,
  loading,
}: {
  health: GovernanceHealth | null;
  loading: boolean;
}) {
  if (loading || !health) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
            <SkeletonBar className="h-4 w-24 mb-3" />
            <SkeletonBar className="h-8 w-20" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ArqFlow (TAO) */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Shield size={18} className="text-blue-600" />
          ArqFlow — Trust-Aware Orchestration
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Trust Profiles"
            value={health.tao.trust_profiles}
            subtitle={health.tao.avg_trust_score != null ? `Avg: ${(health.tao.avg_trust_score * 100).toFixed(0)}%` : undefined}
            icon={<Users size={18} className="text-white" />}
            color="bg-blue-500"
          />
          <MetricCard
            label="Lineage Nodes"
            value={health.tao.lineage_nodes}
            subtitle={`${health.tao.lineage_24h} in last 24h`}
            icon={<GitBranch size={18} className="text-white" />}
            color="bg-indigo-500"
          />
          <MetricCard
            label="HITL Queue"
            value={health.tao.hitl_pending}
            subtitle={`${health.tao.hitl_total} total requests`}
            icon={<AlertTriangle size={18} className="text-white" />}
            color={health.tao.hitl_pending > 0 ? "bg-amber-500" : "bg-green-500"}
          />
          <MetricCard
            label="Audit Receipts"
            value={health.tao.audit_receipts}
            subtitle={`${health.tao.tokens_24h} tokens (24h)`}
            icon={<FileCheck size={18} className="text-white" />}
            color="bg-purple-500"
          />
        </div>
      </div>

      {/* ArqGuard (CAPC) */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <FileCheck size={18} className="text-emerald-600" />
          ArqGuard — Compliance-Aware Prompt Compiler
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard
            label="Evidence Packets"
            value={health.capc.evidence_packets}
            subtitle={`${health.capc.evidence_24h} in last 24h`}
            icon={<FileCheck size={18} className="text-white" />}
            color="bg-emerald-500"
          />
          <MetricCard
            label="Policy Violations"
            value={health.capc.policy_violations}
            icon={<AlertTriangle size={18} className="text-white" />}
            color={health.capc.policy_violations > 0 ? "bg-red-500" : "bg-green-500"}
          />
          <MetricCard
            label="Compliance Rate"
            value={
              health.capc.evidence_packets > 0
                ? `${(((health.capc.evidence_packets - health.capc.policy_violations) / health.capc.evidence_packets) * 100).toFixed(1)}%`
                : "N/A"
            }
            icon={<CheckCircle size={18} className="text-white" />}
            color="bg-teal-500"
          />
        </div>
      </div>

      {/* ArqSight (ODA-RAG) */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Activity size={18} className="text-orange-600" />
          ArqSight — Observability-Driven Adaptive RAG
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Signals"
            value={health.oda_rag.signals_total}
            subtitle={`${health.oda_rag.signals_24h} in last 24h`}
            icon={<Activity size={18} className="text-white" />}
            color="bg-orange-500"
          />
          <MetricCard
            label="Adaptations"
            value={health.oda_rag.adaptations}
            icon={<Zap size={18} className="text-white" />}
            color="bg-amber-500"
          />
          <MetricCard
            label="Avg Feedback"
            value={
              health.oda_rag.avg_feedback_quality != null
                ? `${(health.oda_rag.avg_feedback_quality * 100).toFixed(0)}%`
                : "N/A"
            }
            icon={<MessageSquare size={18} className="text-white" />}
            color="bg-cyan-500"
          />
          <MetricCard
            label="System Status"
            value={health.oda_rag.signals_24h > 0 ? "Active" : "Idle"}
            icon={<BarChart3 size={18} className="text-white" />}
            color={health.oda_rag.signals_24h > 0 ? "bg-green-500" : "bg-gray-400"}
          />
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// TAO Tab
// ════════════════════════════════════════════════════════════════════════════

function TAOTab({
  health,
  subTab,
  setSubTab,
  trustProfiles,
  hitlRequests,
  lineageNodes,
  auditReceipts,
}: {
  health: GovernanceHealth | null;
  subTab: TAOSubTab;
  setSubTab: (t: TAOSubTab) => void;
  trustProfiles: TrustProfile[] | null;
  hitlRequests: HITLRequest[] | null;
  lineageNodes: LineageNode[] | null;
  auditReceipts: AuditReceiptItem[] | null;
}) {
  const subTabs: { id: TAOSubTab; label: string }[] = [
    { id: "trust", label: "Trust Profiles" },
    { id: "hitl", label: "HITL Queue" },
    { id: "lineage", label: "Lineage" },
    { id: "receipts", label: "Audit Receipts" },
  ];

  return (
    <div className="space-y-4">
      {/* Sub-tabs */}
      <div className="flex gap-2">
        {subTabs.map((st) => (
          <button
            key={st.id}
            onClick={() => setSubTab(st.id)}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              subTab === st.id
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {st.label}
            {st.id === "hitl" && health && health.tao.hitl_pending > 0 && (
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 text-xs font-bold rounded-full bg-red-500 text-white">
                {health.tao.hitl_pending}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Trust Profiles */}
      {subTab === "trust" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {!trustProfiles ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : trustProfiles.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No agent trust profiles yet. Profiles are created when agents execute actions.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Agent ID</th>
                    <th className="px-4 py-3 font-medium w-48">Trust Score</th>
                    <th className="px-4 py-3 font-medium">Escalation</th>
                    <th className="px-4 py-3 font-medium">Decay Model</th>
                    <th className="px-4 py-3 font-medium">Last Active</th>
                    <th className="px-4 py-3 font-medium text-right">History</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {trustProfiles.map((p) => (
                    <tr key={p.agent_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-900">
                        {p.agent_id}
                      </td>
                      <td className="px-4 py-3">
                        <TrustScoreBar score={p.trust_score} />
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-medium",
                            p.escalation_level === 0
                              ? "bg-green-100 text-green-800"
                              : p.escalation_level <= 2
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-red-100 text-red-800"
                          )}
                        >
                          Level {p.escalation_level}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs">{p.decay_model}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDateTime(p.last_successful_action)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500">
                        {p.history_count} events
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* HITL Requests */}
      {subTab === "hitl" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {!hitlRequests ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : hitlRequests.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No HITL approval requests. High-risk actions will appear here for human review.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Risk</th>
                    <th className="px-4 py-3 font-medium">Trust</th>
                    <th className="px-4 py-3 font-medium">Created</th>
                    <th className="px-4 py-3 font-medium">Reviewer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {hitlRequests.map((r) => (
                    <tr key={r.request_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{r.agent_id}</td>
                      <td className="px-4 py-3 text-gray-700">{r.requested_action}</td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-semibold",
                            r.risk_tier === "critical"
                              ? "bg-red-100 text-red-800"
                              : r.risk_tier === "high"
                              ? "bg-orange-100 text-orange-800"
                              : "bg-yellow-100 text-yellow-800"
                          )}
                        >
                          {r.risk_tier} ({(r.action_risk_score * 100).toFixed(0)})
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs">
                        {(r.agent_trust_score * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDateTime(r.created_at)}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {r.reviewer || "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Lineage */}
      {subTab === "lineage" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {!lineageNodes ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : lineageNodes.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No lineage nodes recorded yet. Agent actions create lineage traces.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Node ID</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Trust</th>
                    <th className="px-4 py-3 font-medium text-right">Duration</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {lineageNodes.map((n) => (
                    <tr key={n.node_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-500">
                        {n.node_id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
                          {n.node_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{n.agent_id || "\u2014"}</td>
                      <td className="px-4 py-3 text-gray-700 text-xs">{n.action}</td>
                      <td className="px-4 py-3 text-gray-600 text-xs">
                        {n.trust_score != null ? `${(n.trust_score * 100).toFixed(0)}%` : "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500 text-xs">
                        {n.duration_ms != null ? `${n.duration_ms}ms` : "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDateTime(n.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Audit Receipts */}
      {subTab === "receipts" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {!auditReceipts ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : auditReceipts.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No audit receipts. Hash-chained receipts are created for each agent action.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Receipt ID</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Risk Score</th>
                    <th className="px-4 py-3 font-medium">Output</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {auditReceipts.map((r) => (
                    <tr key={r.receipt_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-500">
                        {r.receipt_id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3 text-gray-700">{r.action_type}</td>
                      <td className="px-4 py-3 font-mono text-xs">{r.agent_id}</td>
                      <td className="px-4 py-3">
                        {r.action_risk_score != null ? (
                          <span
                            className={cn(
                              "inline-block px-2 py-0.5 rounded text-xs font-semibold",
                              r.action_risk_score > 0.7
                                ? "bg-red-100 text-red-800"
                                : r.action_risk_score > 0.4
                                ? "bg-yellow-100 text-yellow-800"
                                : "bg-green-100 text-green-800"
                            )}
                          >
                            {(r.action_risk_score * 100).toFixed(0)}
                          </span>
                        ) : (
                          "\u2014"
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs max-w-xs truncate">
                        {r.output_summary
                          ? typeof r.output_summary === "string"
                            ? r.output_summary
                            : JSON.stringify(r.output_summary)
                          : "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDateTime(r.timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// CAPC Tab
// ════════════════════════════════════════════════════════════════════════════

function CAPCTab({
  health,
  evidencePackets,
}: {
  health: GovernanceHealth | null;
  evidencePackets: EvidencePacketSummary[] | null;
}) {
  return (
    <div className="space-y-4">
      {/* Summary cards */}
      {health && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricCard
            label="Evidence Packets"
            value={health.capc.evidence_packets}
            subtitle={`${health.capc.evidence_24h} in last 24h`}
            icon={<FileCheck size={18} className="text-white" />}
            color="bg-emerald-500"
          />
          <MetricCard
            label="Policy Violations"
            value={health.capc.policy_violations}
            icon={<AlertTriangle size={18} className="text-white" />}
            color={health.capc.policy_violations > 0 ? "bg-red-500" : "bg-green-500"}
          />
          <MetricCard
            label="Compliance Rate"
            value={
              health.capc.evidence_packets > 0
                ? `${(((health.capc.evidence_packets - health.capc.policy_violations) / health.capc.evidence_packets) * 100).toFixed(1)}%`
                : "N/A"
            }
            icon={<CheckCircle size={18} className="text-white" />}
            color="bg-teal-500"
          />
        </div>
      )}

      {/* Evidence Packets Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-900">Evidence Packets</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Signed evidence bundles for each compiled prompt
          </p>
        </div>
        {!evidencePackets ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonBar key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : evidencePackets.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            No evidence packets. Packets are created when prompts are compiled through ArqGuard.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-gray-600">
                  <th className="px-4 py-3 font-medium">Packet ID</th>
                  <th className="px-4 py-3 font-medium">Request</th>
                  <th className="px-4 py-3 font-medium text-right">Decisions</th>
                  <th className="px-4 py-3 font-medium">Exception</th>
                  <th className="px-4 py-3 font-medium">Hash</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {evidencePackets.map((p) => (
                  <tr key={p.packet_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {p.packet_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3 text-gray-700 text-xs max-w-xs truncate">
                      {p.original_request}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {p.policy_decisions_count}
                    </td>
                    <td className="px-4 py-3">
                      {p.exception_action ? (
                        <span
                          className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-medium",
                            p.exception_action === "ABORT"
                              ? "bg-red-100 text-red-800"
                              : p.exception_action === "REVIEW"
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-orange-100 text-orange-800"
                          )}
                        >
                          {p.exception_action}
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          PASS
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <code className="font-mono text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                        {p.packet_hash}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDateTime(p.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ODA-RAG Tab
// ════════════════════════════════════════════════════════════════════════════

function ODARAGTab({
  health,
  subTab,
  setSubTab,
  signals,
  signalSummary,
  adaptations,
  feedback,
}: {
  health: GovernanceHealth | null;
  subTab: ODASubTab;
  setSubTab: (t: ODASubTab) => void;
  signals: RAGSignalItem[] | null;
  signalSummary: SignalSummaryItem[] | null;
  adaptations: AdaptationItem[] | null;
  feedback: RAGFeedbackItem[] | null;
}) {
  const subTabs: { id: ODASubTab; label: string }[] = [
    { id: "signals", label: "Signals & Drift" },
    { id: "adaptations", label: "Adaptations" },
    { id: "feedback", label: "Feedback" },
  ];

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      {health && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Signals"
            value={health.oda_rag.signals_total}
            subtitle={`${health.oda_rag.signals_24h} in last 24h`}
            icon={<Activity size={18} className="text-white" />}
            color="bg-orange-500"
          />
          <MetricCard
            label="Adaptations"
            value={health.oda_rag.adaptations}
            icon={<Zap size={18} className="text-white" />}
            color="bg-amber-500"
          />
          <MetricCard
            label="Avg Feedback"
            value={
              health.oda_rag.avg_feedback_quality != null
                ? `${(health.oda_rag.avg_feedback_quality * 100).toFixed(0)}%`
                : "N/A"
            }
            icon={<MessageSquare size={18} className="text-white" />}
            color="bg-cyan-500"
          />
          <MetricCard
            label="System Status"
            value={health.oda_rag.signals_24h > 0 ? "Active" : "Idle"}
            icon={<BarChart3 size={18} className="text-white" />}
            color={health.oda_rag.signals_24h > 0 ? "bg-green-500" : "bg-gray-400"}
          />
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-2">
        {subTabs.map((st) => (
          <button
            key={st.id}
            onClick={() => setSubTab(st.id)}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              subTab === st.id
                ? "bg-orange-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {st.label}
          </button>
        ))}
      </div>

      {/* Signals */}
      {subTab === "signals" && (
        <div className="space-y-4">
          {/* Signal Summary Cards */}
          {signalSummary && signalSummary.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {signalSummary.map((s) => (
                <div
                  key={s.signal_type}
                  className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm"
                >
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {s.signal_type.replace(/_/g, " ")}
                  </p>
                  <p className="text-xl font-bold mt-1 text-gray-900">{s.count}</p>
                  <div className="flex gap-4 mt-2 text-xs text-gray-400">
                    <span>avg: {s.avg_value?.toFixed(3) ?? "N/A"}</span>
                    <span>min: {s.min_value?.toFixed(3) ?? "N/A"}</span>
                    <span>max: {s.max_value?.toFixed(3) ?? "N/A"}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Recent Signals Table */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900">Recent Signals</h3>
            </div>
            {!signals ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <SkeletonBar key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : signals.length === 0 ? (
              <div className="p-12 text-center text-gray-400">
                No signals recorded. Signals are collected during RAG queries.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-left text-gray-600">
                      <th className="px-4 py-3 font-medium">Type</th>
                      <th className="px-4 py-3 font-medium">Metric</th>
                      <th className="px-4 py-3 font-medium text-right">Value</th>
                      <th className="px-4 py-3 font-medium">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {signals.slice(0, 50).map((s) => (
                      <tr key={s.signal_id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                            {s.signal_type.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700 text-xs">{s.metric_name}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs">{s.metric_value.toFixed(4)}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(s.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Adaptations */}
      {subTab === "adaptations" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Adaptation Events</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Automatic parameter adjustments in response to drift
            </p>
          </div>
          {!adaptations ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : adaptations.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No adaptations yet. The system adapts RAG parameters when drift is detected.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Drift Score</th>
                    <th className="px-4 py-3 font-medium">Reason</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {adaptations.map((a) => (
                    <tr key={a.event_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                          {a.action_type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {a.drift_score != null ? a.drift_score.toFixed(3) : "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs max-w-md truncate">
                        {a.reason || "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(a.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Feedback */}
      {subTab === "feedback" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">RAG Feedback</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Quality and relevance feedback for the closed-loop learner
            </p>
          </div>
          {!feedback ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBar key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : feedback.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              No feedback recorded. Feedback is collected from RAG query responses.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-600">
                    <th className="px-4 py-3 font-medium">Query</th>
                    <th className="px-4 py-3 font-medium">Quality</th>
                    <th className="px-4 py-3 font-medium">Relevance</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {feedback.map((f) => (
                    <tr key={f.feedback_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-700 text-xs max-w-xs truncate">
                        {f.query}
                      </td>
                      <td className="px-4 py-3">
                        <QualityBadge value={f.response_quality} />
                      </td>
                      <td className="px-4 py-3">
                        {f.relevance_score != null ? (
                          <QualityBadge value={f.relevance_score} />
                        ) : (
                          "\u2014"
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{f.feedback_source}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(f.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function QualityBadge({ value }: { value: number }) {
  const pct = (value * 100).toFixed(0);
  const color =
    value >= 0.8
      ? "bg-green-100 text-green-800"
      : value >= 0.5
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded text-xs font-semibold", color)}>
      {pct}%
    </span>
  );
}
