"use client";
import { useState, useMemo } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { MatchCard } from "@/components/MatchCard";
import { MatchModal } from "@/components/MatchModal";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { Segmented } from "@/components/ui/Segmented";
import { LeagueSelect } from "@/components/ui/LeagueSelect";
import { ProbBar } from "@/components/ui/ProbBar";
import { TeamLogo } from "@/components/TeamLogo";
import { I } from "@/components/Icons";

type Match = {
  id: number; competition: string; league: string; date: string;
  homeTeam: string; awayTeam: string;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; target?: string; bookmaker?: string; bestOdds?: number };
  recommendation?: string; confidence?: string;
  stats?: { btts_pct?: number; over25_pct?: number; over15_pct?: number; home_form?: string[]; away_form?: string[]; predicted_goals?: number; predicted_corners?: number; predicted_cards?: number };
  details?: { homeElo?: number; awayElo?: number; homeDaysRest?: number; awayDaysRest?: number; weatherCode?: number };
  injuries?: string[];
};

const getValueBetLabel = (match: Match) => {
  const selection = match.valueBet?.selection;
  const target = match.valueBet?.target;
  if (selection === "Home" || target === "1") return match.homeTeam;
  if (selection === "Away" || target === "2") return match.awayTeam;
  if (selection === "Draw" || target === "N") return "Match nul";
  return match.recommendation ?? "Sélection IA";
};

function ValueBetHero({ match, onClick }: { match: Match; onClick: () => void }) {
  const edge = match.valueBet?.edge ?? 0;
  const dateFmt = new Date(match.date).toLocaleString("fr-FR", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <Card onClick={onClick} pad={0} style={{ overflow: "hidden" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr" }}>
        <div style={{ padding: 32 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <Tag size="sm">{match.competition}</Tag>
            <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>{dateFmt}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
              <TeamLogo name={match.homeTeam} size={44} />
              <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{match.homeTeam}</div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", flexShrink: 0 }}>VS</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textAlign: "right" }}>{match.awayTeam}</div>
              <TeamLogo name={match.awayTeam} size={44} />
            </div>
          </div>
          <ProbBar p1={match.probs.p1} pn={match.probs.pn} p2={match.probs.p2} height={10} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-home)", fontWeight: 600 }}>1 · {match.probs.p1}%</span>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-draw)" }}>N · {match.probs.pn}%</span>
            <span className="mono tabular" style={{ fontSize: 12, color: "var(--acc-away)", fontWeight: 600 }}>2 · {match.probs.p2}%</span>
          </div>
        </div>
        <div style={{ padding: 32, background: "var(--value-tint)", display: "flex", flexDirection: "column", justifyContent: "center", gap: 12 }}>
          <div className="overline">Edge détecté</div>
          <div className="mono tabular" style={{ fontSize: 52, fontWeight: 600, letterSpacing: "-0.04em", lineHeight: 0.9, color: "var(--value)" }}>
            +{edge}%
          </div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>
            Parier sur <span style={{ color: "var(--value)" }}>{getValueBetLabel(match)}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-soft)" }}>
            Cote {match.odds?.h?.toFixed(2) ?? "—"}{match.valueBet?.bookmaker && ` sur ${match.valueBet.bookmaker}`} · Juste {match.probs?.p1 ? (100 / match.probs.p1).toFixed(2) : "—"}
          </div>
        </div>
      </div>
    </Card>
  );
}

function MatchListView({ matches, onOpen }: { matches: Match[]; onOpen: (m: Match) => void }) {
  return (
    <Card pad={0}>
      <div style={{ display: "grid", gridTemplateColumns: "180px 1fr 200px 100px 40px", padding: "12px 20px", borderBottom: "1px solid var(--border)", background: "var(--bg-inset)" }}>
        {["Date", "Match", "Probabilités", "Value", ""].map((h, i) => (
          <div key={i} className="overline">{h}</div>
        ))}
      </div>
      {matches.map((m, i) => (
        <div
          key={m.id}
          onClick={() => onOpen(m)}
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <TeamLogo name={m.homeTeam} size={24} />
            <span style={{ fontSize: 13, fontWeight: 500 }}>{m.homeTeam}</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>vs</span>
            <TeamLogo name={m.awayTeam} size={24} />
            <span style={{ fontSize: 13, fontWeight: 500 }}>{m.awayTeam}</span>
          </div>
          <div>
            <ProbBar p1={m.probs.p1} pn={m.probs.pn} p2={m.probs.p2} height={6} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              {[m.probs.p1, m.probs.pn, m.probs.p2].map((p, j) => (
                <span key={j} className="mono tabular" style={{ fontSize: 11, color: "var(--text-soft)" }}>{p}</span>
              ))}
            </div>
          </div>
          <div>
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
  const [openedMatch, setOpenedMatch] = useState<Match | null>(null);

  const availableLeagues = useMemo(() => {
    const seen = new Set<string>();
    return initialMatches.map((m) => m.league ?? m.competition).filter((l) => l && !seen.has(l) && seen.add(l));
  }, [initialMatches]);

  const filtered = useMemo(() =>
    league === "all" ? initialMatches : initialMatches.filter((m) => (m.league ?? m.competition) === league),
    [initialMatches, league]
  );

  const valueBets = useMemo(() =>
    filtered.filter((m) => m.valueBet?.active).sort((a, b) => (b.valueBet?.edge ?? 0) - (a.valueBet?.edge ?? 0)),
    [filtered]
  );

  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <AppShell>
      <div style={{ padding: "0 40px 80px" }}>
        <PageHeader
          overline={today}
          title="Analyses"
          subtitle={`${filtered.length} matchs à venir. ${valueBets.length} value bet${valueBets.length > 1 ? "s" : ""} détecté${valueBets.length > 1 ? "s" : ""}.`}
          actions={
            <Segmented
              value={view}
              onChange={setView}
              options={[
                { value: "cards", icon: <I.Grid size={15} /> },
                { value: "list", icon: <I.List size={15} /> },
              ]}
            />
          }
        />

        {initialMatches.length === 0 ? (
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
            <section style={{ padding: "8px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em" }}>
                  Tous les matchs
                  <span className="mono" style={{ marginLeft: 10, color: "var(--text-muted)", fontSize: 14, fontWeight: 400 }}>{filtered.length}</span>
                </h2>
                <LeagueSelect value={league} onChange={setLeague} leagues={availableLeagues} />
              </div>

              {filtered.length === 0 ? (
                <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
                  Aucun match disponible pour cette sélection.
                </div>
              ) : view === "cards" ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
                  {filtered.map((m) => (
                    <MatchCard key={m.id} match={m} onClick={() => setOpenedMatch(m)} />
                  ))}
                </div>
              ) : (
                <MatchListView matches={filtered} onOpen={(m) => setOpenedMatch(m)} />
              )}
            </section>
          </>
        )}
      </div>

      <MatchModal match={openedMatch} onClose={() => setOpenedMatch(null)} />
    </AppShell>
  );
}
