"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Bot,
  Send,
  User,
  Search,
  AlertTriangle,
  CheckCircle,
  Loader2,
  X,
} from "lucide-react";
import { useWorkspace } from "@/lib/workspace-context";
import {
  agents,
  cases as casesApi,
  CaseSummary,
  InvestigateResponse,
  AgentStatus,
  AgentChatResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* -------------------------------------------------------------------------- */
/*  Prose overrides – compact spacing for chat bubbles                        */
/* -------------------------------------------------------------------------- */

const markdownClasses = [
  "prose prose-sm prose-invert max-w-none text-t-secondary",
  "prose-headings:font-semibold prose-headings:text-t-primary",
  "prose-h1:text-base prose-h2:text-[0.9rem] prose-h3:text-sm",
  "prose-headings:mt-3 prose-headings:mb-1 first:prose-headings:mt-0",
  "prose-p:my-1.5 prose-p:leading-relaxed",
  "prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5",
  "prose-code:before:content-none prose-code:after:content-none",
  "prose-code:bg-surface-3 prose-code:rounded prose-code:px-1 prose-code:py-0.5",
  "prose-code:text-arq-lime-400 prose-code:text-xs prose-code:font-medium",
  "prose-pre:bg-surface-0 prose-pre:text-t-secondary prose-pre:rounded-lg prose-pre:my-2",
  "prose-pre:text-xs prose-pre:leading-relaxed",
  "prose-table:my-2 prose-table:text-xs prose-table:w-full prose-table:border-collapse",
  "prose-table:border prose-table:border-white/[0.06] prose-table:rounded-lg",
  "prose-thead:bg-surface-2/60",
  "prose-th:text-left prose-th:px-2.5 prose-th:py-1.5 prose-th:font-semibold prose-th:text-t-muted",
  "prose-th:border prose-th:border-white/[0.06] prose-th:text-[11px] prose-th:uppercase prose-th:tracking-wide",
  "prose-td:px-2.5 prose-td:py-1.5 prose-td:border prose-td:border-white/[0.06] prose-td:text-t-secondary",
  "prose-td:whitespace-nowrap",
  "prose-blockquote:border-arq-blue-400 prose-blockquote:text-t-muted prose-blockquote:my-2 prose-blockquote:not-italic",
  "prose-hr:my-3 prose-hr:border-white/[0.06]",
  "prose-a:text-arq-blue-400 prose-a:underline",
  "prose-strong:text-t-primary prose-strong:font-semibold",
].join(" ");

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  model?: string;
  sources?: string[];
  confidence?: string;
  investigation?: InvestigateResponse;
}

/* -------------------------------------------------------------------------- */
/*  Investigation card (rendered inside assistant message)                     */
/* -------------------------------------------------------------------------- */

function InvestigationCard({ data }: { data: InvestigateResponse }) {
  return (
    <div className="mt-3 space-y-3">
      {/* Summary */}
      <div className="rounded-lg bg-surface-2/80 border border-white/[0.06] p-3">
        <h4 className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-1">
          Summary
        </h4>
        <p className="text-sm text-t-primary leading-relaxed">{data.summary}</p>
      </div>

      {/* Findings */}
      {data.findings.length > 0 && (
        <div className="rounded-lg bg-surface-2/80 border border-white/[0.06] p-3">
          <h4 className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-2">
            Findings
          </h4>
          <ul className="space-y-1.5">
            {data.findings.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-t-secondary">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 mt-0.5 shrink-0" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Risk Assessment */}
      {data.risk_assessment && (
        <div className="rounded-lg bg-surface-2/80 border border-white/[0.06] p-3">
          <h4 className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-1">
            Risk Assessment
          </h4>
          <p className="text-sm text-t-primary leading-relaxed">
            {data.risk_assessment}
          </p>
        </div>
      )}

      {/* Recommended Actions */}
      {data.recommended_actions.length > 0 && (
        <div className="rounded-lg bg-surface-2/80 border border-white/[0.06] p-3">
          <h4 className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-2">
            Recommended Actions
          </h4>
          <ul className="space-y-1.5">
            {data.recommended_actions.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-t-secondary">
                <CheckCircle className="h-3.5 w-3.5 text-green-400 mt-0.5 shrink-0" />
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence & Model */}
      <div className="flex items-center gap-4 text-xs text-t-muted">
        <span>
          Confidence:{" "}
          <span
            className={cn(
              "font-medium",
              data.confidence >= 0.7
                ? "text-green-400"
                : data.confidence >= 0.4
                  ? "text-amber-400"
                  : "text-red-400",
            )}
          >
            {(data.confidence * 100).toFixed(0)}%
          </span>
        </span>
        <span>Model: {data.model_used}</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Main page                                                                 */
/* -------------------------------------------------------------------------- */

export default function AgentsPage() {
  const { activeWorkspace } = useWorkspace();

  // Chat state
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "I'm your AI investigation assistant. I can analyze cases, explain fraud patterns, and help with investigations. Select a case above to scope the conversation, or just ask a general question.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Agent status
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);

  // Session state — persist across tab switches
  const STORAGE_KEY = "arq_chat_session_id";
  const [sessionId, setSessionId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY);
    }
    return null;
  });
  const [restoringSession, setRestoringSession] = useState(false);

  // Case selector state
  const [caseList, setCaseList] = useState<CaseSummary[]>([]);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [caseSearch, setCaseSearch] = useState("");
  const [showCaseDropdown, setShowCaseDropdown] = useState(false);
  const [loadingCases, setLoadingCases] = useState(false);

  // Restore chat history from backend on mount
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setRestoringSession(true);
    agents
      .sessionMessages(sessionId, 100)
      .then((data) => {
        if (cancelled || !data.messages || data.messages.length === 0) return;
        const restored: Message[] = data.messages.map((m) => ({
          role: m.role,
          content: m.content,
          timestamp: m.created_at ? new Date(m.created_at) : new Date(),
          model: m.model_used ?? undefined,
          sources: m.sources_cited ?? undefined,
          confidence: m.confidence ?? undefined,
        }));
        setMessages(restored);
      })
      .catch(() => {
        // Session expired or invalid — clear it
        localStorage.removeItem(STORAGE_KEY);
        setSessionId(null);
      })
      .finally(() => {
        if (!cancelled) setRestoringSession(false);
      });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Poll agent status
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const s = await agents.status();
        if (!cancelled) setAgentStatus(s);
      } catch {
        if (!cancelled) setAgentStatus(null);
      }
    }
    poll();
    const interval = setInterval(poll, 15_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Load cases for selector
  useEffect(() => {
    let cancelled = false;
    setLoadingCases(true);
    casesApi
      .list({ page: 1, size: 100, workspace_id: activeWorkspace })
      .then((res) => {
        if (!cancelled) setCaseList(res.items);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingCases(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace]);

  // Filtered case list
  const filteredCases = caseSearch
    ? caseList.filter(
        (c) =>
          c.case_id.toLowerCase().includes(caseSearch.toLowerCase()) ||
          c.claim_id.toLowerCase().includes(caseSearch.toLowerCase()),
      )
    : caseList;

  /* ─── Send message ─── */

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isTyping) return;

    const userMessage: Message = {
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const result = await agents.chat(trimmed, selectedCase, sessionId, activeWorkspace);

      // Track session from first response — persist for tab switches
      if (result.session_id && !sessionId) {
        setSessionId(result.session_id);
        localStorage.setItem(STORAGE_KEY, result.session_id);
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: result.response,
        timestamp: new Date(),
        model: result.model_used,
        sources: result.sources_cited,
        confidence: result.confidence,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMsg: Message = {
        role: "assistant",
        content: `Failed to get response: ${err instanceof Error ? err.message : "Unknown error"}. Make sure the backend is running.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  }, [input, isTyping, selectedCase, sessionId, activeWorkspace]);

  /* ─── Investigate case ─── */

  const handleInvestigate = useCallback(async () => {
    if (!selectedCase || isTyping) return;

    const userMessage: Message = {
      role: "user",
      content: `Investigate case ${selectedCase}`,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const result = await agents.investigate(selectedCase, undefined, activeWorkspace);

      const assistantMessage: Message = {
        role: "assistant",
        content: result.summary,
        timestamp: new Date(),
        model: result.model_used,
        investigation: result,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMsg: Message = {
        role: "assistant",
        content: `Investigation failed: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  }, [selectedCase, isTyping]);

  /* ─── Key handler ─── */

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function formatTime(date: Date): string {
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const selectedCaseData = caseList.find((c) => c.case_id === selectedCase);

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* Header */}
      <div className="bg-surface-1 border-b border-white/[0.06] px-6 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-arq-blue-500/20">
              <Bot className="w-5 h-5 text-arq-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-t-primary">
                AI Investigation Assistant
              </h1>
              <div className="flex items-center gap-2 mt-0.5">
                {agentStatus?.mode === "slm" ? (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-green-400" />
                    <p className="text-xs text-t-muted">
                      Powered by <span className="font-medium text-t-secondary">{agentStatus.model}</span> (local SLM)
                    </p>
                  </>
                ) : agentStatus?.status === "loading" ? (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                    <p className="text-xs text-amber-400">
                      Model downloading&hellip; using data engine in the meantime
                    </p>
                  </>
                ) : (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-arq-blue-500" />
                    <p className="text-xs text-t-muted">
                      Data-driven analysis engine
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Case selector */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={() => setShowCaseDropdown(!showCaseDropdown)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                  selectedCase
                    ? "border-arq-blue-500/20 bg-arq-blue-900/30 text-arq-blue-400"
                    : "border-white/[0.06] bg-surface-2 text-t-secondary hover:bg-surface-2/40",
                )}
              >
                <Search className="h-3.5 w-3.5" />
                {selectedCase ? (
                  <span className="font-mono text-xs">{selectedCase}</span>
                ) : (
                  <span>Select Case</span>
                )}
              </button>

              {selectedCase && (
                <button
                  onClick={() => {
                    setSelectedCase(null);
                    setShowCaseDropdown(false);
                  }}
                  className="ml-1 inline-flex items-center justify-center w-6 h-6 rounded text-t-muted hover:text-t-secondary hover:bg-surface-2"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}

              {showCaseDropdown && (
                <div className="absolute right-0 top-full mt-1 z-50 w-80 rounded-lg border border-white/[0.08] bg-surface-2 shadow-lg">
                  <div className="p-2 border-b border-white/[0.06]">
                    <input
                      type="text"
                      value={caseSearch}
                      onChange={(e) => setCaseSearch(e.target.value)}
                      placeholder="Search cases..."
                      className="w-full rounded-md border border-surface-3 bg-surface-3 px-3 py-1.5 text-sm text-t-primary focus:border-arq-blue-400 focus:outline-none"
                      autoFocus
                    />
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {loadingCases ? (
                      <div className="flex items-center justify-center py-4 text-sm text-t-muted">
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Loading cases...
                      </div>
                    ) : filteredCases.length === 0 ? (
                      <div className="py-4 text-center text-sm text-t-muted">
                        No cases found
                      </div>
                    ) : (
                      filteredCases.map((c) => (
                        <button
                          key={c.case_id}
                          onClick={() => {
                            setSelectedCase(c.case_id);
                            setShowCaseDropdown(false);
                            setCaseSearch("");
                          }}
                          className={cn(
                            "w-full px-3 py-2 text-left text-sm hover:bg-surface-2/40 flex items-center justify-between",
                            selectedCase === c.case_id && "bg-arq-blue-900/30",
                          )}
                        >
                          <div>
                            <span className="font-mono text-xs text-t-primary">
                              {c.case_id}
                            </span>
                            <span className="ml-2 text-xs text-t-muted">
                              {c.claim_id}
                            </span>
                          </div>
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-medium",
                              c.risk_level === "critical"
                                ? "bg-red-500/20 text-red-400"
                                : c.risk_level === "high"
                                  ? "bg-orange-500/20 text-orange-400"
                                  : c.risk_level === "medium"
                                    ? "bg-amber-500/20 text-amber-400"
                                    : "bg-green-500/20 text-green-400",
                            )}
                          >
                            {c.risk_level}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Investigate button */}
            {selectedCase && (
              <button
                onClick={handleInvestigate}
                disabled={isTyping}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-white transition-colors",
                  isTyping
                    ? "bg-arq-blue-500/60 cursor-not-allowed"
                    : "bg-arq-blue-500 hover:bg-arq-blue-600",
                )}
              >
                {isTyping ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Bot className="h-3.5 w-3.5" />
                )}
                Investigate
              </button>
            )}
          </div>
        </div>

        {/* Selected case banner */}
        {selectedCaseData && (
          <div className="mt-2 flex items-center gap-3 rounded-md bg-arq-blue-900/30 border border-arq-blue-500/20 px-3 py-1.5 text-xs">
            <span className="text-arq-blue-400 font-medium">
              Scoped to: {selectedCaseData.case_id}
            </span>
            <span className="text-t-muted">|</span>
            <span className="text-t-muted">
              Claim: {selectedCaseData.claim_id}
            </span>
            <span className="text-t-muted">|</span>
            <span
              className={cn(
                "font-medium",
                selectedCaseData.risk_level === "critical"
                  ? "text-red-400"
                  : selectedCaseData.risk_level === "high"
                    ? "text-orange-400"
                    : "text-amber-400",
              )}
            >
              Risk: {selectedCaseData.risk_score.toFixed(0)} (
              {selectedCaseData.risk_level})
            </span>
            <span className="text-t-muted">|</span>
            <span className="text-t-muted">
              Status: {selectedCaseData.status}
            </span>
          </div>
        )}
      </div>

      {/* Message Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 bg-surface-0">
        {restoringSession && (
          <div className="flex items-center justify-center py-4 text-sm text-t-muted">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Restoring previous conversation...
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-3 ${
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            }`}
          >
            {/* Avatar */}
            <div
              className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 ${
                msg.role === "assistant"
                  ? "bg-surface-2 text-t-muted"
                  : "bg-arq-blue-500 text-white"
              }`}
            >
              {msg.role === "assistant" ? (
                <Bot className="w-4 h-4" />
              ) : (
                <User className="w-4 h-4" />
              )}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[75%] ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={cn(
                  "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  msg.role === "assistant"
                    ? "bg-surface-2 text-t-primary rounded-tl-sm"
                    : "bg-arq-blue-500 text-white rounded-tr-sm",
                )}
              >
                {msg.role === "assistant" ? (
                  <div className={markdownClasses}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        table: ({ children, ...props }) => (
                          <div className="overflow-x-auto my-2 rounded-lg border border-white/[0.06]">
                            <table {...props} className="min-w-full text-xs border-collapse">
                              {children}
                            </table>
                          </div>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <span className="whitespace-pre-wrap">{msg.content}</span>
                )}

                {/* Investigation card */}
                {msg.investigation && (
                  <InvestigationCard data={msg.investigation} />
                )}
              </div>

              {/* Meta info */}
              <div
                className={`flex items-center gap-2 mt-1 ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <p className="text-xs text-t-muted">
                  {formatTime(msg.timestamp)}
                </p>
                {msg.model && (
                  <span className="text-[10px] text-t-muted font-mono">
                    {msg.model}
                  </span>
                )}
                {msg.confidence && (
                  <span
                    className={cn(
                      "text-[10px] font-medium",
                      msg.confidence === "high"
                        ? "text-green-400"
                        : msg.confidence === "medium"
                          ? "text-amber-400"
                          : "text-red-400",
                    )}
                  >
                    {msg.confidence} confidence
                  </span>
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <span className="text-[10px] text-arq-blue-400">
                    {msg.sources.length} source
                    {msg.sources.length !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-full shrink-0 bg-surface-2 text-t-muted">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-surface-2 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-t-muted rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-t-muted rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-t-muted rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-surface-1 border-t border-white/[0.06] px-6 py-4 shrink-0">
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedCase
                ? `Ask about ${selectedCase}...`
                : "Ask about a case or fraud pattern..."
            }
            className="flex-1 rounded-lg border border-surface-3 bg-surface-2 px-4 py-2.5 text-sm text-t-primary placeholder-t-muted focus:border-arq-blue-400 focus:ring-1 focus:ring-arq-blue-400/30 outline-none transition-colors"
            disabled={isTyping}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className={`flex items-center justify-center w-10 h-10 rounded-lg transition-colors ${
              !input.trim() || isTyping
                ? "bg-surface-2 text-t-muted cursor-not-allowed"
                : "bg-arq-blue-500 text-white hover:bg-arq-blue-600"
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
