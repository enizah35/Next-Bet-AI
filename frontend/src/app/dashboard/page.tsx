"use client";

import React, { useEffect, useState, useMemo } from 'react';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { Icons } from '@/components/Icons';

/* ───── sub-components ───── */

const FormDots = ({ form }: { form: string[] }) => (
  <div style={{ display: 'flex', gap: '4px' }}>
    {form.map((r, i) => (
      <span key={i} style={{
        width: '22px', height: '22px', borderRadius: '6px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.65rem', fontWeight: 700, color: '#fff',
        background: r === 'W' ? '#22c55e' : r === 'D' ? '#eab308' : '#ef4444',
      }}>{r}</span>
    ))}
  </div>
);

const StatCircle = ({ value, label, color }: { value: number; label: string; color: string }) => {
  const circumference = 2 * Math.PI * 30;
  const pct = Math.min(value / 100, 1);
  const dashOffset = circumference - pct * circumference;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
      <div style={{ position: 'relative', width: '68px', height: '68px' }}>
        <svg width="68" height="68" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="34" cy="34" r="30" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
          <circle cx="34" cy="34" r="30" fill="none" stroke={color} strokeWidth="5"
            strokeDasharray={circumference} strokeDashoffset={dashOffset}
            strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
        </svg>
        <span style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)',
        }}>{value}%</span>
      </div>
      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600 }}>{label}</span>
    </div>
  );
};

/* ───── page ───── */

export default function DashboardPage() {
  const [cache, setCache] = useState<Record<string, any[]>>({});
  const [matches, setMatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingText, setLoadingText] = useState("Verification de la meteo...");
  const [selectedMatch, setSelectedMatch] = useState<any>(null);
  const [selectedBet, setSelectedBet] = useState<{match: any, selection: any} | null>(null);
  const [league, setLeague] = useState<"Ligue 1" | "Premier League">("Ligue 1");
  const [tab, setTab] = useState<"predictions" | "stats" | "tips">("predictions");
  const { user, profile } = useAuth();

  /* loading animation */
  useEffect(() => {
    if (!loading) return;
    const texts = [
      "Surveillance de la temperature des vestiaires...",
      "Verification de la pression des ballons...",
      "Analyse des derniers potins mercato...",
      "Inspection de la pelouse...",
      "Echauffement des algorithmes...",
    ];
    let idx = 0;
    const iv = setInterval(() => { idx = (idx + 1) % texts.length; setLoadingText(texts[idx]); }, 1500);
    return () => clearInterval(iv);
  }, [loading]);

  /* fetch data (single API call, used by all tabs) */
  useEffect(() => {
    if (cache[league]) { setMatches(cache[league]); setLoading(false); return; }
    setLoading(true);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/predictions/upcoming?league=${league}`)
      .then(r => r.json())
      .then(data => { setMatches(data); setCache(p => ({ ...p, [league]: data })); setLoading(false); })
      .catch(() => setLoading(false));
  }, [league]);

  const closeModal = () => setSelectedMatch(null);
  const isUnlocked = () => true; // DEV bypass

  /* Tips derived from matches data (no extra API call) */
  const tips = useMemo(() => {
    const t: any[] = [];
    for (const m of matches) {
      const pr = m.probs || {};
      const st = m.stats || {};
      const dcHome = (pr.p1 || 0) + (pr.pn || 0);
      if (dcHome > 70) t.push({ ...m, tip: '1 ou Nul', category: 'Dbl Chance', confidence: Math.round(dcHome), odds: +(100 / dcHome).toFixed(2) });
      const dcAway = (pr.p2 || 0) + (pr.pn || 0);
      if (dcAway > 70) t.push({ ...m, tip: '2 ou Nul', category: 'Dbl Chance', confidence: Math.round(dcAway), odds: +(100 / dcAway).toFixed(2) });
      if ((st.btts_pct || 0) > 60) t.push({ ...m, tip: 'Les deux marquent', category: 'BTTS', confidence: st.btts_pct, odds: +(100 / st.btts_pct).toFixed(2) });
      if ((st.over25_pct || 0) > 58) t.push({ ...m, tip: 'Plus de 2.5 buts', category: 'Goals', confidence: st.over25_pct, odds: +(100 / st.over25_pct).toFixed(2) });
    }
    t.sort((a, b) => b.confidence - a.confidence);
    return t.slice(0, 15);
  }, [matches]);

  const catColor = (c: string) => c === 'Dbl Chance' ? '#3b82f6' : c === 'BTTS' ? '#8b5cf6' : c === 'Goals' ? '#22c55e' : '#f59e0b';
  const confLevel = (c: number) => c >= 80 ? { l: 'TRES FIABLE', c: '#22c55e' } : c >= 70 ? { l: 'FIABLE', c: '#3b82f6' } : c >= 60 ? { l: 'MODERE', c: '#f59e0b' } : { l: 'RISQUE', c: '#ef4444' };

  const sorted = [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  return (
    <>
      {/* HEADER */}
      <header className="header" style={{ background: "var(--header-bg)" }}>
        <div className="header-logo"><Logo width={220} height={55} /></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <Link href="/dashboard" style={{ color: 'var(--color-accent)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 }}>Analyses</Link>
          <Link href="/results" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 }}>Resultats</Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ThemeToggle />
            <UserNav />
          </div>
        </div>
      </header>

      {/* LOADING */}
      {loading && matches.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 80px)', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', fontWeight: 600 }}>Chargement de l analyse IA</h2>
          <p style={{ color: 'var(--text-secondary)' }}>{loadingText}</p>
        </div>
      ) : (
        <main className="container">
          {/* TOP BAR */}
          <div className="top-bar">
            <div>
              <h1 className="dashboard-title">Analyses IA — Matchs a venir</h1>
              <p className="dashboard-subtitle">Predictions, statistiques et tips generes par notre reseau de neurones.</p>
            </div>
            <div className="league-toggle">
              <button className={`toggle-btn ${league === 'Ligue 1' ? 'active' : ''}`} onClick={() => setLeague('Ligue 1')}>Ligue 1</button>
              <button className={`toggle-btn ${league === 'Premier League' ? 'active' : ''}`} onClick={() => setLeague('Premier League')}>Premier League</button>
            </div>
          </div>

          {/* TAB BAR */}
          <div style={{
            display: 'flex', gap: '4px', marginBottom: '1.5rem',
            background: 'var(--glass-bg)', borderRadius: '12px', padding: '4px',
            border: '1px solid var(--glass-border)', width: 'fit-content',
          }}>
            {([['predictions', 'Predictions'], ['stats', 'Stats & Bet Builder'], ['tips', 'Tips du Jour']] as const).map(([key, label]) => (
              <button key={key} onClick={() => setTab(key as any)}
                style={{
                  padding: '8px 20px', borderRadius: '10px', border: 'none', cursor: 'pointer',
                  fontWeight: 600, fontSize: '0.85rem', fontFamily: 'inherit', transition: 'all 0.2s',
                  background: tab === key ? 'linear-gradient(135deg, #7c3aed, #3b82f6)' : 'transparent',
                  color: tab === key ? '#fff' : 'var(--text-muted)',
                }}>{label}</button>
            ))}
          </div>

          {/* TAB: PREDICTIONS */}
          {tab === 'predictions' && (
            <div className="matches-grid">
              {sorted.map(match => (
                <div key={match.id} className="match-card" onClick={() => setSelectedMatch(match)} style={{ cursor: 'pointer' }}>
                  <div className="match-header">
                    <span className="competition-badge">{match.competition}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 500 }}>
                      <Icons.calendar size={14} /> {new Date(match.date).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', '')}
                    </div>
                  </div>

                  {match.valueBet?.active && (
                    <div className="badge badge-value" style={{ width: 'fit-content' }}>
                      <Icons.trendingUp size={14} /> VALUE BET ({match.valueBet.edge}% EDGE)
                    </div>
                  )}

                  <div className="recommendation-banner">
                    <Icons.zap size={14} /> {match.recommendation}
                  </div>

                  <div className="match-teams">
                    <div className="team home">
                      <span className="team-name">{match.homeTeam}</span>
                      {match.injuries?.filter((inj: string) => inj.includes(match.homeTeam)).map((_: string, i: number) => (
                        <span key={`h-${i}`} className="badge badge-injury"><Icons.alertCircle size={12} /> Alerte Info</span>
                      ))}
                    </div>
                    <div className="vs">VS</div>
                    <div className="team away">
                      <span className="team-name">{match.awayTeam}</span>
                      {match.injuries?.filter((inj: string) => inj.includes(match.awayTeam)).map((_: string, i: number) => (
                        <span key={`a-${i}`} className="badge badge-injury"><Icons.alertCircle size={12} /> Alerte Info</span>
                      ))}
                    </div>
                  </div>

                  <div className="prediction-section">
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      Probabilites AI
                    </span>
                    <div className="prob-bar-container">
                      <div className="prob-segment prob-1" style={{ width: `${match.probs.p1}%` }} />
                      <div className="prob-segment prob-n" style={{ width: `${match.probs.pn}%` }} />
                      <div className="prob-segment prob-2" style={{ width: `${match.probs.p2}%` }} />
                    </div>
                    <div className="prob-labels">
                      <span className="label-1">{match.homeTeam} {match.probs.p1}%</span>
                      <span className="label-n">Nul {match.probs.pn}%</span>
                      <span className="label-2">{match.awayTeam} {match.probs.p2}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB: STATS & BET BUILDER */}
          {tab === 'stats' && (
            <div className="matches-grid">
              {sorted.map(match => {
                const st = match.stats || {};
                const bb = match.betBuilder;
                return (
                  <div key={match.id} className="match-card">
                    <div className="match-header">
                      <span className="competition-badge">{match.competition}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 500 }}>
                        <Icons.calendar size={14} />
                        {new Date(match.date).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', '')}
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0.8rem 0' }}>
                      <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-home)' }}>{match.homeTeam}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>VS</span>
                      <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-away)', textAlign: 'right' }}>{match.awayTeam}</span>
                    </div>

                    {/* Stats numbers */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', background: 'var(--card-inner-bg)', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-accent)' }}>{st.predicted_goals?.toFixed(1) ?? '2.5'}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Buts</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>{st.predicted_corners?.toFixed(1) ?? '10.0'}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Corners</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444' }}>{st.predicted_cards?.toFixed(1) ?? '4.0'}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Cartons</div>
                      </div>
                    </div>

                    {/* Circles */}
                    <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: '12px' }}>
                      <StatCircle value={st.btts_pct ?? 50} label="BTTS" color="#8b5cf6" />
                      <StatCircle value={st.over25_pct ?? 50} label="O 2.5" color="#22c55e" />
                      <StatCircle value={st.over15_pct ?? 65} label="O 1.5" color="#3b82f6" />
                    </div>

                    {/* Form */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-inner-bg)', borderRadius: '10px', padding: '12px', marginBottom: '12px' }}>
                      <div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>FORME DOM.</div>
                        <FormDots form={st.home_form || []} />
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>FORME EXT.</div>
                        <FormDots form={st.away_form || []} />
                      </div>
                    </div>

                    {/* Bet Builder */}
                    {bb && bb.selections?.length > 0 && (
                      <div style={{ background: 'linear-gradient(135deg, rgba(124,58,237,0.08), rgba(59,130,246,0.08))', borderRadius: '10px', padding: '12px', border: '1px solid rgba(124,58,237,0.2)' }}>
                        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Icons.cpu size={14} /> AI Bet Builder
                        </div>
                        {bb.source && (
                          <div style={{ fontSize: '0.65rem', color: bb.source === 'winamax_betclic' ? '#22c55e' : 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
                            {bb.source === 'winamax_betclic' ? '● Cotes Winamax / Betclic' : '● Cotes estimées IA'}
                          </div>
                        )}
                        {bb.selections.map((sel: any, i: number) => (
                          <div
                            key={i}
                            onClick={() => setSelectedBet({ match, selection: sel })}
                            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 6px', borderBottom: i < bb.selections.length - 1 ? '1px solid var(--glass-border)' : 'none', cursor: 'pointer', borderRadius: '6px', transition: 'background 0.15s' }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(124,58,237,0.12)')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                              <span style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 500 }}>{sel.label_fr}</span>
                              {sel.bookmaker && (
                                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>{sel.bookmaker}</span>
                              )}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f59e0b' }}>{sel.odds.toFixed(2)}</span>
                              <Icons.chevronRight size={12} style={{ color: 'var(--text-muted)' }} />
                            </div>
                          </div>
                        ))}
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(124,58,237,0.2)' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>COTE COMBINEE</span>
                          <span style={{ fontSize: '1rem', fontWeight: 700, color: '#f59e0b' }}>{bb.combined_odds.toFixed(2)}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* TAB: TIPS DU JOUR */}
          {tab === 'tips' && (
            tips.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>&#128270;</div>
                <p>Aucun tip disponible pour cette ligue.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '700px' }}>
                {tips.map((tip: any, i: number) => {
                  const lv = confLevel(tip.confidence);
                  return (
                    <div key={i} style={{
                      background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
                      borderRadius: '14px', padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '14px',
                      backdropFilter: 'blur(10px)', transition: 'all 0.2s',
                    }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
                        background: i < 3 ? 'linear-gradient(135deg, #f59e0b, #ef4444)' : 'var(--card-inner-bg)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 700, fontSize: '0.8rem', color: i < 3 ? '#fff' : 'var(--text-muted)',
                      }}>{i + 1}</div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                          <span style={{ fontSize: '0.6rem', fontWeight: 600, color: catColor(tip.category), background: `${catColor(tip.category)}15`, padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>{tip.category}</span>
                        </div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{tip.homeTeam} - {tip.awayTeam}</div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{tip.tip}</div>
                      </div>

                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: '1.05rem', color: lv.c }}>{tip.confidence}%</div>
                        <div style={{ fontSize: '0.6rem', fontWeight: 600, color: lv.c, background: `${lv.c}15`, padding: '2px 6px', borderRadius: '4px', display: 'inline-block', marginBottom: '2px' }}>{lv.l}</div>
                        <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#f59e0b' }}>Cote {tip.odds}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}

          {/* MODAL: Detail */}
          {selectedMatch && (
            <div className="modal-overlay" onClick={closeModal}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="close-button" onClick={closeModal}><Icons.x size={24} /></button>

                <h2 style={{ fontSize: '1rem', color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1.5rem', fontWeight: 600 }}>
                  Analyse Detaillee IA
                </h2>

                <div className="match-teams" style={{ marginBottom: '1rem', background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '16px', border: '1px solid var(--glass-border)' }}>
                  <div className="team home">
                    <span className="team-name" style={{ fontSize: '1.8rem', background: 'var(--color-home-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{selectedMatch.homeTeam}</span>
                  </div>
                  <div className="vs" style={{ fontSize: '1rem', padding: '0.6rem' }}>VS</div>
                  <div className="team away">
                    <span className="team-name" style={{ fontSize: '1.8rem', background: 'var(--color-away-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{selectedMatch.awayTeam}</span>
                  </div>
                </div>

                <div className="modal-grid-2">
                  <div className="data-box">
                    <div className="data-box-title">Forme du moment</div>
                    <div className="metric-row">
                      <span style={{ color: 'var(--color-home)' }}>{Math.round((selectedMatch.details?.formHome ?? 0.5) * 100)} / 100</span>
                      <span style={{ color: 'var(--text-muted)' }}>Note globale</span>
                      <span style={{ color: 'var(--color-away)' }}>{Math.round((selectedMatch.details?.formAway ?? 0.5) * 100)} / 100</span>
                    </div>
                  </div>

                  <div className="data-box">
                    <div className="data-box-title">Repos & Puissance</div>
                    <div className="metric-row">
                      <span style={{ color: 'var(--text-primary)' }}>{selectedMatch.details?.homeDaysRest ?? '?'} jours</span>
                      <span style={{ color: 'var(--text-muted)' }}>Repos</span>
                      <span style={{ color: 'var(--text-primary)' }}>{selectedMatch.details?.awayDaysRest ?? '?'} jours</span>
                    </div>
                    <div className="metric-row">
                      <span style={{ color: 'var(--color-home)' }}>{selectedMatch.details?.homeElo ?? '?'}</span>
                      <span style={{ color: 'var(--text-muted)' }}>Elo</span>
                      <span style={{ color: 'var(--color-away)' }}>{selectedMatch.details?.awayElo ?? '?'}</span>
                    </div>
                  </div>

                  {/* Stats in modal */}
                  {selectedMatch.stats && (
                    <div className="data-box" style={{ gridColumn: '1 / -1' }}>
                      <div className="data-box-title">Predictions Statistiques</div>
                      <div style={{ display: 'flex', justifyContent: 'space-around', margin: '0.5rem 0' }}>
                        <StatCircle value={selectedMatch.stats.btts_pct ?? 50} label="BTTS" color="#8b5cf6" />
                        <StatCircle value={selectedMatch.stats.over25_pct ?? 50} label="Over 2.5" color="#22c55e" />
                        <StatCircle value={selectedMatch.stats.over15_pct ?? 65} label="Over 1.5" color="#3b82f6" />
                      </div>
                      <div className="metric-row">
                        <span style={{ color: 'var(--color-accent)' }}>{selectedMatch.stats.predicted_goals?.toFixed(1)} buts</span>
                        <span style={{ color: 'var(--text-muted)' }}>Total predit</span>
                        <span style={{ color: '#f59e0b' }}>{selectedMatch.stats.predicted_corners?.toFixed(1)} corners</span>
                      </div>
                    </div>
                  )}

                  {/* Weather */}
                  <div className="data-box" style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                    <div style={{ fontSize: '3rem', lineHeight: 1 }}>
                      {selectedMatch.details?.weatherCode === 1 ? '☀️' : selectedMatch.details?.weatherCode === 2 ? '⛅' : '🌧️'}
                    </div>
                    <div>
                      <div className="data-box-title" style={{ marginBottom: '0.3rem' }}>Impact Meteo</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                        {selectedMatch.details?.weatherCode === 1 ? 'Condition optimale' : selectedMatch.details?.weatherCode === 2 ? 'Ciel nuageux / Vent' : 'Forte pluie'}
                      </div>
                    </div>
                  </div>

                  {/* Conseil */}
                  <div className="data-box" style={{ gridColumn: '1 / -1', background: 'var(--instruction-bg)', borderColor: 'var(--glass-border)' }}>
                    <div className="data-box-title" style={{ color: 'var(--color-accent)' }}>NOTRE CONSEIL</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--instruction-text)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Icons.zap size={24} /> {selectedMatch.recommendation}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      )}
    </>
  );
}
