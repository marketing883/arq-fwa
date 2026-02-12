"use client";
import { useState, useRef, useEffect } from "react";
import { Bot, Send, User } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const WELCOME_MESSAGE: Message = {
  role: "assistant",
  content:
    "I'm your AI investigation assistant. I can analyze cases, explain fraud patterns, and help with investigations. Note: AI agent integration requires Ollama to be running (Phase 9).",
  timestamp: new Date(),
};

const PLACEHOLDER_RESPONSE =
  "AI agent integration is coming in Phase 9. This will connect to Ollama for local LLM-powered investigation assistance.";

export default function AgentsPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessage: Message = {
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    // Simulate assistant response after 500ms
    setTimeout(() => {
      const assistantMessage: Message = {
        role: "assistant",
        content: PLACEHOLDER_RESPONSE,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
    }, 500);
  }

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

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3 shrink-0 shadow-sm">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-purple-100">
          <Bot className="w-5 h-5 text-purple-600" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900">
            AI Investigation Assistant
          </h1>
          <p className="text-xs text-gray-500">
            Powered by local LLM &middot; Phase 9
          </p>
        </div>
      </div>

      {/* Message Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 bg-gray-50">
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
                  ? "bg-slate-200 text-slate-600"
                  : "bg-blue-500 text-white"
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
              className={`max-w-[70%] ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "assistant"
                    ? "bg-slate-100 text-gray-800 rounded-tl-sm"
                    : "bg-blue-500 text-white rounded-tr-sm"
                }`}
              >
                {msg.content}
              </div>
              <p
                className={`text-xs text-gray-400 mt-1 ${
                  msg.role === "user" ? "text-right" : "text-left"
                }`}
              >
                {formatTime(msg.timestamp)}
              </p>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-full shrink-0 bg-slate-200 text-slate-600">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 px-6 py-4 shrink-0 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a case or fraud pattern..."
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
            disabled={isTyping}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className={`flex items-center justify-center w-10 h-10 rounded-lg transition-colors ${
              !input.trim() || isTyping
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
