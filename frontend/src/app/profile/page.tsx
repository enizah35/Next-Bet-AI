"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHeader } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { I } from "@/components/Icons";
import { useAuth } from "@/context/AuthContext";
import { logout, cancelSubscription } from "@/app/auth/actions";

function Row({ label, value, action, onAction }: { label: string; value: string; action?: string; onAction?: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
      <div style={{ flex: "0 0 140px", fontSize: 13, color: "var(--text-soft)" }}>{label}</div>
      <div style={{ flex: 1, fontSize: 14 }}>{value}</div>
      {action && (
        <button onClick={onAction} style={{ fontSize: 12, color: "var(--text)", textDecoration: "underline", textUnderlineOffset: 3, cursor: "pointer" }}>
          {action}
        </button>
      )}
    </div>
  );
}

function Toggle({ label, sub, defaultOn }: { label: string; sub: string; defaultOn?: boolean }) {
  const [on, setOn] = useState(!!defaultOn);
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{sub}</div>
      </div>
      <button
        onClick={() => setOn(!on)}
        style={{
          width: 40, height: 22, borderRadius: 100, padding: 2,
          background: on ? "var(--text)" : "var(--bg-inset)",
          border: "1px solid", borderColor: on ? "var(--text)" : "var(--border)",
          transition: "all 0.15s", flexShrink: 0, cursor: "pointer",
          display: "flex", alignItems: "center",
        }}
      >
        <div style={{
          width: 16, height: 16, borderRadius: "50%",
          background: on ? "var(--bg)" : "var(--text-muted)",
          transform: on ? "translateX(18px)" : "translateX(0)",
          transition: "transform 0.15s",
        }} />
      </button>
    </div>
  );
}

const PLAN_LABELS: Record<string, string> = {
  ligue1: "Ligue 1",
  pl: "Premier League",
  ultimate: "Ultimate",
  free: "Free",
};

export default function ProfilePage() {
  const { user, profile, loading } = useAuth();
  const router = useRouter();
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  if (loading || !user) {
    return null;
  }

  const name = profile?.full_name ?? user.email?.split("@")[0] ?? "—";
  const email = user.email ?? "—";
  const tier = (profile?.subscription_tier as string | undefined) ?? "free";
  const planLabel = PLAN_LABELS[tier] ?? tier;
  const initials = name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();

  const handleCancel = async () => {
    if (!confirm("Annuler l'abonnement ?")) return;
    setCancelling(true);
    await cancelSubscription();
    setCancelling(false);
  };

  return (
    <AppShell>
      <div style={{ padding: "0 40px 80px" }}>
        <PageHeader title="Profil" subtitle="Gère ton compte, ton abonnement et tes préférences." />

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 24, padding: "8px 0" }}>
          {/* Left column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card>
              <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 24, paddingBottom: 24, borderBottom: "1px solid var(--border)" }}>
                <div style={{
                  width: 64, height: 64, borderRadius: "50%",
                  background: "linear-gradient(135deg, var(--acc-home), var(--acc-away))",
                  color: "white", display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", flexShrink: 0,
                }}>
                  {initials}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.015em" }}>{name}</div>
                  <div style={{ fontSize: 13, color: "var(--text-soft)" }}>{email}</div>
                </div>
              </div>
              <div className="overline" style={{ marginBottom: 14 }}>Informations</div>
              <Row label="Nom" value={name} action="Modifier" />
              <Row label="E-mail" value={email} />
              <Row label="Mot de passe" value="••••••••••" action="Changer" />
              <Row label="Langue" value="Français" />
            </Card>

            <Card>
              <div className="overline" style={{ marginBottom: 2 }}>Notifications</div>
              <Toggle label="Alertes value bets par e-mail" sub="Dès qu'un edge > 7% est détecté" defaultOn />
              <Toggle label="Digest quotidien" sub="Un résumé des tips à 9h00" defaultOn />
              <Toggle label="Alertes blessures" sub="Changements de dernière minute" />
            </Card>

            <Card>
              <div className="overline" style={{ marginBottom: 14 }}>Jeu responsable</div>
              <p style={{ fontSize: 13, color: "var(--text-soft)", lineHeight: 1.55, marginBottom: 16 }}>
                Le pari sportif comporte des risques financiers. Définis des limites personnelles pour rester dans le jeu.
              </p>
              <div style={{ display: "flex", gap: 10 }}>
                <Button variant="secondary" size="sm">Limite journalière</Button>
                <Button variant="ghost" size="sm" style={{ color: "var(--bad)" }}>Auto-exclusion</Button>
              </div>
            </Card>
          </div>

          {/* Right column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card style={{ background: "var(--bg-inset)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                <Tag size="sm" color="var(--value)" tint="var(--value-tint)">{planLabel}</Tag>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {tier !== "free" ? "Actif" : "Inactif"}
                </span>
              </div>
              {tier !== "free" ? (
                <>
                  <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", marginBottom: 4 }}>
                    {tier === "ultimate" ? "16€ / mois" : "9€ / mois"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-soft)", marginBottom: 16 }}>
                    Prochain débit le 14 mai 2026
                  </div>
                  <Button variant="secondary" size="sm" style={{ width: "100%", marginBottom: 8 }} onClick={() => router.push("/pricing")}>
                    Changer de forfait
                  </Button>
                  <Button variant="ghost" size="sm" style={{ width: "100%", color: "var(--text-muted)" }} onClick={handleCancel} disabled={cancelling}>
                    {cancelling ? "Annulation…" : "Annuler l'abonnement"}
                  </Button>
                </>
              ) : (
                <>
                  <div style={{ fontSize: 13, color: "var(--text-soft)", marginBottom: 16 }}>Aucun abonnement actif.</div>
                  <Button variant="primary" size="sm" style={{ width: "100%" }} onClick={() => router.push("/pricing")}>
                    Voir les forfaits
                  </Button>
                </>
              )}
            </Card>

            <Card>
              <div className="overline" style={{ marginBottom: 12 }}>Facturation</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
                {[["14 avr 2026", "16,00€", "Payé"], ["14 mar 2026", "16,00€", "Payé"], ["14 fév 2026", "9,00€", "Payé"]].map((r, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="mono" style={{ fontSize: 12, color: "var(--text-soft)" }}>{r[0]}</span>
                    <span className="mono tabular" style={{ fontWeight: 500 }}>{r[1]}</span>
                    <Tag size="sm" color="var(--good)" tint="var(--good-tint)">{r[2]}</Tag>
                  </div>
                ))}
              </div>
            </Card>

            <form action={logout}>
              <Button variant="ghost" icon={<I.Logout size={15} />} style={{ width: "100%", color: "var(--text-soft)" }}>
                Se déconnecter
              </Button>
            </form>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
