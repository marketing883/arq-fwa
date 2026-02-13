import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { WorkspaceProvider } from "@/lib/workspace-context";
import { AppShell } from "@/components/layout/app-shell";

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
        <AuthProvider>
          <WorkspaceProvider>
            <AppShell>{children}</AppShell>
          </WorkspaceProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
