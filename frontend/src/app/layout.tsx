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
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
