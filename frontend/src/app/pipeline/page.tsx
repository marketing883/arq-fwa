"use client";

import { PipelineMonitor } from "@/components/pipeline-monitor";
import { useWorkspace } from "@/lib/workspace-context";

export default function PipelinePage() {
  const { activeWorkspace } = useWorkspace();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-t-primary">Detection Pipeline</h1>
        <p className="text-sm text-t-muted mt-1">
          Run the full FWA detection pipeline with real-time progress tracking
        </p>
      </div>
      <PipelineMonitor workspaceId={activeWorkspace} />
    </div>
  );
}
