"use client";

import React, { useState, useCallback } from 'react';
import { AppShell, PageHeader } from '@/components/AppShell';
import { Button } from '@/components/ui/Button';
import { I } from '@/components/Icons';

interface ResultStats {
  total: number;
  won: number;
  lost: number;
  pending: number;
  winRate: number;
}

interface PredictionEntry {
  id: number;
  homeTeam: string;
  awayTeam: string;
  league: string;
  matchDate: string | null;
  prediction: string;
  tipType: string;
  confidence: number;
  odds: number | null;
  actualResult: string | null;
  actualScore: string | null;
  isWon: boolean | null;
  createdAt: string | null;
  verifiedAt: string | null;
}

interface BetBuilderEntry {
  matchKey: string;
  homeTeam: string;
  awayTeam: string;
  league: string;
  matchDate: string | null;
  actualScore: string | null;
  selections: PredictionEntry[];
  combinedOdds: number;
  isWon: boolean | null;
}

type FilterKey = "all" | "won" | "lost" | "pending";

export default function ResultsClient({
  initialStats,
  initialHistory,
  initialBetBuilders
}: {
  initialStats: ResultStats;
  initialHistory: PredictionEntry[];
  initialBetBuilders: BetBuilderEntry[];
}) {
  const [stats, setStats] = useState<ResultStats>(initialStats);
  const [history, setHistory] = useState<PredictionEntry[]>(initialHistory);
  const [betBuilders, setBetBuilders] = useState<BetBuilderEntry[]>(initialBetBuilders);
  const [verifying, setVerifying] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();

  const fetchResults = useCallback(() => {
    fetch(`${apiUrl}/predictions/results`)
      .then(res => res.json())
      .then(data => {
        setStats(data.stats || { total: 0, won: 0, lost: 0, pending: 0, winRate: 0 });
        setHistory(data.history || []);
        setBetBuilders(data.betBuilders || []);
      })
      .catch(() => {});
  }, [apiUrl]);

  const handleVerify = async () => {
    setVerifying(true);
    setVerifyMsg(null);
    try {
      const res = await fetch(`${apiUrl}/predictions/verify`, { method: 'POST' });
      const data = await res.json();
      setVerifyMsg(`${data.verified || 0} prediction(s) verifiee(s)`);
      fetchResults();
    } catch {
      setVerifyMsg("Erreur lors de la verification");
    } finally {
      setVerifying(false);
    }
  };

  const filtered = filter === "all" ? history
    : filter === "won" ? history.filter(e => e.isWon === true)
    : filter === "lost" ? history.filter(e => e.isWon === false)
    : history.filter(e => e.isWon === null);

  const WinRateCircle = ({ rate }: { rate: number }) => {
    const circumference = 2 * Math.PI * 54;
    const dashOffset = circumference - (rate / 100) * circumference;
    const color = rate >= 65 ? 'var(--good)' : rate >= 50 ? 'var(--warn)' : 'var(--bad)';
    return (
      <div style={{ position: 'relative', width: '130px', height: '130px' }}>
        <svg width="130" height="130" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="65" cy="65" r="54" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
          <circle cx="65" cy="65" r="54" fill="none" stroke={color} strokeWidth="10"
            strokeDasharray={circumference} strokeDashoffset={dashOffset}
            strokeLinecap="round" style={{ transition: 'stroke-dashoffset 1s ease' }} />
        </svg>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text)' }}>{rate}%</div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600 }}>WIN RATE</div>
        </div>
      </div>
    );
  };

  return (
    <AppShell>
      <div className="app-page results-container">
          <PageHeader
            title="Resultats & Performance"
            subtitle="Suivi en temps reel de nos predictions IA vs resultats reels."
            actions={
              <Button onClick={handleVerify} disabled={verifying} variant="value" icon={<I.Check size={15} />}>
                {verifying ? 'Verification...' : 'Verifier'}
              </Button>
            }
          />

          {verifyMsg && (
            <div style={{
              background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
              borderRadius: '10px', padding: '10px 16px', marginBottom: '1.5rem',
              color: '#22c55e', fontWeight: 600, fontSize: '0.85rem',
            }}>{verifyMsg}</div>
          )}

          {/* Stats Overview */}
          <div className="results-overview" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '40px',
            background: 'var(--bg-elev)', border: '1px solid var(--border)',
            borderRadius: '20px', padding: '30px', marginBottom: '2rem',
            backdropFilter: 'blur(10px)', flexWrap: 'wrap',
          }}>
            <WinRateCircle rate={stats.winRate} />
            <div className="results-stat-counts" style={{ display: 'flex', gap: '24px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#22c55e' }}>{stats.won}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Gagnes</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#ef4444' }}>{stats.lost}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Perdus</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#f59e0b' }}>{stats.pending}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>En attente</div>
              </div>
            </div>
          </div>

          {/* Bet Builder Results */}
          {betBuilders.length > 0 && (
            <>
              <h2 style={{ fontSize: '1rem', color: 'var(--value)', fontWeight: 700, marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <I.Spark size={16} /> Bet Builder ({betBuilders.length})
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '2rem' }}>
                {betBuilders.map((bb, i) => {
                  const statusColor = bb.isWon === true ? '#22c55e' : bb.isWon === false ? '#ef4444' : '#f59e0b';
                  const statusBg = bb.isWon === true ? 'rgba(34,197,94,0.08)' : bb.isWon === false ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)';
                  return (
                    <div key={i} style={{
                      background: statusBg, border: `1px solid ${statusColor}33`,
                      borderRadius: '14px', padding: '16px', borderLeft: `4px solid ${statusColor}`,
                    }}>
                      <div className="results-builder-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)' }}>
                            {bb.homeTeam} - {bb.awayTeam}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {bb.league}{bb.matchDate && ` — ${new Date(bb.matchDate).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}`}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          {bb.actualScore ? (
                            <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text)' }}>{bb.actualScore}</div>
                          ) : (
                            <div style={{ fontSize: '0.75rem', color: '#f59e0b', fontWeight: 600 }}>En attente</div>
                          )}
                          <div style={{ fontSize: '0.7rem', color: statusColor, fontWeight: 700, marginTop: '2px' }}>
                            {bb.isWon === true ? '✅ GAGNE' : bb.isWon === false ? '❌ PERDU' : '⏳ EN COURS'}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {bb.selections.map((sel, j) => {
                          const selColor = sel.isWon === true ? '#22c55e' : sel.isWon === false ? '#ef4444' : 'var(--text-muted)';
                          return (
                            <div key={j} className="results-selection-row" style={{
                              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                              padding: '6px 10px', borderRadius: '8px',
                              background: 'rgba(255,255,255,0.03)',
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ fontSize: '0.8rem' }}>
                                  {sel.isWon === true ? '✅' : sel.isWon === false ? '❌' : '⏳'}
                                </span>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text)', fontWeight: 500 }}>{sel.prediction}</span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{sel.confidence}%</span>
                                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: selColor }}>{sel.odds?.toFixed(2)}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(124,58,237,0.15)' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>COTE COMBINEE</span>
                        <span style={{ fontSize: '1rem', fontWeight: 700, color: statusColor }}>{bb.combinedOdds.toFixed(2)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* Filter bar */}
          <div className="results-filter" style={{ display: 'flex', gap: '4px', marginBottom: '1rem', background: 'var(--bg-elev)', borderRadius: '10px', padding: '4px', border: '1px solid var(--border)', width: 'fit-content' }}>
            {([['all', 'Tout'], ['won', 'Gagnes'], ['lost', 'Perdus'], ['pending', 'En attente']] as const).map(([key, label]) => (
              <button key={key} onClick={() => setFilter(key)}
                style={{
                  padding: '6px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                  fontWeight: 600, fontSize: '0.8rem', fontFamily: 'inherit', transition: 'all 0.2s',
                  background: filter === key ? 'var(--bg-inset)' : 'transparent',
                  color: filter === key ? 'var(--text)' : 'var(--text-muted)',
                  boxShadow: filter === key ? 'inset 0 0 0 1px var(--border)' : 'none',
                }}>{label}</button>
            ))}
          </div>

          <h2 style={{ fontSize: '1rem', color: 'var(--text-soft)', fontWeight: 600, marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Historique des predictions ({filtered.length})
          </h2>

          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>&#128202;</div>
              <p>Aucune prediction enregistree pour le moment.</p>
              <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>Les predictions apparaitront ici apres avoir consulte le dashboard.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filtered.map((entry) => (
                <div key={entry.id} className="results-history-row" style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  background: 'var(--bg-elev)', border: '1px solid var(--border)',
                  borderRadius: '12px', padding: '14px 16px',
                  borderLeft: `3px solid ${entry.isWon === true ? '#22c55e' : entry.isWon === false ? '#ef4444' : '#f59e0b'}`,
                }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: entry.isWon === true ? 'rgba(34,197,94,0.15)' : entry.isWon === false ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                    color: entry.isWon === true ? '#22c55e' : entry.isWon === false ? '#ef4444' : '#f59e0b',
                  }}>
                    {entry.isWon === true ? <I.Check size={18} /> : entry.isWon === false ? <I.Close size={18} /> : <I.Target size={16} />}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                      {entry.homeTeam} - {entry.awayTeam}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {entry.prediction} - {entry.tipType} - {entry.league}
                      {entry.matchDate && ` - ${new Date(entry.matchDate).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}`}
                    </div>
                  </div>

                  <div className="results-history-status" style={{ textAlign: 'right', flexShrink: 0 }}>
                    {entry.actualScore ? (
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)' }}>{entry.actualScore}</div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: '#f59e0b', fontWeight: 600 }}>En attente</div>
                    )}
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      {entry.confidence}% conf.
                      {entry.odds && ` - Cote ${entry.odds.toFixed(2)}`}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </AppShell>
  );
}
