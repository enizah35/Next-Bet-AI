"use client";
import { useEffect, useMemo, useState } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { MatchCard } from "@/components/MatchCard";
import { MatchModal } from "@/components/MatchModal";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { Segmented } from "@/components/ui/Segmented";
import { LeagueSelect } from "@/components/ui/LeagueSelect";
import { DropdownSelect } from "@/components/ui/DropdownSelect";
import { ProbBar } from "@/components/ui/ProbBar";
import { TeamLogo } from "@/components/TeamLogo";
import { I } from "@/components/Icons";
import { LiveStatusPill } from "@/components/LiveStatusPill";
import { PredictionLoading } from "@/components/PredictionLoading";
import { useLiveMatches, type MatchLiveStatus } from "@/hooks/useLiveMatches";
import { getPublicApiUrl } from "@/utils/publicApi";

type Match = {
  id: number; competition: string; league: string; date: string;
  homeTeam: string; awayTeam: string;
  homeLogo?: string | null; awayLogo?: string | null;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; target?: string; bookmaker?: string; bestOdds?: number };
  recommendation?: string; confidence?: string;
  stats?: { btts_pct?: number; over25_pct?: number; over15_pct?: number; home_form?: string[]; away_form?: string[]; predicted_goals?: number; predicted_corners?: number; predicted_cards?: number };
  details?: { homeElo?: number; awayElo?: number; homeDaysRest?: number; awayDaysRest?: number; weatherCode?: number };
  injuries?: string[];
  liveStatus?: MatchLiveStatus;
};

type SortKey =
  | "date_asc"
  | "date_desc"
  | "odds_desc"
  | "confidence_desc"
  | "value_edge_desc"
  | "league_asc";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "date_asc", label: "Date proche" },
  { value: "date_desc", label: "Date lointaine" },
  { value: "odds_desc", label: "Cote élevée" },
  { value: "confidence_desc", label: "Confiance max" },
  { value: "value_edge_desc", label: "Value edge" },
  { value: "league_asc", label: "Ligue A-Z" },
];

const LEAGUE_OPTIONS = [
  "Champions League",
  "Premier League",
  "Championship",
  "Ligue 1",
  "Ligue 2",
  "Bundesliga",
  "2. Bundesliga",
  "La Liga",
  "La Liga 2",
  "Serie A",
  "Serie B",
  "Eredivisie",
  "Primeira Liga",
  "Süper Lig",
  "Belgian Pro League",
  "Scottish Premiership",
];

const matchTime = (match: Match) => {
  const time = new Date(match.date).getTime();
  return Number.isFinite(time) ? time : Number.MAX_SAFE_INTEGER;
};

const confidenceProb = (match: Match) => Math.max(match.probs?.p1 ?? 0, match.probs?.pn ?? 0, match.probs?.p2 ?? 0);
const valueEdge = (match: Match) => (match.valueBet?.active ? match.valueBet?.edge ?? 0 : -1);
const leagueName = (match: Match) => match.league ?? match.competition ?? "";

const getMarketOdd = (match: Match, key: "h" | "d" | "a") => {
  const legacy = key === "h" ? "home" : key === "d" ? "draw" : "away";
  return match.odds?.[key] ?? match.odds?.[legacy];
};

const maxMatchOdd = (match: Match) => {
  const odds = [
    getMarketOdd(match, "h"),
    getMarketOdd(match, "d"),
    getMarketOdd(match, "a"),
    match.valueBet?.bestOdds,
  ].filter((odd): odd is number => typeof odd === "number" && Number.isFinite(odd));
  return odds.length ? Math.max(...odds) : -1;
};

const valueBetMarket = (match: Match) => {
  const selection = match.valueBet?.selection;
  const target = match.valueBet?.target?.toUpperCase();
  if (selection === "Home" || target === "1") return "home";
  if (selection === "Away" || target === "2") return "away";
  if (selection === "Draw" || target === "N" || target === "X") return "draw";
  if (target === "1N" || target === "1X") return "home_draw";
  if (target === "N2" || target === "X2") return "draw_away";
  return "home";
};

const getValueBetOdd = (match: Match) => {
  if (match.valueBet?.bestOdds) return match.valueBet.bestOdds;
  const market = valueBetMarket(match);
  if (market === "home") return getMarketOdd(match, "h");
  if (market === "draw") return getMarketOdd(match, "d");
  if (market === "away") return getMarketOdd(match, "a");
};

const getValueBetFairOdd = (match: Match) => {
  const market = valueBetMarket(match);
  const prob =
    market === "home" ? match.probs?.p1 :
    market === "draw" ? match.probs?.pn :
    market === "away" ? match.probs?.p2 :
    market === "home_draw" ? (match.probs?.p1 ?? 0) + (match.probs?.pn ?? 0) :
    market === "draw_away" ? (match.probs?.pn ?? 0) + (match.probs?.p2 ?? 0) :
    0;
  return prob > 0 ? 100 / prob : undefined;
};

const getValueBetLabel = (match: Match) => {
  const market = valueBetMarket(match);
  if (market === "home") return match.homeTeam;
  if (market === "away") return match.awayTeam;
  if (market === "draw") return "Match nul";
  if (market === "home_draw") return `${match.homeTeam} ou Nul`;
  if (market === "draw_away") return `${match.awayTeam} ou Nul`;
  return match.recommendation ?? "Sélection IA";
};

function ValueBetHero({ match, onClick }: { match: Match; onClick: () => void }) {
  const edge = match.valueBet?.edge ?? 0;
  const displayedOdd = getValueBetOdd(match);
  const fairOdd = getValueBetFairOdd(match);
  const dateFmt = new Date(match.date).toLocaleString("fr-FR", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <Card className="value-hero-card" onClick={onClick} pad={0} style={{ overflow: "hidden" }}>
      <div className="value-hero-grid" style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr" }}>
        <div className="value-hero-main" style={{ padding: 32 }}>
          <div className="value-hero-meta" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <Tag size="sm">{match.competition}</Tag>
            <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>{dateFmt}</span>
          </div>
          <div className="matchup-row" style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
              <TeamLogo name={match.homeTeam} logoUrl={match.homeLogo} size={44} />
              <div className="value-hero-team-name" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{match.homeTeam}</div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", flexShrink: 0 }}>VS</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
              <div className="value-hero-team-name" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textAlign: "right" }}>{match.awayTeam}</div>
              <TeamLogo name={match.awayTeam} logoUrl={match.awayLogo} size={44} />
            </div>
          </div>
          <ProbBar p1={match.probs.p1} pn={match.probs.pn} p2={match.probs.p2} height={10} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-home)", fontWeight: 600 }}>1 · {match.probs.p1}%</span>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-draw)" }}>N · {match.probs.pn}%</span>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-away)", fontWeight: 600 }}>2 · {match.probs.p2}%</span>
          </div>
        </div>
        <div className="value-hero-panel" style={{ padding: 32, background: "var(--value-tint)", display: "flex", flexDirection: "column", justifyContent: "center", gap: 12 }}>
          <div className="overline">Edge détecté</div>
          <div className="mono tabular value-hero-edge" style={{ fontSize: 52, fontWeight: 600, letterSpacing: "-0.04em", lineHeight: 0.9, color: "var(--value)" }}>
            +{edge}%
          </div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>
            Parier sur <span style={{ color: "var(--value)" }}>{getValueBetLabel(match)}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-soft)" }}>
            Cote {displayedOdd?.toFixed(2) ?? "—"}{match.valueBet?.bookmaker && ` sur ${match.valueBet.bookmaker}`} · Juste {fairOdd?.toFixed(2) ?? "—"}
          </div>
        </div>
      </div>
    </Card>
  );
}

function MatchListView({ matches, onOpen }: { matches: Match[]; onOpen: (m: Match) => void }) {
  return (
    <Card pad={0}>
      <div className="mobile-list-header" style={{ display: "grid", gridTemplateColumns: "180px 1fr 200px 100px 40px", padding: "12px 20px", borderBottom: "1px solid var(--border)", background: "var(--bg-inset)" }}>
        {["Date", "Match", "Probabilités", "Value", ""].map((h, i) => (
          <div key={i} className="overline">{h}</div>
        ))}
      </div>
      {matches.map((m, i) => (
        <div
          key={m.id}
          onClick={() => onOpen(m)}
          className="mobile-list-row"
          style={{
            display: "grid", gridTemplateColumns: "180px 1fr 200px 100px 40px",
            padding: "16px 20px", alignItems: "center", gap: 12,
            borderBottom: i < matches.length - 1 ? "1px solid var(--border)" : "none",
            cursor: "pointer", transition: "background 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-inset)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <div className="mono" style={{ fontSize: 12, color: "var(--text-soft)" }}>
            {new Date(m.date).toLocaleString("fr-FR", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
          </div>
          <div className="mobile-match-line" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <TeamLogo name={m.homeTeam} logoUrl={m.homeLogo} size={24} />
            <span className="mobile-match-team" style={{ fontSize: 13, fontWeight: 500 }}>{m.homeTeam}</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>vs</span>
            <TeamLogo name={m.awayTeam} logoUrl={m.awayLogo} size={24} />
            <span className="mobile-match-team" style={{ fontSize: 13, fontWeight: 500 }}>{m.awayTeam}</span>
          </div>
          <div className="mobile-list-probs">
            <ProbBar p1={m.probs.p1} pn={m.probs.pn} p2={m.probs.p2} height={6} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              {[m.probs.p1, m.probs.pn, m.probs.p2].map((p, j) => (
                <span key={j} className="mono tabular" style={{ fontSize: 11, color: "var(--text-soft)" }}>{p}</span>
              ))}
            </div>
          </div>
          <div className="mobile-list-value">
            {m.valueBet?.active ? (
              <span className="mono tabular" style={{ fontSize: 14, fontWeight: 600, color: "var(--value)" }}>+{m.valueBet.edge}%</span>
            ) : (
              <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>—</span>
            )}
          </div>
          <I.Chevron size={14} style={{ color: "var(--text-muted)" }} />
        </div>
      ))}
    </Card>
  );
}

export default function DashboardClient({ initialMatches = [] }: { initialMatches: Match[] }) {
  const [league, setLeague] = useState("all");
  const [view, setView] = useState("cards");
  const [sort, setSort] = useState<SortKey>("date_asc");
  const [openedMatch, setOpenedMatch] = useState<Match | null>(null);
  const { matches: liveMatches, state: liveState } = useLiveMatches<Match>(initialMatches, 300);
  const [leagueMatches, setLeagueMatches] = useState<Match[] | null>(null);
  const [leagueLoading, setLeagueLoading] = useState(false);

  useEffect(() => {
    if (league === "all") {
      setLeagueMatches(null);
      setLeagueLoading(false);
      return;
    }

    let cancelled = false;
    let attempt = 0;
    let timer: number | undefined;

    const fetchLeague = async () => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), attempt === 0 ? 12000 : 7000);

      try {
        const url = `${getPublicApiUrl()}/predictions/upcoming/full-cached?league=${encodeURIComponent(league)}&limit=80`;
        const response = await fetch(url, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`League refresh failed: ${response.status}`);

        const data = (await response.json()) as Match[];
        if (cancelled || !Array.isArray(data)) return;

        if (data.length === 0 && attempt < 6) {
          attempt += 1;
          timer = window.setTimeout(fetchLeague, 5000);
          return;
        }

        setLeagueMatches(data);
        setLeagueLoading(false);
      } catch {
        if (cancelled) return;
        attempt += 1;
        if (attempt < 4) {
          timer = window.setTimeout(fetchLeague, 6000);
        } else {
          setLeagueMatches([]);
          setLeagueLoading(false);
        }
      } finally {
        window.clearTimeout(timeout);
      }
    };

    setLeagueMatches(null);
    setLeagueLoading(true);
    fetchLeague();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [league]);

  const visibleMatches = useMemo(() => {
    if (league === "all") return liveMatches;
    return leagueMatches ?? liveMatches.filter((m) => (m.league ?? m.competition) === league);
  }, [league, leagueMatches, liveMatches]);

  const filtered = useMemo(() =>
    league === "all" ? visibleMatches : visibleMatches.filter((m) => (m.league ?? m.competition) === league),
    [visibleMatches, league]
  );
  const isLoadingPredictions = visibleMatches.length === 0 && (
    liveState === "refreshing" ||
    liveState === "stale" ||
    (league !== "all" && leagueLoading)
  );

  const sortedMatches = useMemo(() => {
    const byDateAsc = (a: Match, b: Match) => matchTime(a) - matchTime(b);
    return [...filtered].sort((a, b) => {
      let diff = 0;
      if (sort === "date_asc") diff = byDateAsc(a, b);
      if (sort === "date_desc") diff = matchTime(b) - matchTime(a);
      if (sort === "odds_desc") diff = maxMatchOdd(b) - maxMatchOdd(a);
      if (sort === "confidence_desc") diff = confidenceProb(b) - confidenceProb(a);
      if (sort === "value_edge_desc") diff = valueEdge(b) - valueEdge(a);
      if (sort === "league_asc") diff = leagueName(a).localeCompare(leagueName(b), "fr");
      return diff || byDateAsc(a, b) || a.id - b.id;
    });
  }, [filtered, sort]);

  const valueBets = useMemo(() =>
    filtered.filter((m) => m.valueBet?.active).sort((a, b) => (b.valueBet?.edge ?? 0) - (a.valueBet?.edge ?? 0)),
    [filtered]
  );

  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          overline={today}
          title="Analyses"
          subtitle={
            isLoadingPredictions
              ? "Chargement des prédictions en cours."
              : `${filtered.length} matchs à venir. ${valueBets.length} value bet${valueBets.length > 1 ? "s" : ""} détecté${valueBets.length > 1 ? "s" : ""}.`
          }
          actions={
            <>
              <LiveStatusPill state={liveState} />
              <Segmented
                className="dashboard-view-toggle"
                value={view}
                onChange={setView}
                options={[
                  { value: "cards", icon: <I.Grid size={15} /> },
                  { value: "list", icon: <I.List size={15} /> },
                ]}
              />
            </>
          }
        />

        {isLoadingPredictions ? (
          <PredictionLoading
            title={league === "all" ? "Chargement des prédictions" : `Chargement ${league}`}
            subtitle="Les matchs, probabilités et cotes vont apparaître automatiquement."
            rows={4}
          />
        ) : visibleMatches.length === 0 ? (
          <div style={{ padding: "80px 0", textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 14, color: "var(--text-muted)" }}>Aucune analyse trouvée ou impossible de charger les données.</div>
          </div>
        ) : (
          <>
            {/* Top value bet hero */}
            {valueBets[0] && (
              <section style={{ padding: "8px 0 32px" }}>
                <div className="overline" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <I.Bolt size={12} style={{ color: "var(--value)" }} /> Value bet du jour
                </div>
                <ValueBetHero match={valueBets[0]} onClick={() => setOpenedMatch(valueBets[0])} />
              </section>
            )}

            {/* All matches */}
            <section className="analysis-list-section" style={{ padding: "8px 0" }}>
              <div className="analysis-list-top" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
                <h2 className="analysis-list-title" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em" }}>
                  Tous les matchs
                  <span className="mono" style={{ marginLeft: 10, color: "var(--text-muted)", fontSize: 14, fontWeight: 400 }}>{filtered.length}</span>
                </h2>
                <div className="analysis-controls" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <label className="analysis-control" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="overline" style={{ color: "var(--text-muted)" }}>Tri</span>
                    <DropdownSelect
                      value={sort}
                      onChange={(nextSort) => setSort(nextSort as SortKey)}
                      options={SORT_OPTIONS}
                      minWidth={202}
                      ariaLabel="Trier les analyses"
                    />
                  </label>
                  <label className="analysis-control" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="overline" style={{ color: "var(--text-muted)" }}>Ligue</span>
                    <LeagueSelect value={league} onChange={setLeague} leagues={LEAGUE_OPTIONS} />
                  </label>
                </div>
              </div>

              {filtered.length === 0 ? (
                <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
                  Aucun match disponible pour cette sélection.
                </div>
              ) : view === "cards" ? (
                <div className="match-card-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: 16 }}>
                  {sortedMatches.map((m) => (
                    <MatchCard key={m.id} match={m} onClick={() => setOpenedMatch(m)} />
                  ))}
                </div>
              ) : (
                <MatchListView matches={sortedMatches} onOpen={(m) => setOpenedMatch(m)} />
              )}
            </section>
          </>
        )}
      </div>

      <MatchModal match={openedMatch} onClose={() => setOpenedMatch(null)} />
    </AppShell>
  );
}
