import React from "react";
import { Card } from "./ui/Card";
import { Tag } from "./ui/Tag";
import { TeamLogo } from "./TeamLogo";
import { I } from "./Icons";

interface MatchCardProps {
  match: {
    id: number;
    competition: string;
    date: string;
    homeTeam: string;
    awayTeam: string;
    probs: { p1: number; pn: number; p2: number };
    valueBet?: { active?: boolean; edge?: number };
    recommendation?: string;
  };
  onClick?: () => void;
}

export function MatchCard({ match, onClick }: MatchCardProps) {
  const { competition, date, homeTeam, awayTeam, probs, valueBet, recommendation } = match;
  const favorite = probs.p1 >= probs.p2 ? "home" : "away";
  const maxProb = Math.max(probs.p1, probs.pn, probs.p2);
  const dateFmt = new Date(date).toLocaleString("fr-FR", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });

  return (
    <Card className="match-card" onClick={onClick}>
      <div className="match-card-meta" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Tag size="sm">{competition}</Tag>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{dateFmt}</span>
      </div>

      <div className="match-card-teams" style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
        {(["home", "away"] as const).map((side) => {
          const name = side === "home" ? homeTeam : awayTeam;
          const pct = side === "home" ? probs.p1 : probs.p2;
          const isFav = side === favorite;
          return (
            <div key={side} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <TeamLogo name={name} size={32} />
              <div className="match-card-team-name" style={{ flex: 1, minWidth: 0, fontSize: 15, fontWeight: isFav ? 600 : 500, color: isFav ? "var(--text)" : "var(--text-soft)", letterSpacing: "-0.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {name}
              </div>
              <div
                className="mono tabular"
                style={{
                  fontSize: 15, fontWeight: 600,
                  color: isFav ? (side === "home" ? "var(--acc-home)" : "var(--acc-away)") : "var(--text-muted)",
                }}
              >
                {pct}%
              </div>
            </div>
          );
        })}
      </div>

      <div className="match-card-prob-strip">
        {[
          { label: "1", pct: probs.p1, color: "var(--acc-home)" },
          { label: "N", pct: probs.pn, color: "var(--acc-draw)" },
          { label: "2", pct: probs.p2, color: "var(--acc-away)" },
        ].map((item) => {
          const active = item.pct === maxProb;
          return (
            <div key={item.label} className={active ? "match-card-prob active" : "match-card-prob"}>
              <span>{item.label}</span>
              <strong className="mono tabular" style={{ color: active ? item.color : undefined }}>{item.pct}%</strong>
            </div>
          );
        })}
      </div>

      <div className="match-card-footer" style={{ paddingTop: 16, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        {valueBet?.active ? (
          <Tag icon={<I.Bolt size={11} />} color="var(--value)" tint="var(--value-tint)" size="sm">
            Value +{valueBet.edge}%
          </Tag>
        ) : (
          <span className="overline" style={{ fontSize: 10 }}>Pas de value</span>
        )}
        {recommendation && (
          <span style={{ minWidth: 0, fontSize: 12, color: "var(--text-soft)", textAlign: "right", overflowWrap: "anywhere" }}>{recommendation}</span>
        )}
      </div>
    </Card>
  );
}
