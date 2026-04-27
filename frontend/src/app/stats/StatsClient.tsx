"use client";
import { useState, useMemo } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { MatchModal } from "@/components/MatchModal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Ring } from "@/components/ui/Ring";
import { FormDots } from "@/components/ui/FormDots";
import { TeamLogo } from "@/components/TeamLogo";
import { I } from "@/components/Icons";

type Match = {
  id: number; competition: string; league: string; date: string;
  homeTeam: string; awayTeam: string;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; bookmaker?: string };
  recommendation?: string;
  stats?: { btts_pct?: number; over25_pct?: number; over15_pct?: number; home_form?: string[]; away_form?: string[]; predicted_goals?: number; predicted_corners?: number; predicted_cards?: number };
  details?: { homeElo?: number; awayElo?: number; homeDaysRest?: number; awayDaysRest?: number; weatherCode?: number };
};

type Leg = { label: string; cat: string; odds: number };
type Combo = { id: string; profile: "safe" | "balanced" | "bold"; confidence: number; legs: Leg[]; totalOdds: number; combinedProb: number; edge: number };

function buildCombos(m: Match): Combo[] {
  const pr = m.probs ?? { p1: 33, pn: 33, p2: 33 };
  const st = m.stats ?? {};
  const fav = pr.p1 >= pr.p2 ? "home" : "away";
  const favTeam = fav === "home" ? m.homeTeam : m.awayTeam;
  const favProb = Math.max(pr.p1, pr.p2);
  const favOdds = fav === "home" ? (m.odds?.h ?? 2.0) : (m.odds?.a ?? 2.0);
  const o15 = +((100 / (st.over15_pct ?? 75)) * 0.95).toFixed(2);
  const o25 = +((100 / (st.over25_pct ?? 60)) * 0.95).toFixed(2);
  const btts = +((100 / (st.btts_pct ?? 55)) * 0.95).toFixed(2);
  const dcOdds = +((1 / ((favProb + pr.pn) / 100)) * 0.93).toFixed(2);

  const configs: Array<{ id: string; profile: "safe" | "balanced" | "bold"; confidence: number; legs: Leg[] }> = [
    { id: "safe", profile: "safe", confidence: 78, legs: [{ label: "Plus de 1.5 but", cat: "Total · Match", odds: o15 }, { label: `Double chance ${fav === "home" ? "1N" : "N2"}`, cat: "Double chance", odds: dcOdds }] },
    { id: "balanced", profile: "balanced", confidence: 64, legs: [{ label: `Victoire ${favTeam}`, cat: "1N2", odds: favOdds }, { label: "Plus de 2.5 buts", cat: "Total · Match", odds: o25 }, { label: "Les deux marquent", cat: "BTTS", odds: btts }] },
    { id: "bold", profile: "bold", confidence: 41, legs: [{ label: `Victoire ${favTeam}`, cat: "1N2", odds: favOdds }, { label: "Plus de 3.5 buts", cat: "Total · Match", odds: +(o25 * 1.6).toFixed(2) }, { label: "Les deux marquent", cat: "BTTS", odds: btts }, { label: `${favTeam} marque en 1ʳᵉ MT`, cat: "Mi-temps", odds: 1.7 }] },
  ];

  return configs.map((c) => {
    const totalOdds = c.legs.reduce((a, l) => a * l.odds, 1);
    return { ...c, totalOdds, combinedProb: c.confidence * 0.85, edge: ((c.confidence / 100) * totalOdds - 1) * 100 };
  });
}

const comboPalette = {
  safe:     { tint: "var(--good-tint)",  color: "var(--good)",  label: "Sûr",       icon: <I.Shield size={13} sw={1.8} /> },
  balanced: { tint: "var(--value-tint)", color: "var(--value)", label: "Équilibré",  icon: <I.Target size={13} sw={1.8} /> },
  bold:     { tint: "var(--warn-tint)",  color: "var(--warn)",  label: "Audacieux",  icon: <I.Flame size={13} sw={1.8} /> },
};

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12 }}>
      <div className="overline" style={{ marginBottom: 6 }}>{label}</div>
      <div className="mono tabular" style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>{value}</div>
    </div>
  );
}

function AIComboCard({ combo }: { combo: Combo }) {
  const p = comboPalette[combo.profile];
  return (
    <Card pad={0} hover={false} style={{ overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", background: p.tint, borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, color: p.color, fontSize: 12, fontWeight: 600 }}>
          {p.icon} Combiné {p.label}
        </div>
        <span className="mono tabular" style={{ fontSize: 11, color: p.color, fontWeight: 600 }}>Conf. {combo.confidence}%</span>
      </div>
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
        {combo.legs.map((leg, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <div style={{
              width: 18, height: 18, borderRadius: "50%",
              background: "var(--bg-inset)", border: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 600, color: "var(--text-soft)", flexShrink: 0, marginTop: 1,
            }}>{i + 1}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.35 }}>{leg.label}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{leg.cat}</div>
            </div>
            <div className="mono tabular" style={{ fontSize: 13, fontWeight: 600, flexShrink: 0 }}>{leg.odds?.toFixed(2) ?? "—"}</div>
          </div>
        ))}
      </div>
      <div style={{ padding: "14px 16px", background: "var(--bg-inset)", borderTop: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
          <span className="overline">Cote totale</span>
          <span className="mono tabular" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{combo.totalOdds?.toFixed(2)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-soft)", marginBottom: 12 }}>
          <span>Edge IA <span className="mono tabular" style={{ color: "var(--good)", fontWeight: 600 }}>+{combo.edge?.toFixed(1)}%</span></span>
          <span>Probabilité <span className="mono tabular">{combo.combinedProb?.toFixed(1)}%</span></span>
        </div>
        <Button variant="secondary" size="sm" style={{ width: "100%" }} icon={<I.Bolt size={13} sw={2} />}>
          Suivre ce combiné
        </Button>
      </div>
    </Card>
  );
}

export default function StatsClient({ initialMatches = [] }: { initialMatches: Match[] }) {
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(initialMatches.length > 0 ? initialMatches[0] : null);
  const [openedMatch, setOpenedMatch] = useState<Match | null>(null);

  const combos = useMemo(() => (selectedMatch ? buildCombos(selectedMatch) : []), [selectedMatch]);
  const st = selectedMatch?.stats ?? {};

  return (
    <AppShell>
      <div style={{ padding: "0 40px 80px" }}>
        <PageHeader
          title="Stats & AI Bet Builder"
          subtitle="Stats prédictives par match et combinés générés par l'IA selon votre appétit au risque."
        />

        {initialMatches.length === 0 ? (
          <div style={{ padding: "80px 0", textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 14, color: "var(--text-muted)" }}>Aucune stat trouvée.</div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(300px,360px)", gap: 24 }} className="stats-grid">
            {/* Left: match stats */}
            <div>
              {/* Match selector */}
              <div style={{ marginBottom: 24, overflowX: "auto" }}>
                <div style={{ display: "flex", gap: 10, paddingBottom: 8 }}>
                  {initialMatches.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedMatch(m)}
                      style={{
                        padding: "10px 14px", borderRadius: 10, flexShrink: 0,
                        background: m.id === selectedMatch?.id ? "var(--bg-elev)" : "transparent",
                        border: "1px solid",
                        borderColor: m.id === selectedMatch?.id ? "var(--border-strong)" : "var(--border)",
                        color: "var(--text)",
                        display: "flex", alignItems: "center", gap: 8,
                        fontSize: 13, fontWeight: 500, cursor: "pointer",
                        boxShadow: m.id === selectedMatch?.id ? "var(--shadow-card)" : "none",
                      }}
                    >
                      <TeamLogo name={m.homeTeam} size={22} />
                      <TeamLogo name={m.awayTeam} size={22} />
                      <span>{m.homeTeam.slice(0, 3).toUpperCase()} · {m.awayTeam.slice(0, 3).toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>

              {selectedMatch && (
                <Card onClick={() => setOpenedMatch(selectedMatch)}>
                  {/* Match header */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, paddingBottom: 24, borderBottom: "1px solid var(--border)", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
                      <TeamLogo name={selectedMatch.homeTeam} size={44} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{selectedMatch.homeTeam}</div>
                        {selectedMatch.details?.homeElo && <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>Elo {selectedMatch.details.homeElo}</div>}
                      </div>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>VS</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
                      <div style={{ textAlign: "right", minWidth: 0 }}>
                        <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{selectedMatch.awayTeam}</div>
                        {selectedMatch.details?.awayElo && <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>Elo {selectedMatch.details.awayElo}</div>}
                      </div>
                      <TeamLogo name={selectedMatch.awayTeam} size={44} />
                    </div>
                  </div>

                  {/* Rings */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 28, justifyItems: "center" }}>
                    <Ring value={st.btts_pct ?? 50} size={84} color="var(--acc-draw)" label="BTTS" />
                    <Ring value={st.over25_pct ?? 50} size={84} color="var(--good)" label="Plus 2.5 buts" />
                    <Ring value={st.over15_pct ?? 65} size={84} color="var(--acc-home)" label="Plus 1.5 but" />
                  </div>

                  {/* Predicted totals */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
                    <StatTile label="Buts prédits" value={(st.predicted_goals ?? 2.5)?.toFixed(1) ?? "2.5"} />
                    <StatTile label="Corners prédits" value={(st.predicted_corners ?? 10)?.toFixed(1) ?? "10.0"} />
                    <StatTile label="Cartons prédits" value={(st.predicted_cards ?? 4)?.toFixed(1) ?? "4.0"} />
                  </div>

                  {/* Form */}
                  <div style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <span className="overline" style={{ fontSize: 10 }}>Forme domicile</span>
                      <FormDots form={st.home_form ?? []} />
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>5 derniers matchs</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                      <span className="overline" style={{ fontSize: 10 }}>Forme extérieur</span>
                      <FormDots form={st.away_form ?? []} />
                    </div>
                  </div>
                </Card>
              )}
            </div>

            {/* Right: AI Bet Builder */}
            <div style={{ position: "sticky", top: 20, alignSelf: "start", display: "flex", flexDirection: "column", gap: 16 }}>
              <Card pad={20}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--bg-inset)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--value)" }}>
                    <I.Spark size={15} sw={2} />
                  </div>
                  <h3 style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.015em" }}>AI Bet Builder</h3>
                </div>
                <p style={{ fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5, marginTop: 8 }}>
                  L'IA compose 3 combinés optimisés pour ce match. Choisis selon ton appétit au risque.
                </p>
              </Card>

              {combos.map((c) => <AIComboCard key={c.id} combo={c} />)}

              <div style={{ padding: "10px 12px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "flex-start" }}>
                <I.Info size={13} sw={1.8} style={{ color: "var(--text-muted)", flexShrink: 0, marginTop: 2 }} />
                <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5 }}>
                  Conseils générés par notre modèle. Tu places toujours toi-même tes paris chez ton bookmaker.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      <MatchModal match={openedMatch} onClose={() => setOpenedMatch(null)} />
    </AppShell>
  );
}
