import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { WorkspaceProvider } from "@/lib/workspace-context";
import { NotificationBell } from "@/components/layout/notification-bell";

export const metadata: Metadata = {
  title: "ArqAI FWA Detection & Prevention",
  description: "Fraud, Waste, and Abuse detection for Insurance/TPA",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans flex h-screen overflow-hidden">
        <WorkspaceProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <header className="h-12 border-b border-white/[0.06] bg-surface-1 flex items-center justify-end px-4 shrink-0">
              <NotificationBell />
            </header>
            <main className="flex-1 overflow-y-auto p-6">{children}</main>
          </div>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
