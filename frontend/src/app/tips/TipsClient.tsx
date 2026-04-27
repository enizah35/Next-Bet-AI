"use client";
import { useState, useMemo } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { MatchModal } from "@/components/MatchModal";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { I } from "@/components/Icons";

type Match = {
  id: number; competition: string; league: string; date: string;
  homeTeam: string; awayTeam: string;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; target?: string; bookmaker?: string };
  recommendation?: string;
  stats?: { btts_pct?: number; over25_pct?: number; over15_pct?: number; home_form?: string[]; away_form?: string[]; predicted_goals?: number; predicted_corners?: number; predicted_cards?: number };
  details?: { homeElo?: number; awayElo?: number; homeDaysRest?: number; awayDaysRest?: number; weatherCode?: number };
  injuries?: string[];
};

type Tip = {
  match: Match; category: string; label: string;
  confidence: number; odds: number; edge?: number;
};

function buildTips(matches: Match[]): Tip[] {
  const t: Tip[] = [];
  for (const m of matches) {
    const pr = m.probs ?? { p1: 33, pn: 33, p2: 33 };
    const st = m.stats ?? {};
    const dcHome = pr.p1 + pr.pn;
    const dcAway = pr.p2 + pr.pn;
    if (m.valueBet?.active && m.valueBet.edge) {
      const sel = m.valueBet.selection;
      const target = m.valueBet.target;
      const isDraw = sel === "Draw" || target === "N";
      const isAway = sel === "Away" || target === "2";
      const label = isDraw ? "Match nul" : `Victoire ${isAway ? m.awayTeam : m.homeTeam}`;
      const confidence = isDraw ? pr.pn : isAway ? pr.p2 : pr.p1;
      const odds = isDraw ? (m.odds?.d ?? m.odds?.draw) : isAway ? (m.odds?.a ?? m.odds?.away) : (m.odds?.h ?? m.odds?.home);
      t.push({ match: m, category: "Value", label, confidence, odds: odds ?? 2.0, edge: m.valueBet.edge });
    }
    if (dcHome > 70) t.push({ match: m, category: "Double chance", label: `${m.homeTeam} ou Nul`, confidence: Math.round(dcHome), odds: +((100 / dcHome) * 0.95).toFixed(2) });
    if (dcAway > 70) t.push({ match: m, category: "Double chance", label: `${m.awayTeam} ou Nul`, confidence: Math.round(dcAway), odds: +((100 / dcAway) * 0.95).toFixed(2) });
    if ((st.btts_pct ?? 0) > 60) t.push({ match: m, category: "BTTS", label: "Les deux équipes marquent", confidence: st.btts_pct!, odds: +((100 / st.btts_pct!) * 0.95).toFixed(2) });
    if ((st.over25_pct ?? 0) > 60) t.push({ match: m, category: "Goals", label: "Plus de 2.5 buts", confidence: st.over25_pct!, odds: +((100 / st.over25_pct!) * 0.95).toFixed(2) });
  }
  return t.sort((a, b) => b.confidence - a.confidence).slice(0, 12);
}

const catStyle = (c: string) => {
  if (c === "Value") return { color: "var(--value)", tint: "var(--value-tint)" };
  if (c === "Double chance") return { color: "var(--acc-home)", tint: "var(--acc-home-tint)" };
  if (c === "BTTS") return { color: "var(--acc-draw)", tint: "var(--acc-draw-tint)" };
  return { color: "var(--acc-away)", tint: "var(--acc-away-tint)" };
};
const confColor = (c: number) => c >= 80 ? "var(--good)" : c >= 70 ? "var(--acc-home)" : c >= 60 ? "var(--warn)" : "var(--bad)";

export default function TipsClient({ initialMatches = [] }: { initialMatches: Match[] }) {
  const [openedMatch, setOpenedMatch] = useState<Match | null>(null);

  const tips = useMemo(() => buildTips(initialMatches), [initialMatches]);
  const top3 = tips.slice(0, 3);
  const rest = tips.slice(3);

  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <AppShell>
      <div style={{ padding: "0 40px 80px" }}>
        <PageHeader
          overline={today}
          title="Tips du jour"
          subtitle={`${tips.length} paris recommandés, triés par fiabilité.`}
        />

        {initialMatches.length === 0 ? (
          <div style={{ padding: "80px 0", textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 14, color: "var(--text-muted)" }}>Aucun tip généré (pas de données).</div>
          </div>
        ) : (
          <>
            {/* Top 3 */}
            <section style={{ padding: "8px 0 32px" }}>
              <div className="overline" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <I.Flame size={12} style={{ color: "var(--value)" }} /> Top 3
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
                {top3.map((t, i) => {
                  const cs = catStyle(t.category);
                  return (
                    <Card key={i} onClick={() => setOpenedMatch(t.match)}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
                        <Tag color={cs.color} tint={cs.tint} size="sm">{t.category}</Tag>
                        <span className="mono tabular" style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.03em", color: confColor(t.confidence), lineHeight: 1 }}>
                          {t.confidence}<span style={{ fontSize: 16, color: "var(--text-muted)" }}>%</span>
                        </span>
                      </div>
                      <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.015em", marginBottom: 6, lineHeight: 1.25 }}>{t.label}</div>
                      <div style={{ fontSize: 13, color: "var(--text-soft)", marginBottom: 20 }}>
                        {t.match.homeTeam} <span style={{ color: "var(--text-muted)" }}>vs</span> {t.match.awayTeam}
                      </div>
                      <div style={{ paddingTop: 16, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <div className="overline" style={{ fontSize: 10, marginBottom: 2 }}>Cote</div>
                          <div className="mono tabular" style={{ fontSize: 16, fontWeight: 600 }}>{t.odds?.toFixed(2) ?? "—"}</div>
                        </div>
                        {t.edge !== undefined && (
                          <div style={{ textAlign: "right" }}>
                            <div className="overline" style={{ fontSize: 10, marginBottom: 2 }}>Edge</div>
                            <div className="mono tabular" style={{ fontSize: 16, fontWeight: 600, color: "var(--value)" }}>+{t.edge}%</div>
                          </div>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </section>

            {/* Rest */}
            {rest.length > 0 && (
              <section style={{ padding: "8px 0" }}>
                <div className="overline" style={{ marginBottom: 12 }}>Autres recommandations</div>
                <Card pad={0}>
                  {rest.map((t, i) => {
                    const cs = catStyle(t.category);
                    return (
                      <div
                        key={i}
                        onClick={() => setOpenedMatch(t.match)}
                        style={{
                          display: "grid", gridTemplateColumns: "40px 110px 1fr 80px 80px 30px",
                          padding: "14px 20px", alignItems: "center", gap: 14,
                          borderBottom: i < rest.length - 1 ? "1px solid var(--border)" : "none",
                          cursor: "pointer", transition: "background 0.15s",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-inset)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <div className="mono" style={{ fontSize: 13, color: "var(--text-muted)" }}>#{i + 4}</div>
                        <Tag color={cs.color} tint={cs.tint} size="sm">{t.category}</Tag>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 500 }}>{t.label}</div>
                          <div style={{ fontSize: 12, color: "var(--text-soft)", marginTop: 2 }}>{t.match.homeTeam} vs {t.match.awayTeam}</div>
                        </div>
                        <div className="mono tabular" style={{ fontSize: 14, fontWeight: 600, color: confColor(t.confidence), textAlign: "right" }}>{t.confidence}%</div>
                        <div className="mono tabular" style={{ fontSize: 14, fontWeight: 600, textAlign: "right" }}>{t.odds?.toFixed(2) ?? "—"}</div>
                        <I.Chevron size={14} style={{ color: "var(--text-muted)" }} />
                      </div>
                    );
                  })}
                </Card>
              </section>
            )}
          </>
        )}
      </div>
      <MatchModal match={openedMatch} onClose={() => setOpenedMatch(null)} />
    </AppShell>
  );
}
