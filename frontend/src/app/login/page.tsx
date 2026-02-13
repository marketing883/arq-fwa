"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import Image from "next/image";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a14]">
      <div className="w-full max-w-[400px] px-6">
        {/* Logo */}
        <div className="flex justify-center mb-10">
          <Image
            src="/logo-white.svg"
            alt="ArqAI"
            width={160}
            height={36}
            className="h-9 w-auto"
            priority
          />
        </div>

        {/* Card */}
        <div className="rounded-[16px] bg-[#12121F] border border-white/[0.08] p-8">
          <h1 className="text-[18px] font-semibold text-white mb-1">Sign in</h1>
          <p className="text-[13px] text-white/40 mb-6">
            FWA Detection & Prevention Platform
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-medium text-white/50 uppercase tracking-wider mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="w-full px-3.5 py-2.5 rounded-[10px] bg-white/[0.05] border border-white/[0.08]
                           text-[14px] text-white placeholder-white/20
                           focus:outline-none focus:border-brand-blue/50 focus:ring-1 focus:ring-brand-blue/20
                           transition-all"
                placeholder="you@thearq.com"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-white/50 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-[10px] bg-white/[0.05] border border-white/[0.08]
                           text-[14px] text-white placeholder-white/20
                           focus:outline-none focus:border-brand-blue/50 focus:ring-1 focus:ring-brand-blue/20
                           transition-all"
                placeholder="Enter password"
              />
            </div>

            {error && (
              <div className="rounded-[8px] bg-red-500/10 border border-red-500/20 px-3.5 py-2.5 text-[13px] text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 rounded-[10px] bg-brand-blue text-white text-[14px] font-medium
                         hover:bg-brand-blue/90 disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200"
            >
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>

        {/* Demo credentials hint */}
        <div className="mt-6 rounded-[12px] bg-white/[0.03] border border-white/[0.05] p-4">
          <p className="text-[11px] text-white/30 font-medium mb-2">Demo accounts</p>
          <div className="space-y-1 text-[11px] text-white/20 font-mono">
            <div>admin@thearq.com / Admin123!</div>
            <div>investigator@thearq.com / Investigator123!</div>
            <div>analyst@thearq.com / Analyst123!</div>
            <div>viewer@thearq.com / Viewer123!</div>
          </div>
        </div>
      </div>
    </div>
  );
}
