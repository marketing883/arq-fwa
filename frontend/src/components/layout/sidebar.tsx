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

  // Close dropdown on outside click
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
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen shrink-0">
      <div className="p-5 border-b border-gray-700">
        <h1 className="text-lg font-bold tracking-tight">ArqAI</h1>
        <p className="text-xs text-gray-400 mt-0.5">
          FWA Detection &amp; Prevention
        </p>
      </div>

      {/* Workspace Switcher */}
      <div className="px-3 pt-4 pb-2" ref={dropdownRef}>
        <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider px-2 mb-1.5">
          Workspace
        </p>
        <button
          onClick={() => setDropdownOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-gray-800 hover:bg-gray-750 text-sm transition-colors text-left"
        >
          <Building2 size={14} className="text-gray-400 shrink-0" />
          <span className="flex-1 truncate text-gray-200">
            {loading ? "Loading..." : activeLabel}
          </span>
          <ChevronDown
            size={14}
            className={`text-gray-500 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
          />
        </button>
        {dropdownOpen && !loading && (
          <div className="mt-1 rounded-md bg-gray-800 border border-gray-700 shadow-lg py-1 max-h-60 overflow-y-auto z-50">
            <button
              onClick={() => {
                setActiveWorkspace(null);
                setDropdownOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-700 transition-colors ${
                activeWorkspace === null ? "text-blue-400 font-medium" : "text-gray-300"
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
                className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-700 transition-colors ${
                  activeWorkspace === ws.workspace_id
                    ? "text-blue-400 font-medium"
                    : "text-gray-300"
                }`}
              >
                <div className="truncate">{ws.name}</div>
                {ws.client_name && (
                  <div className="text-[10px] text-gray-500 truncate">
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
              className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-primary-700 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
        v0.1.0 &middot; POC
      </div>
    </aside>
  );
}
