"use client";
import React, { useState, createContext, useContext } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHeader } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

import { Segmented } from "@/components/ui/Segmented";
import { I } from "@/components/Icons";
import { useAuth } from "@/context/AuthContext";

type Cycle = "monthly" | "yearly";
const CycleCtx = createContext<Cycle>("yearly");

const PLANS = [
  {
    id: "ligue1", name: "Ligue 1", price_m: 9, price_y: 89,
    tagline: "Pour les supporters du championnat français",
    features: ["Prédictions Ligue 1 complètes", "Value Bets · détection d'edge", "Tip du jour quotidien", "Stats avancées par match", "Alertes blessures et météo"],
    featured: false,
  },
  {
    id: "pl", name: "Premier League", price_m: 9, price_y: 89,
    tagline: "Le championnat le plus couvert du marché",
    features: ["Prédictions Premier League complètes", "Value Bets · détection d'edge", "Tip du jour quotidien", "Stats avancées par match", "Alertes blessures et météo"],
    featured: false,
  },
  {
    id: "ultimate", name: "Ultimate", price_m: 16, price_y: 149,
    tagline: "Accès total · pour les passionnés",
    features: ["Tous les championnats (L1, PL, Bundesliga, Liga, Serie A)", "AI Bet Builder · combinés optimisés", "Accès API développeur", "Alertes temps réel Telegram & e-mail", "Support prioritaire", "Historique 5 ans · export CSV"],
    featured: true,
  },
];

const TABLE_ROWS: [string, string, string, string][] = [
  ["Championnats couverts", "1 (au choix)", "1 (au choix)", "5 grandes ligues"],
  ["Prédictions par match", "✓", "✓", "✓"],
  ["Value Bets quotidiens", "✓", "✓", "✓"],
  ["Tip du jour", "✓", "✓", "✓"],
  ["Stats avancées", "✓", "✓", "✓"],
  ["Alertes blessures & météo", "✓", "✓", "✓"],
  ["AI Bet Builder", "—", "—", "✓"],
  ["Alertes Telegram temps réel", "—", "—", "✓"],
  ["Accès API", "—", "—", "✓"],
  ["Historique 5 ans", "—", "—", "✓"],
  ["Support prioritaire", "—", "—", "✓"],
];

function PlanCard({ plan }: { plan: typeof PLANS[0] }) {
  const cycle = useContext(CycleCtx);
  const { user } = useAuth();
  const router = useRouter();
  const price = cycle === "monthly" ? plan.price_m : plan.price_y;
  const per = cycle === "monthly" ? "/mois" : "/an";
  const monthly = cycle === "yearly" ? (plan.price_y / 12).toFixed(2).replace(".", ",") : null;

  const handleCta = () => {
    if (!user) { router.push("/login"); return; }
    router.push(`/api/stripe/create-checkout-session?plan=${plan.id}&cycle=${cycle}`);
  };

  return (
    <Card pad={0} hover={false} style={{
      border: plan.featured ? "1.5px solid var(--text)" : "1px solid var(--border)",
      boxShadow: plan.featured ? "var(--shadow-float)" : "var(--shadow-card)",
      display: "flex", flexDirection: "column", overflow: "hidden", position: "relative",
    }}>
      {plan.featured && (
        <div style={{ position: "absolute", top: 16, right: 16, background: "var(--text)", color: "var(--bg-elev)", fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", padding: "5px 10px", borderRadius: 100, textTransform: "uppercase" }}>
          Recommandé
        </div>
      )}
      <div style={{ padding: "28px 28px 24px" }}>
        <h3 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em", marginBottom: 8 }}>{plan.name}</h3>
        <p style={{ fontSize: 13, color: "var(--text-soft)", lineHeight: 1.5, minHeight: 40 }}>{plan.tagline}</p>
      </div>
      <div style={{ padding: "0 28px 24px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 4 }}>
          <span className="mono tabular" style={{ fontSize: 48, fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1 }}>{price}€</span>
          <span style={{ fontSize: 14, color: "var(--text-muted)" }}>{per}</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", minHeight: 18 }}>
          {monthly ? `Soit ${monthly}€ par mois` : "Sans engagement"}
        </div>
      </div>
      <div style={{ padding: "0 28px 24px" }}>
        <Button variant={plan.featured ? "primary" : "secondary"} style={{ width: "100%" }} onClick={handleCta}>
          Démarrer 7 jours gratuits
        </Button>
      </div>
      <div style={{ height: 1, background: "var(--border)", margin: "0 28px" }} />
      <div style={{ padding: "24px 28px 28px", flex: 1 }}>
        <div className="overline" style={{ marginBottom: 14, fontSize: 10 }}>Inclus</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
          {plan.features.map((f, i) => (
            <div key={i} style={{ display: "flex", gap: 10, fontSize: 13.5, alignItems: "flex-start", lineHeight: 1.45 }}>
              <div style={{
                flexShrink: 0, marginTop: 2, width: 16, height: 16, borderRadius: "50%",
                background: plan.featured ? "var(--text)" : "var(--good-tint)",
                color: plan.featured ? "var(--bg-elev)" : "var(--good)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <I.Check size={10} sw={3} />
              </div>
              <span>{f}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

export default function PricingPage() {
  const [cycle, setCycle] = useState<Cycle>("yearly");

  return (
    <CycleCtx.Provider value={cycle}>
      <AppShell>
        <div className="app-page">
          <PageHeader
            overline="Forfaits"
            title="Choisis ton championnat."
            subtitle="Conseils, value bets et analyses. 7 jours d'essai gratuit, sans carte bancaire. Annulation en un clic."
            actions={
              <Segmented
                value={cycle}
                onChange={(v) => setCycle(v as Cycle)}
                options={[{ value: "monthly", label: "Mensuel" }, { value: "yearly", label: "Annuel · -17%" }]}
              />
            }
          />

          {/* Cards */}
          <div className="match-card-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: 20, padding: "20px 0", alignItems: "stretch" }}>
            {PLANS.map((p) => <PlanCard key={p.id} plan={p} />)}
          </div>

          {/* Comparison table */}
          <section style={{ marginTop: 56 }}>
            <div className="overline" style={{ marginBottom: 14 }}>Comparer en détail</div>
            <Card pad={0} hover={false} style={{ overflow: "hidden" }}>
              <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", minWidth: 620, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--bg-inset)" }}>
                    {["Fonctionnalité", "Ligue 1", "Premier League", "Ultimate"].map((h, i) => (
                      <th key={i} style={{ padding: "14px 16px", fontSize: 12, fontWeight: 600, color: i === 3 ? "var(--text)" : "var(--text-soft)", textAlign: i === 0 ? "left" : "center", borderBottom: "1px solid var(--border)", background: i === 3 ? "var(--bg)" : undefined }}>
                        {h === "Ultimate" ? (
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                            Ultimate <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--value)", display: "inline-block" }} />
                          </span>
                        ) : h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TABLE_ROWS.map(([label, c1, c2, c3], i) => (
                    <tr key={i}>
                      <td style={{ padding: "14px 16px", fontSize: 13, fontWeight: 500, borderBottom: "1px solid var(--border)" }}>{label}</td>
                      {[c1, c2, c3].map((v, j) => (
                        <td key={j} style={{ padding: "14px 16px", textAlign: "center", borderBottom: "1px solid var(--border)", background: j === 2 ? "var(--bg)" : undefined }}>
                          {v === "✓" ? <I.Check size={14} sw={2.5} style={{ color: "var(--good)" }} /> :
                           v === "—" ? <span style={{ color: "var(--text-muted)", fontSize: 16 }}>—</span> :
                           <span className="mono" style={{ fontSize: 12, color: "var(--text-soft)" }}>{v}</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </Card>
          </section>

          {/* Guarantees */}
          <section style={{ marginTop: 56 }}>
            <div className="overline" style={{ marginBottom: 16 }}>Garanties</div>
            <div className="match-card-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 16 }}>
              {([
                [<I.Lock size={18} sw={1.6} />, "Paiement sécurisé", "Stripe. Aucune donnée bancaire stockée chez nous."],
                [<I.Close size={18} sw={1.6} />, "Annulation 1-clic", "Depuis ton profil, sans e-mail ni justification."],
                [<I.Check size={18} sw={2} />, "7 jours offerts", "Accès complet. Carte demandée seulement à la fin."],
                [<I.Shield size={18} sw={1.6} />, "Jeu responsable", "Outils de limite et rappels intégrés."],
              ] as [React.ReactNode, string, string][]).map(([icon, t, d]) => (
                <Card key={t} pad={20} hover={false}>
                  <div style={{ color: "var(--text-soft)", marginBottom: 12 }}>{icon}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, letterSpacing: "-0.01em" }}>{t}</div>
                  <div style={{ fontSize: 13, color: "var(--text-soft)", lineHeight: 1.5 }}>{d}</div>
                </Card>
              ))}
            </div>
          </section>
        </div>
      </AppShell>
    </CycleCtx.Provider>
  );
}
