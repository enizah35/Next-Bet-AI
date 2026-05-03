"use client";

import { useEffect, useMemo, useState } from "react";
import { getPublicApiUrl } from "@/utils/publicApi";

type LiveMode = "fast" | "full";

export type MatchLiveStatus = {
  mode?: LiveMode;
  generatedAt?: string;
  oddsLoaded?: boolean;
  bookmakerMarketsLoaded?: boolean;
  statsLoaded?: boolean;
  injuriesLoaded?: boolean;
  lineupsLoaded?: boolean;
};

type MatchWithLiveStatus = {
  id: number;
  homeTeam?: string;
  awayTeam?: string;
  date?: string;
  liveStatus?: MatchLiveStatus;
  availability?: unknown;
  details?: unknown;
};

export type LiveHydrationState = "idle" | "refreshing" | "complete" | "stale" | "empty" | "error";

const getDetails = (match: MatchWithLiveStatus) =>
  (match.details ?? {}) as { fixtureId?: number | null; injuriesSource?: string; lineupsAvailable?: boolean };

const isFullLivePayload = (matches: MatchWithLiveStatus[]) =>
  matches.some((match) => {
    const details = getDetails(match);
    return (
      match.liveStatus?.mode === "full" ||
      match.liveStatus?.injuriesLoaded ||
      match.liveStatus?.lineupsLoaded ||
      details.injuriesSource === "fixture" ||
      details.lineupsAvailable
    );
  });

const mergeMatches = <T extends MatchWithLiveStatus>(current: T[], incoming: T[]) => {
  if (incoming.length === 0) return current;

  const incomingByKey = new Map(
    incoming.map((match) => [
      `${match.homeTeam ?? ""}|${match.awayTeam ?? ""}|${match.date ?? ""}`,
      match,
    ]),
  );
  const seen = new Set<string>();

  const merged = current.map((match) => {
    const key = `${match.homeTeam ?? ""}|${match.awayTeam ?? ""}|${match.date ?? ""}`;
    seen.add(key);
    return { ...match, ...(incomingByKey.get(key) ?? {}) } as T;
  });

  for (const match of incoming) {
    const key = `${match.homeTeam ?? ""}|${match.awayTeam ?? ""}|${match.date ?? ""}`;
    if (!seen.has(key)) merged.push(match);
  }

  return merged;
};

export function useLiveMatches<T extends MatchWithLiveStatus>(initialMatches: T[], limit = 40) {
  const [matches, setMatches] = useState<T[]>(initialMatches);
  const [state, setState] = useState<LiveHydrationState>(() =>
    initialMatches.length === 0 ? "refreshing" : isFullLivePayload(initialMatches) ? "complete" : "stale",
  );

  const initialSignature = useMemo(
    () => initialMatches.map((match) => `${match.homeTeam ?? ""}|${match.awayTeam ?? ""}|${match.date ?? ""}`).join("::"),
    [initialMatches],
  );

  useEffect(() => {
    setMatches(initialMatches);
    setState(initialMatches.length === 0 ? "refreshing" : isFullLivePayload(initialMatches) ? "complete" : "stale");
  }, [initialMatches, initialSignature]);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;
    let timer: number | undefined;

    const fetchLive = async () => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), attempt === 0 ? 9000 : 6000);

      try {
        setState((current) => (current === "complete" ? current : "refreshing"));
        const url = `${getPublicApiUrl()}/predictions/upcoming/full-cached?limit=${limit}`;
        const response = await fetch(url, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`Live refresh failed: ${response.status}`);

        const data = (await response.json()) as T[];
        if (cancelled || !Array.isArray(data)) return;

        if (data.length === 0) {
          attempt += 1;
          if (attempt < 6) {
            setState("stale");
            timer = window.setTimeout(fetchLive, 5000);
          } else {
            setState("empty");
          }
          return;
        }

        setMatches((current) => mergeMatches(current, data));
        if (isFullLivePayload(data)) {
          setState("complete");
          return;
        }

        attempt += 1;
        setState("stale");
        if (attempt < 6) {
          timer = window.setTimeout(fetchLive, 5000);
        }
      } catch {
        if (cancelled) return;
        attempt += 1;
        if (attempt < 4) {
          setState("stale");
          timer = window.setTimeout(fetchLive, 6000);
        } else {
          setState("error");
        }
      } finally {
        window.clearTimeout(timeout);
      }
    };

    fetchLive();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [initialMatches.length, limit, initialSignature]);

  return { matches, state };
}
