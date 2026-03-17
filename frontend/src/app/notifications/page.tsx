"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { notifications, type NotificationItem } from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  case_assigned: "Case Assigned",
  case_status_changed: "Status Changed",
  sla_warning: "SLA Warning",
  sla_breached: "SLA Breached",
  case_escalated: "Escalated",
  pipeline_completed: "Pipeline Complete",
};

const TYPE_COLORS: Record<string, string> = {
  case_assigned: "bg-arq-blue-500/20 text-arq-blue-400",
  case_status_changed: "bg-purple-500/20 text-purple-400",
  sla_warning: "bg-yellow-500/20 text-yellow-400",
  sla_breached: "bg-red-500/20 text-red-400",
  case_escalated: "bg-orange-500/20 text-orange-400",
  pipeline_completed: "bg-arq-lime-500/20 text-arq-lime-400",
};

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  useEffect(() => {
    load();
  }, [filter]);

  function load() {
    setLoading(true);
    notifications
      .list({
        is_read: filter === "unread" ? false : undefined,
        limit: 100,
      })
      .then((res) => setItems(res.notifications))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  async function handleMarkRead(id: string) {
    try {
      await notifications.markRead(id);
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleMarkAllRead() {
    try {
      await notifications.markAllRead();
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function resourceLink(n: NotificationItem): string | null {
    if (n.resource_type === "case" && n.resource_id) {
      return `/cases/${n.resource_id}`;
    }
    return null;
  }

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-t-primary">Notifications</h1>
          <p className="text-sm text-t-muted mt-1">
            Case assignments, status changes, and SLA alerts
          </p>
        </div>
        <button
          onClick={handleMarkAllRead}
          className="px-4 py-2 bg-surface-2 text-t-secondary rounded-lg text-sm hover:bg-surface-3 transition-colors"
        >
          Mark All Read
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-1 mb-6 bg-surface-1 rounded-lg p-1 w-fit">
        {(["all", "unread"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              filter === f
                ? "bg-surface-3 text-t-primary"
                : "text-t-muted hover:text-t-secondary"
            }`}
          >
            {f === "all" ? "All" : "Unread"}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-t-muted text-sm">Loading...</div>
      ) : (
        <div className="space-y-2">
          {items.map((n) => {
            const link = resourceLink(n);
            return (
              <div
                key={n.notification_id}
                className={`p-4 rounded-lg border transition-colors ${
                  n.is_read
                    ? "bg-surface-1 border-white/[0.04]"
                    : "bg-surface-1 border-arq-blue-500/20"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          TYPE_COLORS[n.notification_type] || "bg-surface-3 text-t-muted"
                        }`}
                      >
                        {TYPE_LABELS[n.notification_type] || n.notification_type}
                      </span>
                      <span className="text-xs text-t-muted">
                        {timeAgo(n.created_at)}
                      </span>
                      {!n.is_read && (
                        <span className="w-2 h-2 rounded-full bg-arq-blue-400" />
                      )}
                    </div>
                    <div className="text-sm text-t-primary font-medium">
                      {n.title}
                    </div>
                    <div className="text-sm text-t-muted mt-0.5">
                      {n.body}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {link && (
                      <Link
                        href={link}
                        className="px-3 py-1 bg-arq-blue-500/20 text-arq-blue-400 rounded-lg text-xs hover:bg-arq-blue-500/30 transition-colors"
                      >
                        View
                      </Link>
                    )}
                    {!n.is_read && (
                      <button
                        onClick={() => handleMarkRead(n.notification_id)}
                        className="px-3 py-1 bg-surface-2 text-t-muted rounded-lg text-xs hover:bg-surface-3 transition-colors"
                      >
                        Mark Read
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {items.length === 0 && (
            <div className="text-center text-t-muted py-8">
              {filter === "unread" ? "No unread notifications." : "No notifications yet."}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
