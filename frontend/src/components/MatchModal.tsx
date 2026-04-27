"use client";
import React, { useEffect } from "react";
import { TeamLogo } from "./TeamLogo";
import { Tag } from "./ui/Tag";
import { ProbBar } from "./ui/ProbBar";
import { Ring } from "./ui/Ring";
import { FormDots } from "./ui/FormDots";
import { I } from "./Icons";

interface Match {
  id: number;
  competition: string;
  date: string;
  homeTeam: string;
  awayTeam: string;
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
  };
}

const weatherLabel = (code?: number) =>
  code === 1 ? "Dégagé" : code === 2 ? "Partiellement nuageux" : code === 3 ? "Pluie" : "—";

const getOdd = (match: Match, key: "h" | "d" | "a") => {
  const legacy = key === "h" ? "home" : key === "d" ? "draw" : "away";
  return match.odds?.[key] ?? match.odds?.[legacy];
};

const getFairOdd = (match: Match) => {
  const selection = match.valueBet?.selection;
  const target = match.valueBet?.target;
  const pct =
    selection === "Away" || target === "2" ? match.probs.p2 :
    selection === "Draw" || target === "N" ? match.probs.pn :
    match.probs.p1;
  return pct > 0 ? 100 / pct : undefined;
};

export function MatchModal({ match, onClose }: { match: Match | null; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  if (!match) return null;

  const { competition, date, homeTeam, awayTeam, probs, valueBet, stats, details } = match;
  const displayedOdd = valueBet?.bestOdds ?? getOdd(match, "h");
  const fairOdd = getFairOdd(match);
  const fmt = new Date(date).toLocaleString("fr-FR", { weekday: "long", day: "2-digit", month: "long", hour: "2-digit", minute: "2-digit" });

  return (
    <div
      onClick={onClose}
      className="fade-up"
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,0.5)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-elev)", border: "1px solid var(--border)",
          borderRadius: 20, maxWidth: 720, width: "100%",
          maxHeight: "90vh", overflowY: "auto",
          boxShadow: "var(--shadow-float)", position: "relative",
        }}
      >
        {/* Close */}
        <button
          onClick={onClose}
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
        <div style={{ padding: 28, borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <Tag size="sm">{competition}</Tag>
            <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmt}</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
              <TeamLogo name={homeTeam} size={52} />
              <div>
                <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{homeTeam}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {details?.homeElo && `Elo ${details.homeElo}`}
                  {details?.homeDaysRest && ` · ${details.homeDaysRest}j repos`}
                </div>
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>VS</div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, justifyContent: "flex-end" }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{awayTeam}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {details?.awayElo && `Elo ${details.awayElo}`}
                  {details?.awayDaysRest && ` · ${details.awayDaysRest}j repos`}
                </div>
              </div>
              <TeamLogo name={awayTeam} size={52} />
            </div>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
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
                {match.recommendation}
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
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, justifyItems: "center" }}>
              <Ring value={stats.btts_pct ?? 50} size={80} color="var(--acc-draw)" label="BTTS" />
              <Ring value={stats.over25_pct ?? 50} size={80} color="var(--good)" label="+ 2.5 buts" />
              <Ring value={stats.over15_pct ?? 65} size={80} color="var(--acc-home)" label="+ 1.5 but" />
            </div>
          )}

          {/* Form + weather */}
          {stats && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12 }}>
                <div className="overline" style={{ marginBottom: 10 }}>Forme</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <FormDots form={stats.home_form ?? []} size={16} />
                  <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>5</span>
                  <FormDots form={stats.away_form ?? []} size={16} />
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
        </div>
      </div>
    </div>
  );
}
