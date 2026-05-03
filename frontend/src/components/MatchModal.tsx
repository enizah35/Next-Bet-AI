"use client";
import React, { useEffect } from "react";
import { TeamLogo } from "./TeamLogo";
import { Tag } from "./ui/Tag";
import { ProbBar } from "./ui/ProbBar";
import { Ring } from "./ui/Ring";
import { FormDots } from "./ui/FormDots";
import { I } from "./Icons";

type PlayerStatus = string | { name?: string; reason?: string; type?: string };

interface Match {
  id: number;
  competition: string;
  date: string;
  homeTeam: string;
  awayTeam: string;
  homeLogo?: string | null;
  awayLogo?: string | null;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; target?: string; bookmaker?: string; bestOdds?: number };
  recommendation?: string;
  stats?: {
    btts_pct?: number; over25_pct?: number; over15_pct?: number;
    home_form?: string[]; away_form?: string[];
    predicted_goals?: number; predicted_corners?: number; predicted_cards?: number;
  };
  details?: {
    homeElo?: number; awayElo?: number;
    homeDaysRest?: number; awayDaysRest?: number;
    weatherCode?: number;
    fixtureId?: number | string | null;
    lineupsAvailable?: boolean;
    injuriesSource?: string;
    injuriesCountHome?: number;
    injuriesCountAway?: number;
    homeMissingPlayers?: PlayerStatus[];
    awayMissingPlayers?: PlayerStatus[];
  };
  availability?: {
    fixtureId?: number | string | null;
    injuries?: {
      source?: string;
      home?: { count?: number; players?: PlayerStatus[] };
      away?: { count?: number; players?: PlayerStatus[] };
    };
    homeSquad?: {
      squad_score?: number;
      available_count?: number;
      total_count?: number;
      lineup_confirmed?: boolean;
      formation?: string | null;
      missing_players?: PlayerStatus[];
      starters?: PlayerStatus[];
    };
    awaySquad?: {
      squad_score?: number;
      available_count?: number;
      total_count?: number;
      lineup_confirmed?: boolean;
      formation?: string | null;
      missing_players?: PlayerStatus[];
      starters?: PlayerStatus[];
    };
  };
}

const weatherLabel = (code?: number) =>
  code === 1 ? "Dégagé" : code === 2 ? "Partiellement nuageux" : code === 3 ? "Pluie" : "—";

const getOdd = (match: Match, key: "h" | "d" | "a") => {
  const legacy = key === "h" ? "home" : key === "d" ? "draw" : "away";
  return match.odds?.[key] ?? match.odds?.[legacy];
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
  if (market === "home") return getOdd(match, "h");
  if (market === "draw") return getOdd(match, "d");
  if (market === "away") return getOdd(match, "a");
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

const getFairOdd = (match: Match) => {
  const market = valueBetMarket(match);
  const pct =
    market === "away" ? match.probs.p2 :
    market === "draw" ? match.probs.pn :
    market === "home_draw" ? match.probs.p1 + match.probs.pn :
    market === "draw_away" ? match.probs.pn + match.probs.p2 :
    match.probs.p1;
  return pct > 0 ? 100 / pct : undefined;
};

const getMainPrediction = (match: Match) => {
  const candidates = [
    { key: "1", label: match.homeTeam, pct: match.probs.p1, color: "var(--acc-home)" },
    { key: "N", label: "Match nul", pct: match.probs.pn, color: "var(--acc-draw)" },
    { key: "2", label: match.awayTeam, pct: match.probs.p2, color: "var(--acc-away)" },
  ];

  return candidates.reduce((best, current) => (current.pct > best.pct ? current : best), candidates[0]);
};

const playerLabel = (player: PlayerStatus) => {
  if (typeof player === "string") return player;
  const detail = player.reason || player.type;
  return [player.name, detail].filter(Boolean).join(" - ");
};

export function MatchModal({ match, onClose }: { match: Match | null; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  if (!match) return null;

  const { competition, date, homeTeam, awayTeam, homeLogo, awayLogo, probs, valueBet, stats, details } = match;
  const displayedOdd = getValueBetOdd(match);
  const fairOdd = getFairOdd(match);
  const mainPrediction = getMainPrediction(match);
  const fmt = new Date(date).toLocaleString("fr-FR", { weekday: "long", day: "2-digit", month: "long", hour: "2-digit", minute: "2-digit" });
  const availability = match.availability;
  const homeSquad = availability?.homeSquad;
  const awaySquad = availability?.awaySquad;
  const homeMissing = details?.homeMissingPlayers ?? homeSquad?.missing_players ?? availability?.injuries?.home?.players ?? [];
  const awayMissing = details?.awayMissingPlayers ?? awaySquad?.missing_players ?? availability?.injuries?.away?.players ?? [];
  const homeInjuryCount = details?.injuriesCountHome ?? availability?.injuries?.home?.count ?? homeMissing.length;
  const awayInjuryCount = details?.injuriesCountAway ?? availability?.injuries?.away?.count ?? awayMissing.length;
  const lineupsAvailable = details?.lineupsAvailable || homeSquad?.lineup_confirmed || awaySquad?.lineup_confirmed;
  const hasAvailability = Boolean(details?.fixtureId || availability?.fixtureId || homeInjuryCount || awayInjuryCount || lineupsAvailable);

  return (
    <div
      onClick={onClose}
      className="fade-up modal-backdrop"
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,0.5)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="match-modal"
        style={{
          background: "var(--bg-elev)", border: "1px solid var(--border)",
          borderRadius: 20, maxWidth: 720, width: "100%",
          maxHeight: "90vh", overflowY: "auto",
          boxShadow: "var(--shadow-float)", position: "relative",
        }}
      >
        <div className="modal-handle" aria-hidden="true" />
        {/* Close */}
        <button
          onClick={onClose}
          className="modal-close-button"
          style={{
            position: "absolute", top: 16, right: 16, zIndex: 2,
            width: 32, height: 32, borderRadius: 10,
            background: "var(--bg-inset)", color: "var(--text-soft)",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <I.Close size={16} />
        </button>

        {/* Header */}
        <div className="modal-section" style={{ padding: 28, borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <Tag size="sm">{competition}</Tag>
            <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmt}</span>
          </div>

          <div className="modal-teams" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, minWidth: 0 }}>
              <TeamLogo name={homeTeam} logoUrl={homeLogo} size={52} />
              <div style={{ minWidth: 0 }}>
                <div className="modal-team-name" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{homeTeam}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {details?.homeElo && `Elo ${details.homeElo}`}
                  {details?.homeDaysRest && ` · ${details.homeDaysRest}j repos`}
                </div>
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>VS</div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
              <div style={{ textAlign: "right", minWidth: 0 }}>
                <div className="modal-team-name" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{awayTeam}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {details?.awayElo && `Elo ${details.awayElo}`}
                  {details?.awayDaysRest && ` · ${details.awayDaysRest}j repos`}
                </div>
              </div>
              <TeamLogo name={awayTeam} logoUrl={awayLogo} size={52} />
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Main prediction */}
          <div style={{ padding: 18, borderRadius: 14, background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span
                className="mono tabular"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background: mainPrediction.color,
                  color: "white",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                {mainPrediction.key}
              </span>
              <span className="overline" style={{ color: mainPrediction.color }}>Prédiction IA</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 14, alignItems: "flex-start" }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 18, fontWeight: 650, letterSpacing: "-0.015em", overflowWrap: "anywhere" }}>
                  {mainPrediction.label}
                </div>
                {match.recommendation && (
                  <div style={{ fontSize: 13, color: "var(--text-soft)", marginTop: 4, overflowWrap: "anywhere" }}>
                    {match.recommendation}
                  </div>
                )}
              </div>
              <div className="mono tabular" style={{ fontSize: 24, fontWeight: 700, color: mainPrediction.color, whiteSpace: "nowrap" }}>
                {mainPrediction.pct}%
              </div>
            </div>
          </div>

          {/* Value bet banner */}
          {valueBet?.active && (
            <div style={{ padding: 18, borderRadius: 14, background: "var(--value-tint)", border: "1px solid var(--value)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <I.Bolt size={14} style={{ color: "var(--value)" }} />
                <span className="overline" style={{ color: "var(--value)" }}>
                  Value bet · +{valueBet.edge}% edge
                </span>
              </div>
              <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.015em" }}>
                Parier sur {getValueBetLabel(match)}
              </div>
              <div style={{ fontSize: 13, color: "var(--text-soft)", marginTop: 4 }}>
                Cote {displayedOdd?.toFixed(2) ?? "—"}{valueBet.bookmaker && ` sur ${valueBet.bookmaker}`} · cote juste : {fairOdd?.toFixed(2) ?? "—"}
              </div>
            </div>
          )}

          {/* Probabilities */}
          <div>
            <div className="overline" style={{ marginBottom: 12 }}>Probabilités IA</div>
            <ProbBar p1={probs.p1} pn={probs.pn} p2={probs.p2} height={12} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
              {[
                { pct: probs.p1, label: `1 · ${homeTeam}`, color: "var(--acc-home)" },
                { pct: probs.pn, label: "N · Nul", color: "var(--acc-draw)" },
                { pct: probs.p2, label: `2 · ${awayTeam}`, color: "var(--acc-away)" },
              ].map(({ pct, label, color }, i) => (
                <div key={i} style={{ textAlign: i === 1 ? "center" : i === 2 ? "right" : "left" }}>
                  <div className="mono tabular" style={{ fontSize: 18, fontWeight: 600, color }}>{pct}%</div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Rings */}
          {stats && (
            <div className="modal-rings" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, justifyItems: "center" }}>
              <Ring value={stats.btts_pct ?? 50} size={80} color="var(--acc-draw)" label="BTTS" />
              <Ring value={stats.over25_pct ?? 50} size={80} color="var(--good)" label="+ 2.5 buts" />
              <Ring value={stats.over15_pct ?? 65} size={80} color="var(--acc-home)" label="+ 1.5 but" />
            </div>
          )}

          {/* Form + weather */}
          {stats && (
            <div className="modal-meta-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <div className="overline">Forme recente</div>
                  <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>5 derniers</span>
                </div>
                <div className="modal-form-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, overflowWrap: "anywhere" }}>{homeTeam}</div>
                    <FormDots form={stats.home_form ?? []} size={16} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, overflowWrap: "anywhere", textAlign: "right" }}>{awayTeam}</div>
                    <div style={{ display: "flex", justifyContent: "flex-end" }}>
                      <FormDots form={stats.away_form ?? []} size={16} />
                    </div>
                  </div>
                </div>
              </div>
              {details?.weatherCode && (
                <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12, display: "flex", alignItems: "center", gap: 12 }}>
                  <I.Sun size={20} style={{ color: "var(--text-soft)", flexShrink: 0 }} />
                  <div>
                    <div className="overline" style={{ marginBottom: 2 }}>Météo prévue</div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{weatherLabel(details.weatherCode)}</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {hasAvailability && (
            <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <I.Alert size={18} style={{ color: "var(--text-soft)", flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div className="overline">Disponibilites live</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {lineupsAvailable ? "Compos officielles detectees" : "Compos non publiees"}
                    {(details?.fixtureId || availability?.fixtureId) && ` · fixture ${details?.fixtureId ?? availability?.fixtureId}`}
                    {details?.injuriesSource && ` · ${details.injuriesSource}`}
                  </div>
                </div>
              </div>

              <div className="availability-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                {[
                  { name: homeTeam, squad: homeSquad, missing: homeMissing, count: homeInjuryCount },
                  { name: awayTeam, squad: awaySquad, missing: awayMissing, count: awayInjuryCount },
                ].map(({ name, squad, missing, count }) => (
                  <div key={name} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 12, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, overflowWrap: "anywhere" }}>{name}</span>
                      <span className="mono" style={{ fontSize: 11, color: count ? "var(--bad)" : "var(--good)" }}>
                        {count} out
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                      {squad?.available_count && squad?.total_count
                        ? `${squad.available_count}/${squad.total_count} disponibles`
                        : "Effectif live partiel"}
                      {squad?.formation && ` · ${squad.formation}`}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                      {missing.length > 0 ? (
                        missing.slice(0, 4).map((player, i) => (
                          <span key={`${name}-${i}`} style={{ fontSize: 12, color: "var(--text-soft)", overflowWrap: "anywhere" }}>
                            {playerLabel(player)}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Aucune absence confirmee</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
