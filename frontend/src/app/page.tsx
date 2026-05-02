"use client";
import { useState } from "react";
import Link from "next/link";
import { I } from "@/components/Icons";
import { BrandLockup } from "@/components/BrandLockup";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { Stat } from "@/components/ui/Stat";
import { ProbBar } from "@/components/ui/ProbBar";
import { TeamLogo } from "@/components/TeamLogo";
import { useTheme } from "@/context/ThemeContext";

const TRACK_RECORD = {
  accuracy_30d: 58.2,
  roi_30d: 12.4,
  total_predictions: 10666,
  best_streak: 9,
};

function FAQ({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", padding: "20px 0",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 16, fontWeight: 500, textAlign: "left", color: "var(--text)", cursor: "pointer",
        }}
      >
        {q}
        <div style={{ transform: open ? "rotate(45deg)" : "none", transition: "transform 0.2s", flexShrink: 0 }}>
          <I.Plus size={18} />
        </div>
      </button>
      {open && (
        <div style={{ paddingBottom: 20, color: "var(--text-soft)", fontSize: 14, lineHeight: 1.6, maxWidth: 620 }}>
          {a}
        </div>
      )}
    </div>
  );
}

export default function LandingPage() {
  const { mode, toggleMode } = useTheme();

  return (
    <div style={{ background: "var(--bg)", minHeight: "100vh" }}>
      {/* Nav */}
      <div className="landing-nav" style={{ maxWidth: 1200, margin: "0 auto", padding: "0 40px", display: "flex", justifyContent: "space-between", alignItems: "center", height: 64 }}>
        <BrandLockup size={18} />
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            onClick={toggleMode}
            style={{
              width: 36, height: 36, borderRadius: 10,
              background: "var(--bg-elev)", border: "1px solid var(--border)",
              color: "var(--text-soft)", display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", boxShadow: "var(--shadow-card)",
            }}
          >
            {mode === "light" ? <I.Moon size={15} /> : <I.Sun size={15} />}
          </button>
          <Link href="/login"><Button size="sm" variant="ghost">Se connecter</Button></Link>
          <Link href="/pricing"><Button size="sm" variant="primary">Essai 7 jours</Button></Link>
        </div>
      </div>

      <div className="landing-page">
        {/* Live badge */}
        <div style={{ padding: "16px 0 40px" }}>
          <Tag
            icon={<div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--good)", boxShadow: "0 0 8px var(--good)" }} />}
            size="sm"
          >
            Live · matchs analysés cette semaine
          </Tag>
        </div>

        {/* Hero */}
        <section className="fade-up" style={{ marginBottom: 80, textAlign: "center", maxWidth: 900, margin: "0 auto 80px" }}>
          <h1 style={{ fontSize: "clamp(40px,6vw,62px)", fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1, marginBottom: 24 }}>
            Prédictions football<br />
            <span style={{ color: "var(--text-muted)" }}>calibrées par l'IA.</span>
          </h1>
          <p style={{ fontSize: 18, color: "var(--text-soft)", lineHeight: 1.5, maxWidth: 620, margin: "0 auto 36px" }}>
            10 666 matchs d'entraînement. 14 features sélectionnées. Un modèle qui bat la baseline du marché de 3 points sur la Ligue 1 et la Premier League.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/dashboard">
              <Button size="lg" variant="primary" trailingIcon={<I.Arrow size={16} />}>Voir les analyses live</Button>
            </Link>
            <Link href="/pricing">
              <Button size="lg" variant="secondary">Démarrer — 7 jours gratuits</Button>
            </Link>
          </div>
        </section>

        {/* Track record */}
        <section style={{
          padding: "28px 32px", marginBottom: 64,
          background: "var(--bg-elev)", border: "1px solid var(--border)",
          borderRadius: 20, boxShadow: "var(--shadow-card)",
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 32,
        }}>
          <Stat label="Accuracy (30j)" value={`${TRACK_RECORD.accuracy_30d}%`} sub="vs 52.1% baseline" color="var(--good)" />
          <Stat label="ROI Value Bets" value={`+${TRACK_RECORD.roi_30d}%`} sub="sur 30 jours" color="var(--value)" />
          <Stat label="Matchs analysés" value={TRACK_RECORD.total_predictions.toLocaleString("fr-FR")} sub="5 ligues · 15 saisons" />
          <Stat label="Meilleure série" value={TRACK_RECORD.best_streak} sub="prédictions justes" />
        </section>

        {/* Featured demo */}
        <section style={{ marginBottom: 80 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
            <div>
              <div className="overline" style={{ marginBottom: 6 }}>Aperçu — Match à venir</div>
              <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em" }}>Une carte match, un verdict clair.</h2>
            </div>
            <Link href="/dashboard"><Button variant="ghost" size="sm" trailingIcon={<I.Arrow size={14} />}>Tous les matchs</Button></Link>
          </div>

          <Card pad={0} style={{ overflow: "hidden" }}>
            <div className="landing-demo-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) clamp(280px,30vw,360px)" }}>
              <div className="landing-demo-main" style={{ padding: 32, borderRight: "1px solid var(--border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                  <Tag size="sm">Premier League</Tag>
                  <span className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>Dim 19 avr · 17:30</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 28 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
                    <TeamLogo name="Man City" size={52} />
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em" }}>Man City</div>
                      <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Elo 1942</div>
                    </div>
                  </div>
                  <div className="mono" style={{ fontSize: 13, color: "var(--text-muted)", letterSpacing: "0.15em" }}>VS</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, justifyContent: "flex-end" }}>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em" }}>Arsenal</div>
                      <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Elo 1898</div>
                    </div>
                    <TeamLogo name="Arsenal" size={52} />
                  </div>
                </div>
                <div className="overline" style={{ marginBottom: 10 }}>Probabilités IA</div>
                <ProbBar p1={48} pn={24} p2={28} height={10} />
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
                  <span className="mono tabular" style={{ fontSize: 13, fontWeight: 600, color: "var(--acc-home)" }}>● 48% Man City</span>
                  <span className="mono tabular" style={{ fontSize: 13, color: "var(--text-soft)" }}>● Nul 24%</span>
                  <span className="mono tabular" style={{ fontSize: 13, fontWeight: 600, color: "var(--acc-away)" }}>● 28% Arsenal</span>
                </div>
              </div>
              <div className="landing-demo-side" style={{ padding: 32, background: "var(--bg-inset)", display: "flex", flexDirection: "column", gap: 16 }}>
                <Tag icon={<I.Bolt size={12} />} size="sm" color="var(--value)" tint="var(--value-tint)">Value bet détecté</Tag>
                <div>
                  <div className="overline" style={{ marginBottom: 6 }}>Recommandation</div>
                  <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", marginBottom: 4 }}>Victoire Man City</div>
                  <div style={{ fontSize: 13, color: "var(--text-soft)" }}>
                    Edge <span style={{ color: "var(--value)", fontWeight: 600 }}>+8.4%</span> sur Winamax
                  </div>
                </div>
                <div style={{ paddingTop: 12, borderTop: "1px solid var(--border)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <div className="overline" style={{ fontSize: 10, marginBottom: 4 }}>Cote marché</div>
                    <div className="mono tabular" style={{ fontSize: 18, fontWeight: 600 }}>2.15</div>
                  </div>
                  <div>
                    <div className="overline" style={{ fontSize: 10, marginBottom: 4 }}>Cote juste (IA)</div>
                    <div className="mono tabular" style={{ fontSize: 18, fontWeight: 600, color: "var(--value)" }}>2.08</div>
                  </div>
                </div>
                <Link href="/dashboard" style={{ marginTop: "auto" }}>
                  <Button variant="value" style={{ width: "100%" }} trailingIcon={<I.Arrow size={14} />}>Voir l'analyse</Button>
                </Link>
              </div>
            </div>
          </Card>
        </section>

        {/* Features */}
        <section style={{ marginBottom: 80 }}>
          <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 32 }}>
            Comment on trouve le signal dans le bruit.
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {[
              ["01", "Ingestion live", "Cotes, blessures, xG Understat et météo locale. Mis à jour toutes les 15 minutes."],
              ["02", "Modèle ensemble", "XGBoost (depth=4) + réseau de neurones PyTorch avec stacking."],
              ["03", "Edge vs marché", "On affiche uniquement les écarts > 5% entre probabilité réelle et cote bookmaker."],
            ].map(([num, title, body]) => (
              <div key={num} style={{ padding: 28, borderRadius: 16, background: "var(--bg-elev)", border: "1px solid var(--border)", boxShadow: "var(--shadow-card)" }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16, letterSpacing: "0.1em" }}>{num}</div>
                <h3 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", marginBottom: 8 }}>{title}</h3>
                <p style={{ fontSize: 14, color: "var(--text-soft)", lineHeight: 1.55 }}>{body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section style={{ maxWidth: 720, margin: "0 auto 80px" }}>
          <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 24 }}>Questions fréquentes</h2>
          {([
            ["Quel est le taux de réussite du modèle ?", "Le modèle v2.4 atteint 55.8% d'accuracy moyenne sur 10 666 matchs historiques, et 58.2% sur les 30 derniers jours. La baseline marché plafonne à ~52%."],
            ["Sur quelles ligues fonctionne-t-il ?", "Premier League, Ligue 1, Bundesliga, Liga et Serie A. Les modèles sont calibrés séparément par championnat."],
            ["C'est quoi un Value Bet ?", "Un écart mathématique entre la probabilité calculée par notre IA et la probabilité implicite de la cote bookmaker. On ne remonte que les edges > 5%."],
            ["Puis-je essayer gratuitement ?", "Oui — 7 jours d'essai sur tous les forfaits, sans carte bancaire demandée à l'inscription."],
          ] as [string, string][]).map(([q, a]) => <FAQ key={q} q={q} a={a} />)}
        </section>

        {/* Footer CTA */}
        <section style={{ padding: 48, borderRadius: 24, background: "var(--bg-elev)", border: "1px solid var(--border)", textAlign: "center" }}>
          <h2 style={{ fontSize: "clamp(28px,4vw,38px)", fontWeight: 600, letterSpacing: "-0.03em", marginBottom: 16, lineHeight: 1.05 }}>
            Prêt à parier sur des chiffres ?
          </h2>
          <p style={{ fontSize: 16, color: "var(--text-soft)", marginBottom: 28, maxWidth: 460, margin: "0 auto 28px" }}>
            7 jours gratuits. Sans engagement. Annulation en un clic.
          </p>
          <Link href="/pricing">
            <Button size="lg" variant="primary" trailingIcon={<I.Arrow size={16} />}>Voir les forfaits</Button>
          </Link>
        </section>
      </div>
    </div>
  );
}
