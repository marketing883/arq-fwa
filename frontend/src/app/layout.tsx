import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { WorkspaceProvider } from "@/lib/workspace-context";

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
      <body className="flex h-screen overflow-hidden">
        <WorkspaceProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <main className="flex-1 overflow-y-auto px-8 py-6">
              {children}
            </main>
          </div>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
