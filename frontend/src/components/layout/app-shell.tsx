"use client";

import { useAuth } from "@/lib/auth-context";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const pathname = usePathname();

  // Login page renders standalone (no sidebar)
  if (pathname === "/login") {
    return <>{children}</>;
  }

  // While checking auth, show nothing (avoids flash)
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0a14]">
        <div className="text-white/30 text-sm">Loading...</div>
      </div>
    );
  }

  // Unauthenticated users are redirected by AuthProvider
  if (!isAuthenticated) {
    return null;
  }

  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto px-8 py-6">
          {children}
        </main>
      </div>
    </>
  );
}
