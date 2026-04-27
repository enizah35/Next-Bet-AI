"use client";
import { useState, useEffect, useCallback } from "react";
import { AppShell, PageHeader } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { I } from "@/components/Icons";

const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").trim();

type Prediction = {
  id: number;
  homeTeam: string;
  awayTeam: string;
  league: string;
  matchDate: string | null;
  prediction: string;
  tipType: string;
  confidence: number;
  odds: number | null;
  probHome: number | null;
  probDraw: number | null;
  probAway: number | null;
  actualResult: string | null;
  actualHomeGoals: number | null;
  actualAwayGoals: number | null;
  isWon: boolean | null;
  createdAt: string | null;
  verifiedAt: string | null;
  hasFeaturesJson: boolean;
};

type EditState = {
  actual_result: string;
  actual_home_goals: string;
  actual_away_goals: string;
};

function statusColor(isWon: boolean | null) {
  if (isWon === true) return "var(--acc-home)";
  if (isWon === false) return "#ef4444";
  return "var(--text-muted)";
}

function statusLabel(isWon: boolean | null) {
  if (isWon === true) return "Gagné";
  if (isWon === false) return "Perdu";
  return "En attente";
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function tipLabel(tipType: string) {
  const map: Record<string, string> = {
    match_result_home: "1 (Domicile)",
    match_result_away: "2 (Extérieur)",
    double_chance_home: "1N",
    double_chance_away: "N2",
    over_25: "Plus de 2.5",
    over_15: "Plus de 1.5",
    btts: "BTTS",
    result: "Résultat",
  };
  return map[tipType] ?? tipType;
}

export default function AdminClient() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "verified">("all");
  const [editing, setEditing] = useState<Record<number, EditState>>({});
  const [saving, setSaving] = useState<Record<number, boolean>>({});
  const [autoVerifying, setAutoVerifying] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [retrainLog, setRetrainLog] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/predictions?limit=300`);
      const data = await res.json();
      setPredictions(data.predictions ?? []);
    } catch {
      showToast("Erreur de chargement des prédictions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = predictions.filter((p) => {
    if (filter === "pending") return p.isWon === null;
    if (filter === "verified") return p.isWon !== null;
    return true;
  });

  const stats = {
    total: predictions.length,
    pending: predictions.filter((p) => p.isWon === null).length,
    won: predictions.filter((p) => p.isWon === true).length,
    lost: predictions.filter((p) => p.isWon === false).length,
    withFeatures: predictions.filter((p) => p.hasFeaturesJson).length,
  };

  function startEdit(p: Prediction) {
    setEditing((prev) => ({
      ...prev,
      [p.id]: {
        actual_result: p.actualResult ?? "",
        actual_home_goals: p.actualHomeGoals != null ? String(p.actualHomeGoals) : "",
        actual_away_goals: p.actualAwayGoals != null ? String(p.actualAwayGoals) : "",
      },
    }));
  }

  function cancelEdit(id: number) {
    setEditing((prev) => { const n = { ...prev }; delete n[id]; return n; });
  }

  async function save(p: Prediction) {
    const e = editing[p.id];
    if (!e) return;
    setSaving((prev) => ({ ...prev, [p.id]: true }));
    try {
      const body: Record<string, unknown> = {};
      if (e.actual_result) body.actual_result = e.actual_result;
      if (e.actual_home_goals !== "") body.actual_home_goals = parseInt(e.actual_home_goals);
      if (e.actual_away_goals !== "") body.actual_away_goals = parseInt(e.actual_away_goals);

      const res = await fetch(`${API}/admin/predictions/${p.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Erreur");

      setPredictions((prev) =>
        prev.map((x) =>
          x.id === p.id
            ? {
                ...x,
                actualResult: e.actual_result || x.actualResult,
                actualHomeGoals: e.actual_home_goals !== "" ? parseInt(e.actual_home_goals) : x.actualHomeGoals,
                actualAwayGoals: e.actual_away_goals !== "" ? parseInt(e.actual_away_goals) : x.actualAwayGoals,
                isWon: data.isWon,
                verifiedAt: new Date().toISOString(),
              }
            : x
        )
      );
      cancelEdit(p.id);
      showToast(`Prédiction #${p.id} mise à jour`);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Erreur de sauvegarde");
    } finally {
      setSaving((prev) => ({ ...prev, [p.id]: false }));
    }
  }

  async function autoVerify() {
    setAutoVerifying(true);
    try {
      const res = await fetch(`${API}/predictions/verify`, { method: "POST" });
      const data = await res.json();
      showToast(data.message ?? `${data.verified} prédiction(s) vérifiée(s)`);
      await load();
    } catch {
      showToast("Erreur lors de la vérification automatique");
    } finally {
      setAutoVerifying(false);
    }
  }

  async function retrain() {
    setRetraining(true);
    setRetrainLog(null);
    try {
      const res = await fetch(`${API}/admin/retrain`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast("Réentraînement terminé avec succès");
        setRetrainLog(data.stdout || "OK");
      } else {
        showToast("Réentraînement échoué — voir les logs");
        setRetrainLog((data.stderr || data.error || "") + "\n" + (data.stdout || ""));
      }
    } catch {
      showToast("Erreur lors du réentraînement");
    } finally {
      setRetraining(false);
    }
  }

  return (
    <AppShell>
      <div style={{ padding: "0 40px 80px" }}>
        <PageHeader
          overline="Administration"
          title="Vérification des prédictions"
          subtitle={`${stats.total} prédictions · ${stats.pending} en attente · ${stats.withFeatures} avec features (feedback loop)`}
          actions={
            <div style={{ display: "flex", gap: 10 }}>
              <Button
                variant="secondary"
                size="sm"
                icon={<I.Check size={14} />}
                onClick={autoVerify}
                disabled={autoVerifying}
              >
                {autoVerifying ? "Vérification..." : "Auto-vérifier"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<I.Spark size={14} />}
                onClick={retrain}
                disabled={retraining}
              >
                {retraining ? "Réentraînement..." : "Réentraîner le modèle"}
              </Button>
            </div>
          }
        />

        {/* Stats bar */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Total", value: stats.total, color: "var(--text)" },
            { label: "En attente", value: stats.pending, color: "var(--text-muted)" },
            { label: "Gagnés", value: stats.won, color: "var(--acc-home)" },
            { label: "Perdus", value: stats.lost, color: "#ef4444" },
          ].map((s) => (
            <Card key={s.label} pad={16}>
              <div className="overline" style={{ marginBottom: 6 }}>{s.label}</div>
              <div className="mono tabular" style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.value}</div>
            </Card>
          ))}
        </div>

        {/* Filter tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {(["all", "pending", "verified"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: "1px solid var(--border)",
                background: filter === f ? "var(--text)" : "var(--bg-elev)",
                color: filter === f ? "var(--bg)" : "var(--text-soft)",
                cursor: "pointer",
              }}
            >
              {f === "all" ? "Toutes" : f === "pending" ? "En attente" : "Vérifiées"}
            </button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--text-muted)", alignSelf: "center" }}>
            {filtered.length} résultats
          </span>
        </div>

        {/* Table */}
        {loading ? (
          <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
            Chargement...
          </div>
        ) : (
          <Card pad={0}>
            {/* Header */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "60px 1fr 140px 120px 100px 80px 80px 120px 140px",
              padding: "10px 16px", borderBottom: "1px solid var(--border)",
              background: "var(--bg-inset)",
            }}>
              {["ID", "Match", "Date", "Type", "Tip", "Cote", "Statut", "Résultat réel", "Actions"].map((h) => (
                <div key={h} className="overline" style={{ fontSize: 10 }}>{h}</div>
              ))}
            </div>

            {filtered.length === 0 && (
              <div style={{ padding: "48px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
                Aucune prédiction dans cette catégorie.
              </div>
            )}

            {filtered.map((p, i) => {
              const isEditing = editing[p.id] !== undefined;
              const e = editing[p.id];

              return (
                <div
                  key={p.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "60px 1fr 140px 120px 100px 80px 80px 120px 140px",
                    padding: "12px 16px", alignItems: "center", gap: 8,
                    borderBottom: i < filtered.length - 1 ? "1px solid var(--border)" : "none",
                    background: isEditing ? "var(--bg-inset)" : "transparent",
                  }}
                >
                  {/* ID */}
                  <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>#{p.id}</div>

                  {/* Match */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{p.homeTeam} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>vs</span> {p.awayTeam}</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{p.league}</div>
                  </div>

                  {/* Date */}
                  <div className="mono" style={{ fontSize: 11, color: "var(--text-soft)" }}>{fmtDate(p.matchDate)}</div>

                  {/* Type */}
                  <div style={{ fontSize: 12 }}>{tipLabel(p.tipType)}</div>

                  {/* Tip */}
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{p.prediction}</div>

                  {/* Cote */}
                  <div className="mono" style={{ fontSize: 13 }}>{p.odds?.toFixed(2) ?? "—"}</div>

                  {/* Statut */}
                  <div>
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: "2px 8px",
                      borderRadius: 6, background: "var(--bg-inset)",
                      color: statusColor(p.isWon),
                    }}>
                      {statusLabel(p.isWon)}
                    </span>
                  </div>

                  {/* Résultat réel — inline edit */}
                  <div>
                    {isEditing ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <select
                          value={e.actual_result}
                          onChange={(ev) => setEditing((prev) => ({ ...prev, [p.id]: { ...e, actual_result: ev.target.value } }))}
                          style={{ fontSize: 12, padding: "2px 4px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-elev)", color: "var(--text)" }}
                        >
                          <option value="">—</option>
                          <option value="H">H (Dom.)</option>
                          <option value="D">D (Nul)</option>
                          <option value="A">A (Ext.)</option>
                        </select>
                        <div style={{ display: "flex", gap: 4 }}>
                          <input
                            type="number" min={0} max={20} placeholder="Dom"
                            value={e.actual_home_goals}
                            onChange={(ev) => setEditing((prev) => ({ ...prev, [p.id]: { ...e, actual_home_goals: ev.target.value } }))}
                            style={{ width: 36, fontSize: 12, padding: "2px 4px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-elev)", color: "var(--text)" }}
                          />
                          <span style={{ fontSize: 11, alignSelf: "center", color: "var(--text-muted)" }}>-</span>
                          <input
                            type="number" min={0} max={20} placeholder="Ext"
                            value={e.actual_away_goals}
                            onChange={(ev) => setEditing((prev) => ({ ...prev, [p.id]: { ...e, actual_away_goals: ev.target.value } }))}
                            style={{ width: 36, fontSize: 12, padding: "2px 4px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-elev)", color: "var(--text)" }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="mono" style={{ fontSize: 13 }}>
                        {p.actualResult
                          ? `${p.actualResult} ${p.actualHomeGoals != null ? `(${p.actualHomeGoals}-${p.actualAwayGoals})` : ""}`
                          : <span style={{ color: "var(--text-muted)" }}>—</span>}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 6 }}>
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => save(p)}
                          disabled={saving[p.id]}
                          style={{
                            fontSize: 11, padding: "4px 10px", borderRadius: 6, cursor: "pointer",
                            background: "var(--text)", color: "var(--bg)", border: "none", fontWeight: 600,
                          }}
                        >
                          {saving[p.id] ? "..." : "Sauvegarder"}
                        </button>
                        <button
                          onClick={() => cancelEdit(p.id)}
                          style={{
                            fontSize: 11, padding: "4px 8px", borderRadius: 6, cursor: "pointer",
                            background: "var(--bg-inset)", color: "var(--text-soft)", border: "1px solid var(--border)",
                          }}
                        >
                          Annuler
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => startEdit(p)}
                        style={{
                          fontSize: 11, padding: "4px 10px", borderRadius: 6, cursor: "pointer",
                          background: "var(--bg-inset)", color: "var(--text-soft)", border: "1px solid var(--border)",
                        }}
                      >
                        Modifier
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </Card>
        )}

        {/* Retrain log */}
        {retrainLog && (
          <Card style={{ marginTop: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Logs du réentraînement</span>
              <button onClick={() => setRetrainLog(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}>
                <I.Close size={16} />
              </button>
            </div>
            <pre style={{ fontSize: 11, color: "var(--text-soft)", overflow: "auto", maxHeight: 300, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
              {retrainLog}
            </pre>
          </Card>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 1000,
          background: "var(--text)", color: "var(--bg)",
          padding: "12px 20px", borderRadius: 12,
          fontSize: 14, fontWeight: 500,
          boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
        }}>
          {toast}
        </div>
      )}
    </AppShell>
  );
}
