/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Proxy every API prefix to the FastAPI backend EXCEPT /api/agents/*.
    // Agent endpoints are served by a Next.js API route handler
    // (src/app/api/agents/[...path]/route.ts) that proxies with a 180 s
    // timeout — the default rewrite proxy times out after ~30 s which is
    // too short for Ollama LLM inference.
    const backend = "http://backend:8000";
    const segments = [
      "health",
      "dashboard",
      "claims",
      "rules",
      "cases",
      "audit",
      "scoring",
      "workspaces",
      "providers",
      "pipeline",
    ];
    return segments.flatMap((s) => [
      { source: `/api/${s}`, destination: `${backend}/api/${s}` },
      { source: `/api/${s}/:path*`, destination: `${backend}/api/${s}/:path*` },
    ]);
  },
};

module.exports = nextConfig;
