"use client";

import { PipelineMonitor } from "@/components/pipeline-monitor";
import { useWorkspace } from "@/lib/workspace-context";

export default function PipelinePage() {
  const { activeWorkspace } = useWorkspace();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[15px] font-semibold text-text-primary tracking-tight">Detection Pipeline</h1>
        <p className="text-xs text-text-tertiary mt-1">
          Run the full FWA detection pipeline with real-time progress tracking
        </p>
      </div>
      <PipelineMonitor workspaceId={activeWorkspace} />
    </div>
  );
}
