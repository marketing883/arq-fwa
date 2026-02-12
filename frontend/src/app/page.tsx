"use client";

import { useEffect, useState } from "react";

export default function DashboardPage() {
  const [health, setHealth] = useState<{ status: string } | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Executive Overview</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {["Total Fraud Identified", "Active Cases", "Claims Processed", "Recovery Rate"].map(
          (label) => (
            <div
              key={label}
              className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm"
            >
              <p className="text-sm text-gray-500">{label}</p>
              <p className="text-2xl font-bold mt-1 text-gray-400">--</p>
            </div>
          )
        )}
      </div>
      <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-2">System Status</h2>
        {health ? (
          <p className="text-green-600 font-medium">
            Backend connected — {health.status}
          </p>
        ) : (
          <p className="text-red-500">Backend not reachable</p>
        )}
      </div>
    </div>
  );
}
