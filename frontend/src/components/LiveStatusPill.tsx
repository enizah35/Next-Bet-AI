"use client";

import type { LiveHydrationState } from "@/hooks/useLiveMatches";

const config: Record<LiveHydrationState, { label: string; color: string }> = {
  idle: { label: "Live cache", color: "var(--text-muted)" },
  refreshing: { label: "Live en cours", color: "var(--acc-home)" },
  stale: { label: "Cache en attente", color: "var(--warn)" },
  complete: { label: "Live complet", color: "var(--good)" },
  empty: { label: "Aucun match", color: "var(--text-muted)" },
  error: { label: "Live indisponible", color: "var(--bad)" },
};

export function LiveStatusPill({ state }: { state: LiveHydrationState }) {
  const current = config[state];

  return (
    <span className="live-status-pill" aria-live="polite">
      <span className="live-status-dot" style={{ background: current.color }} />
      {current.label}
    </span>
  );
}
