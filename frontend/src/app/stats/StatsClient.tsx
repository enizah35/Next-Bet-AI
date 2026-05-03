"use client";
import { useEffect, useMemo, useState } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { MatchModal } from "@/components/MatchModal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Ring } from "@/components/ui/Ring";
import { FormDots } from "@/components/ui/FormDots";
import { TeamLogo } from "@/components/TeamLogo";
import { I } from "@/components/Icons";
import { LiveStatusPill } from "@/components/LiveStatusPill";
import { PredictionLoading } from "@/components/PredictionLoading";
import { useLiveMatches, type MatchLiveStatus } from "@/hooks/useLiveMatches";

type Match = {
  id: number; competition: string; league: string; date: string;
  homeTeam: string; awayTeam: string;
  homeLogo?: string | null; awayLogo?: string | null;
  probs: { p1: number; pn: number; p2: number };
  odds?: { h?: number; d?: number; a?: number; home?: number; draw?: number; away?: number };
  valueBet?: { active?: boolean; edge?: number; selection?: string; bookmaker?: string };
  recommendation?: string;
  stats?: { btts_pct?: number; over25_pct?: number; over15_pct?: number; home_form?: string[]; away_form?: string[]; predicted_goals?: number; predicted_corners?: number; predicted_cards?: number };
  betBuilder?: BetBuilder;
  details?: { homeElo?: number; awayElo?: number; homeDaysRest?: number; awayDaysRest?: number; weatherCode?: number };
  liveStatus?: MatchLiveStatus;
};

type BetBuilderSelection = {
  key?: string;
  label_fr?: string;
  label?: string;
  category?: string;
  confidence?: number;
  odds?: number;
  bookmaker?: string;
  odds_source?: string;
};
type BetBuilderCombo = {
  id?: string;
  profile?: string;
  label?: string;
  rationale?: string;
  confidence_range?: { min?: number; max?: number; label?: string };
  selections?: BetBuilderSelection[];
  combined_odds?: number;
  combined_confidence?: number;
  combined_probability?: number;
  edge?: number;
  source?: string;
  method?: string;
};
type BetBuilder = {
  selections?: BetBuilderSelection[];
  combos?: BetBuilderCombo[];
  combined_odds?: number;
  combined_confidence?: number;
  source?: string;
  profile?: string;
};
type Leg = { key?: string; label: string; cat: string; odds: number; confidence?: number; bookmaker?: string; oddsSource?: string };
type Combo = {
  id: string;
  profile: "safe" | "balanced" | "bold";
  confidence: number;
  legs: Leg[];
  totalOdds: number;
  combinedProb: number;
  edge: number;
  rationale?: string;
  rangeLabel?: string;
  source?: string;
  method?: string;
};

function buildCombos(m: Match): Combo[] {
  return buildRealCombos(m);
}

function clampPct(value: number) {
  return Math.max(1, Math.min(100, Number.isFinite(value) ? value : 50));
}

function backendLeg(selection: BetBuilderSelection, index: number): Leg {
  const confidence = clampPct(selection.confidence ?? 50);
  return {
    key: selection.key ?? `leg-${index}`,
    label: selection.label_fr ?? selection.label ?? "Selection IA",
    cat: selection.category ?? "Marche",
    odds: selection.odds && selection.odds > 1 ? selection.odds : 0,
    confidence,
    bookmaker: selection.bookmaker || undefined,
    oddsSource: selection.odds_source,
  };
}

function normalizeProfile(profile: string | undefined, index: number): Combo["profile"] {
  if (profile === "safe" || profile === "balanced" || profile === "bold") return profile;
  return (["safe", "balanced", "bold"] as const)[index] ?? "balanced";
}

function backendComboToCombo(combo: BetBuilderCombo, index: number): Combo | null {
  const legs = combo.selections
    ?.map(backendLeg)
    .filter((leg) => leg.odds >= 1.05 && (leg.confidence ?? 0) >= 20) ?? [];

  if (legs.length < 2) return null;

  const totalOdds = combo.combined_odds && combo.combined_odds >= 1.05
    ? combo.combined_odds
    : +legs.reduce((acc, leg) => acc * leg.odds, 1).toFixed(2);
  const productProb = legs.reduce((acc, leg) => acc * (clampPct(leg.confidence ?? 50) / 100), 1) * 100;
  const combinedProb = combo.combined_probability ?? combo.combined_confidence ?? +productProb.toFixed(1);
  const edge = combo.edge ?? +(((combinedProb / 100) * totalOdds - 1) * 100).toFixed(1);

  return {
    id: combo.id ?? `ai-combo-${index}`,
    profile: normalizeProfile(combo.profile ?? combo.id, index),
    confidence: Math.round(clampPct(combinedProb)),
    legs,
    totalOdds,
    combinedProb,
    edge,
    rationale: combo.rationale,
    rangeLabel: combo.confidence_range?.label ?? combo.label,
    source: combo.source,
    method: combo.method,
  };
}

function buildRealCombos(m: Match): Combo[] {
  const aiCombos = m.betBuilder?.combos
    ?.map(backendComboToCombo)
    .filter(Boolean) as Combo[] | undefined;

  return aiCombos?.slice(0, 3) ?? [];
}

const comboPalette = {
  safe:     { tint: "var(--good-tint)",  color: "var(--good)",  label: "66-100%", icon: <I.Shield size={13} sw={1.8} /> },
  balanced: { tint: "var(--value-tint)", color: "var(--value)", label: "33-66%",  icon: <I.Target size={13} sw={1.8} /> },
  bold:     { tint: "var(--warn-tint)",  color: "var(--warn)",  label: "0-33%",   icon: <I.Flame size={13} sw={1.8} /> },
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
  const rangeLabel = combo.rangeLabel ?? p.label;
  const edgePrefix = combo.edge >= 0 ? "+" : "";
  const edgeColor = combo.edge >= 0 ? "var(--good)" : "var(--text-muted)";
  const totalOddsLabel = combo.source === "ai_model" ? "Cote juste IA" : "Cote totale";
  return (
    <Card className="ai-combo-card" pad={0} hover={false} style={{ overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", background: p.tint, borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, color: p.color, fontSize: 12, fontWeight: 600 }}>
          {p.icon} Combiné {rangeLabel}
        </div>
        <span className="mono tabular" style={{ fontSize: 11, color: p.color, fontWeight: 600 }}>Conf. {combo.confidence}%</span>
      </div>
      {combo.rationale && (
        <div style={{ padding: "10px 16px 0", fontSize: 11, color: "var(--text-soft)", lineHeight: 1.45 }}>
          {combo.rationale}
        </div>
      )}
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
        {combo.legs.map((leg, i) => {
          const sourceLabel = leg.bookmaker ?? (leg.oddsSource === "model_fair" ? "Cote IA" : "");

          return (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <div style={{
              width: 18, height: 18, borderRadius: "50%",
              background: "var(--bg-inset)", border: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 600, color: "var(--text-soft)", flexShrink: 0, marginTop: 1,
            }}>{i + 1}</div>
            <div style={{ flex: 1 }}>
              <div className="ai-combo-leg-label" style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.35 }}>{leg.label}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {leg.cat}
                {leg.confidence ? ` · ${Math.round(leg.confidence)}%` : ""}
                {sourceLabel ? ` · ${sourceLabel}` : ""}
              </div>
            </div>
            <div className="mono tabular" style={{ fontSize: 13, fontWeight: 600, flexShrink: 0 }}>{leg.odds?.toFixed(2) ?? "—"}</div>
          </div>
          );
        })}
      </div>
      <div style={{ padding: "14px 16px", background: "var(--bg-inset)", borderTop: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
          <span className="overline">{totalOddsLabel}</span>
          <span className="mono tabular" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{combo.totalOdds?.toFixed(2)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-soft)", marginBottom: 12 }}>
          <span>Edge IA <span className="mono tabular" style={{ color: edgeColor, fontWeight: 600 }}>{edgePrefix}{combo.edge?.toFixed(1)}%</span></span>
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
  const { matches: liveMatches, state: liveState } = useLiveMatches<Match>(initialMatches, 300);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(initialMatches[0]?.id ?? null);
  const [openedMatch, setOpenedMatch] = useState<Match | null>(null);

  useEffect(() => {
    if (liveMatches.length === 0) {
      setSelectedMatchId(null);
      return;
    }
    if (!liveMatches.some((match) => match.id === selectedMatchId)) {
      setSelectedMatchId(liveMatches[0].id);
    }
  }, [liveMatches, selectedMatchId]);

  const selectedMatch = useMemo(
    () => liveMatches.find((match) => match.id === selectedMatchId) ?? liveMatches[0] ?? null,
    [liveMatches, selectedMatchId],
  );

  const combos = useMemo(() => (selectedMatch ? buildCombos(selectedMatch) : []), [selectedMatch]);
  const st = selectedMatch?.stats ?? {};
  const isLoadingPredictions = liveMatches.length === 0 && (liveState === "refreshing" || liveState === "stale");

  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          title="Stats & AI Bet Builder"
          actions={<LiveStatusPill state={liveState} />}
          subtitle={isLoadingPredictions ? "Chargement des stats prédictives en cours." : "Stats prédictives par match et combinés générés par l'IA selon votre appétit au risque."}
        />

        {isLoadingPredictions ? (
          <PredictionLoading
            title="Chargement des stats"
            subtitle="Les données de matchs et les combinés vont apparaître automatiquement."
            rows={3}
          />
        ) : liveMatches.length === 0 ? (
          <div style={{ padding: "80px 0", textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 14, color: "var(--text-muted)" }}>Aucune stat trouvée.</div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(300px,360px)", gap: 24 }} className="stats-grid">
            {/* Left: match stats */}
            <div>
              {/* Match selector */}
              <div className="stats-match-selector" style={{ marginBottom: 24, overflowX: "auto" }}>
                <div className="stats-match-selector-track" style={{ display: "flex", gap: 10, paddingBottom: 8 }}>
                  {liveMatches.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedMatchId(m.id)}
                      className={m.id === selectedMatch?.id ? "stats-match-pill active" : "stats-match-pill"}
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
                      <TeamLogo name={m.homeTeam} logoUrl={m.homeLogo} size={22} />
                      <TeamLogo name={m.awayTeam} logoUrl={m.awayLogo} size={22} />
                      <span>{m.homeTeam.slice(0, 3).toUpperCase()} · {m.awayTeam.slice(0, 3).toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>

              {selectedMatch && (
                <Card onClick={() => setOpenedMatch(selectedMatch)}>
                  {/* Match header */}
                  <div className="stats-match-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, paddingBottom: 24, borderBottom: "1px solid var(--border)", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
                      <TeamLogo name={selectedMatch.homeTeam} logoUrl={selectedMatch.homeLogo} size={44} />
                      <div style={{ minWidth: 0 }}>
                        <div className="stats-team-name" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{selectedMatch.homeTeam}</div>
                        {selectedMatch.details?.homeElo && <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>Elo {selectedMatch.details.homeElo}</div>}
                      </div>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>VS</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
                      <div style={{ textAlign: "right", minWidth: 0 }}>
                        <div className="stats-team-name" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{selectedMatch.awayTeam}</div>
                        {selectedMatch.details?.awayElo && <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>Elo {selectedMatch.details.awayElo}</div>}
                      </div>
                      <TeamLogo name={selectedMatch.awayTeam} logoUrl={selectedMatch.awayLogo} size={44} />
                    </div>
                  </div>

                  {/* Rings */}
                  <div className="stats-rings-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 28, justifyItems: "center" }}>
                    <Ring value={st.btts_pct ?? 50} size={84} color="var(--acc-draw)" label="BTTS" />
                    <Ring value={st.over25_pct ?? 50} size={84} color="var(--good)" label="Plus 2.5 buts" />
                    <Ring value={st.over15_pct ?? 65} size={84} color="var(--acc-home)" label="Plus 1.5 but" />
                  </div>

                  {/* Predicted totals */}
                  <div className="stats-tiles-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
                    <StatTile label="Buts prédits" value={(st.predicted_goals ?? 2.5)?.toFixed(1) ?? "2.5"} />
                    <StatTile label="Corners prédits" value={(st.predicted_corners ?? 10)?.toFixed(1) ?? "10.0"} />
                    <StatTile label="Cartons prédits" value={(st.predicted_cards ?? 4)?.toFixed(1) ?? "4.0"} />
                  </div>

                  {/* Form */}
                  <div className="stats-form-panel" style={{ padding: 16, background: "var(--bg-inset)", borderRadius: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
            <div className="stats-builder-panel" style={{ position: "sticky", top: 20, alignSelf: "start", display: "flex", flexDirection: "column", gap: 16 }}>
              <Card pad={20}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--bg-inset)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--value)" }}>
                    <I.Spark size={15} sw={2} />
                  </div>
                  <h3 style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.015em" }}>AI Bet Builder</h3>
                </div>
                <p style={{ fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5, marginTop: 8 }}>
                  L'IA compose 3 combinés réfléchis par tranche de confiance: 66-100%, 33-66% et 0-33%.
                </p>
              </Card>

              {combos.length > 0 ? (
                combos.map((c) => <AIComboCard key={c.id} combo={c} />)
              ) : (
                <Card pad={20}>
                  <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
                    Aucun combine IA fiable pour ce match: le moteur n'a pas assez de marches compatibles.
                  </div>
                </Card>
              )}

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
