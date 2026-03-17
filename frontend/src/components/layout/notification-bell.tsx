"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { notifications, type NotificationItem } from "@/lib/api";

const TYPE_COLORS: Record<string, string> = {
  case_assigned: "text-arq-blue-400",
  case_status_changed: "text-purple-400",
  sla_warning: "text-yellow-400",
  sla_breached: "text-red-400",
  case_escalated: "text-orange-400",
  pipeline_completed: "text-arq-lime-400",
};

export function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [recent, setRecent] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadCount();
    const interval = setInterval(loadCount, 30000); // poll every 30s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function loadCount() {
    notifications
      .unreadCount()
      .then((res) => setUnreadCount(res.unread_count))
      .catch(() => {});
  }

  function handleOpen() {
    setOpen(!open);
    if (!open) {
      notifications
        .list({ limit: 8 })
        .then((res) => setRecent(res.notifications))
        .catch(() => {});
    }
  }

  async function handleMarkAllRead() {
    await notifications.markAllRead();
    setUnreadCount(0);
    setRecent((prev) => prev.map((n) => ({ ...n, is_read: true })));
  }

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "now";
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleOpen}
        className="relative p-2 rounded-lg hover:bg-surface-2 transition-colors"
      >
        <Bell size={18} className="text-t-muted" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-surface-1 border border-white/[0.08] rounded-lg shadow-lg shadow-black/40 z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
            <span className="text-sm font-medium text-t-primary">
              Notifications
            </span>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-arq-blue-400 hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {recent.length === 0 ? (
              <div className="px-4 py-6 text-center text-t-muted text-sm">
                No notifications
              </div>
            ) : (
              recent.map((n) => (
                <div
                  key={n.notification_id}
                  className={`px-4 py-3 border-b border-white/[0.04] hover:bg-surface-2/50 ${
                    !n.is_read ? "bg-arq-blue-500/5" : ""
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="w-2 h-2 rounded-full bg-arq-blue-400 mt-1.5 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-t-primary font-medium truncate">
                        {n.title}
                      </div>
                      <div className="text-xs text-t-muted truncate">
                        {n.body}
                      </div>
                      <div className="text-[10px] text-t-muted mt-0.5">
                        {timeAgo(n.created_at)}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="px-4 py-2 border-t border-white/[0.06]">
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className="text-xs text-arq-blue-400 hover:underline"
            >
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
