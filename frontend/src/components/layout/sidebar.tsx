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
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/claims", label: "Claims", icon: FileText },
  { href: "/cases", label: "Cases", icon: Flag },
  { href: "/rules", label: "Rules", icon: Settings },
  { href: "/compliance", label: "Compliance", icon: Shield },
  { href: "/agents", label: "AI Assistant", icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen shrink-0">
      <div className="p-5 border-b border-gray-700">
        <h1 className="text-lg font-bold tracking-tight">ArqAI</h1>
        <p className="text-xs text-gray-400 mt-0.5">
          FWA Detection &amp; Prevention
        </p>
      </div>
      <nav className="flex-1 py-4">
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
