"use client";

import Link from "next/link";
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
} from "lucide-react";
import { useWorkspace } from "@/lib/workspace-context";
import { useState, useRef, useEffect } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/claims", label: "Claims", icon: FileText },
  { href: "/cases", label: "Cases", icon: Flag },
  { href: "/rules", label: "Rules", icon: Settings },
  { href: "/compliance", label: "Compliance", icon: Shield },
  { href: "/governance", label: "AI Governance", icon: Eye },
  { href: "/agents", label: "AI Assistant", icon: Bot },
  { href: "/pipeline", label: "Pipeline", icon: Play },
  { href: "/upload", label: "Upload Data", icon: Upload },
];

export function Sidebar() {
  const pathname = usePathname();
  const { workspaces, activeWorkspace, setActiveWorkspace, loading } = useWorkspace();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const activeWs = workspaces.find((w) => w.workspace_id === activeWorkspace);
  const activeLabel = activeWs ? activeWs.name : "All Workspaces";

  return (
    <aside className="w-64 bg-surface-1 border-r border-white/[0.06] text-t-primary flex flex-col h-screen shrink-0">
      {/* Logo */}
      <div className="p-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-1.5">
          <h1 className="text-lg font-bold tracking-tight text-t-primary">
            Arq
          </h1>
          <span className="text-lg font-bold tracking-tight text-arq-blue-400">
            AI
          </span>
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-arq-lime-400 -mt-2" />
        </div>
        <p className="text-[11px] text-t-muted mt-0.5 tracking-wide">
          FWA Detection &amp; Prevention
        </p>
      </div>

      {/* Workspace Switcher */}
      <div className="px-3 pt-4 pb-2" ref={dropdownRef}>
        <p className="text-[10px] font-medium text-t-muted uppercase tracking-wider px-2 mb-1.5">
          Workspace
        </p>
        <button
          onClick={() => setDropdownOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-2 border border-white/[0.06] hover:bg-surface-3 text-sm transition-colors text-left"
        >
          <Building2 size={14} className="text-t-muted shrink-0" />
          <span className="flex-1 truncate text-t-secondary">
            {loading ? "Loading..." : activeLabel}
          </span>
          <ChevronDown
            size={14}
            className={`text-t-muted transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
          />
        </button>
        {dropdownOpen && !loading && (
          <div className="mt-1 rounded-lg bg-surface-2 border border-white/[0.08] shadow-lg shadow-black/40 py-1 max-h-60 overflow-y-auto z-50">
            <button
              onClick={() => {
                setActiveWorkspace(null);
                setDropdownOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-surface-3 transition-colors ${
                activeWorkspace === null ? "text-arq-lime-400 font-medium" : "text-t-secondary"
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
                className={`w-full text-left px-3 py-2 text-sm hover:bg-surface-3 transition-colors ${
                  activeWorkspace === ws.workspace_id
                    ? "text-arq-lime-400 font-medium"
                    : "text-t-secondary"
                }`}
              >
                <div className="truncate">{ws.name}</div>
                {ws.client_name && (
                  <div className="text-[10px] text-t-muted truncate">
                    {ws.client_name}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 mx-2 px-3 py-2.5 rounded-lg text-sm transition-all ${
                active
                  ? "bg-arq-blue-500/15 text-t-primary border-l-2 border-arq-lime-400 pl-[10px]"
                  : "text-t-muted hover:bg-surface-2 hover:text-t-primary"
              }`}
            >
              <Icon size={18} className={active ? "text-arq-blue-400" : ""} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/[0.06] text-[11px] text-t-muted">
        v0.1.0 &middot; POC
      </div>
    </aside>
  );
}
