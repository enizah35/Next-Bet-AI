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
  const dateFmt = new Date(date).toLocaleString("fr-FR", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });

  return (
    <Card onClick={onClick}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Tag size="sm">{competition}</Tag>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{dateFmt}</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
        {(["home", "away"] as const).map((side) => {
          const name = side === "home" ? homeTeam : awayTeam;
          const pct = side === "home" ? probs.p1 : probs.p2;
          const isFav = side === favorite;
          return (
            <div key={side} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <TeamLogo name={name} size={32} />
              <div style={{ flex: 1, fontSize: 15, fontWeight: isFav ? 600 : 500, color: isFav ? "var(--text)" : "var(--text-soft)", letterSpacing: "-0.01em" }}>
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

      <div style={{ paddingTop: 16, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        {valueBet?.active ? (
          <Tag icon={<I.Bolt size={11} />} color="var(--value)" tint="var(--value-tint)" size="sm">
            Value +{valueBet.edge}%
          </Tag>
        ) : (
          <span className="overline" style={{ fontSize: 10 }}>Pas de value</span>
        )}
        {recommendation && (
          <span style={{ fontSize: 12, color: "var(--text-soft)" }}>{recommendation}</span>
        )}
      </div>
    </Card>
  );
}
