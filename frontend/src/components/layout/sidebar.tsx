"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Flag,
  Settings,
  Shield,
  Bot,
  Upload,
  ChevronDown,
  Building2,
  Play,
  Eye,
  MessageSquare,
} from "lucide-react";
import { useWorkspace } from "@/lib/workspace-context";
import { useState, useRef, useEffect } from "react";

const navGroups = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/claims", label: "Claims", icon: FileText },
      { href: "/cases", label: "Cases", icon: Flag },
    ],
  },
  {
    label: "Investigation",
    items: [
      { href: "/rules", label: "Rules", icon: Settings },
      { href: "/pipeline", label: "Pipeline", icon: Play },
      { href: "/agents", label: "AI Assistant", icon: MessageSquare },
    ],
  },
  {
    label: "Compliance",
    items: [
      { href: "/compliance", label: "Audit Trail", icon: Shield },
      { href: "/governance", label: "AI Governance", icon: Eye },
      { href: "/upload", label: "Upload", icon: Upload },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { workspaces, activeWorkspace, setActiveWorkspace, loading } =
    useWorkspace();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const activeWs = workspaces.find((w) => w.workspace_id === activeWorkspace);
  const activeLabel = activeWs ? activeWs.name : "All Workspaces";

  return (
    <aside className="w-[252px] bg-surface-sidebar flex flex-col h-screen shrink-0 relative z-10">
      {/* Right edge glow */}
      <div
        className="absolute top-0 right-0 w-px h-full pointer-events-none"
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%)",
        }}
      />

      {/* Brand */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-3">
          <Image
            src="/logo-white.svg"
            alt="ArqAI"
            width={140}
            height={32}
            className="h-8 w-auto"
            priority
          />
        </div>
      </div>

      {/* Workspace Switcher */}
      <div className="px-3 mb-2" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen((o) => !o)}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[12px] text-[12.5px] font-medium
                     bg-white/[0.04] border border-white/[0.07] text-white/70
                     hover:bg-white/[0.06] hover:border-white/10
                     transition-all duration-200"
        >
          <span className="w-[7px] h-[7px] rounded-full bg-brand-lime shrink-0" style={{ boxShadow: '0 0 6px rgba(200,230,22,0.4)' }} />
          <span className="flex-1 truncate text-left">
            {loading ? "Loading\u2026" : activeLabel}
          </span>
          <ChevronDown
            size={12}
            className={`text-white/35 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`}
          />
        </button>
        {dropdownOpen && !loading && (
          <div className="mt-1.5 rounded-[12px] bg-[#12121F] border border-white/[0.08] shadow-lg py-1 max-h-60 overflow-y-auto z-50">
            <button
              onClick={() => {
                setActiveWorkspace(null);
                setDropdownOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-[12.5px] hover:bg-white/[0.06] transition-colors ${
                activeWorkspace === null
                  ? "text-brand-blue font-medium"
                  : "text-white/50"
              }`}
            >
              All Workspaces
            </button>
            {workspaces.map((ws) => (
              <button
                key={ws.workspace_id}
                onClick={() => {
                  setActiveWorkspace(ws.workspace_id);
                  setDropdownOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-[12.5px] hover:bg-white/[0.06] transition-colors ${
                  activeWorkspace === ws.workspace_id
                    ? "text-brand-blue font-medium"
                    : "text-white/50"
                }`}
              >
                <div className="truncate">{ws.name}</div>
                {ws.client_name && (
                  <div className="text-[10px] text-white/25 truncate">
                    {ws.client_name}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-1">
        {navGroups.map((group) => (
          <div key={group.label} className="px-3 mb-1">
            <div className="text-[10px] font-semibold text-white/20 uppercase tracking-[0.1em] px-3 pt-4 pb-1.5">
              {group.label}
            </div>
            {group.items.map(({ href, label, icon: Icon }) => {
              const active =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-[8px] text-[13px] mb-px relative
                    transition-all duration-[180ms] ${
                      active
                        ? "text-white bg-white/[0.09]"
                        : "text-white/45 hover:text-white/75 hover:bg-white/[0.06]"
                    }`}
                  style={{ fontWeight: active ? 500 : 430 }}
                >
                  {active && (
                    <span
                      className="absolute -left-3 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-brand-lime"
                      style={{
                        boxShadow: "0 0 8px rgba(200,230,22,0.3)",
                      }}
                    />
                  )}
                  <Icon
                    size={17}
                    strokeWidth={1.7}
                    className={`shrink-0 transition-opacity duration-[180ms] ${
                      active ? "opacity-90" : "opacity-50"
                    }`}
                  />
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3">
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-[8px] bg-white/[0.04] border border-white/[0.07]">
          <span
            className="w-1.5 h-1.5 rounded-full bg-brand-lime animate-glow"
          />
          <span className="text-[11px] text-white/40" style={{ fontWeight: 430 }}>
            All systems operational
          </span>
        </div>
        <div className="text-[10px] text-white/15 px-3 pt-2" style={{ fontWeight: 430 }}>
          v1.0 &middot; ArqAI Inc.
        </div>
      </div>
    </aside>
  );
}
