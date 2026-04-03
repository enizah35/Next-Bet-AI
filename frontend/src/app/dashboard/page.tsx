"use client";

import React, { useEffect, useState } from 'react';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

import { Icons } from '@/components/Icons';

export default function DashboardPage() {
  const [cache, setCache] = useState<Record<string, any[]>>({});
  const [matches, setMatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingText, setLoadingText] = useState("Vérification de la météo...");
  const [selectedMatch, setSelectedMatch] = useState<any>(null);
  const [league, setLeague] = useState<"Ligue 1" | "Premier League">("Ligue 1");
  const { user, profile, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!loading) return;
    const texts = [
      "Surveillance de la température des vestiaires...",
      "Vérification de la pression des ballons...",
      "Analyse des derniers potins mercato...",
      "Inspection de la pelouse...",
      "Échauffement des algorithmes..."
    ];
    let idx = 0;
    const interval = setInterval(() => {
      idx = (idx + 1) % texts.length;
      setLoadingText(texts[idx]);
    }, 1500);
    return () => clearInterval(interval);
  }, [loading]);

  // Auth handled by AuthContext via useAuth() hook above.
  
  useEffect(() => {
    // Data fetching logic only
    if (cache[league]) {
      setMatches(cache[league]);
      setLoading(false);
      return;
    }

    setLoading(true);
    fetch(`http://localhost:8000/predictions/upcoming?league=${league}`)
      .then(res => res.json())
      .then(data => {
        setMatches(data);
        setCache(prev => ({ ...prev, [league]: data }));
        setLoading(false);
      })
      .catch(err => {
        console.error("API Error", err);
        setLoading(false);
      });
  }, [league]);

  const closeModal = () => setSelectedMatch(null);

  // Gating Logic
  const isTrialActive = profile?.trial_started_at && 
    (new Date().getTime() - new Date(profile.trial_started_at).getTime()) < (7 * 24 * 60 * 60 * 1000);
  
  const isUnlockedGlobally = (league: string) => {
    if (!user || !profile) return false;
    const tier = profile.subscription_tier;
    
    // Ultimate débloque tout, tout le temps
    if (tier === 'ultimate') return true;
    
    // Pour les autres tiers (ligue1, pl), ils ne débloquent QUE leur ligue respective
    // L'essai (isTrialActive) permet d'accéder au tier sans payer, mais ne doit pas débloquer l'autre ligue
    return (tier === 'ligue1' && league === 'Ligue 1') || 
           (tier === 'pl' && league === 'Premier League');
  };

  if (!authLoading && !user) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'var(--bg-gradient)' }}>
        <div className="auth-gate-modal" style={{ maxWidth: '450px', background: 'var(--glass-bg)', backdropFilter: 'blur(20px)', padding: '3rem' }}>
          <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>🔐</div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '1rem', color: 'var(--text-primary)' }}>Accès Réservé</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem', lineHeight: 1.6 }}>
            Connectez-vous pour accéder à la Bêta Privée de Next-Bet-AI et voir les prédictions en temps réel.
          </p>
          <Link href="/login" className="auth-submit" style={{ display: 'block', width: '100%', textDecoration: 'none' }}>
            Se connecter
          </Link>
          <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            Pas encore de compte ? <Link href="/register" style={{ color: 'var(--color-accent)', textDecoration: 'none', fontWeight: 600 }}>Inscrivez-vous à la liste d'attente</Link>
          </p>
        </div>
      </div>
    );
  }





  return (
    <>
      <header className="header" style={{ background: "var(--header-bg)" }}>
        <div className="header-logo">
          <Logo width={220} height={55} />
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <Link href="/pricing" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 }}>
            Nos Forfaits
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ThemeToggle />
            <UserNav />
          </div>
        </div>
      </header>

      {loading && matches.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 80px)', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', fontWeight: 600 }}>Chargement de l'analyse IA</h2>
          <p style={{ color: 'var(--text-secondary)' }}>{loadingText}</p>
        </div>
      ) : (
        <main className="container">
        <div className="top-bar">
          <div>
            <h1 className="dashboard-title">Matchs à venir (7j)</h1>
            <p className="dashboard-subtitle">
              Nos algorithmes analysent des milliers de données pour vous donner le meilleur pronostic.
            </p>
          </div>
          
          <div className="league-toggle">
            <button 
              className={`toggle-btn ${league === 'Ligue 1' ? 'active' : ''}`}
              onClick={() => setLeague('Ligue 1')}
            >
              Ligue 1
            </button>
            <button 
              className={`toggle-btn ${league === 'Premier League' ? 'active' : ''}`}
              onClick={() => setLeague('Premier League')}
            >
              Premier League
            </button>
          </div>
        </div>

        {loading && matches.length > 0 && (
          <div style={{ textAlign: 'center', marginBottom: '1.5rem', color: 'var(--color-accent)', fontWeight: 500, fontSize: '0.9rem', animation: 'pulseGlow 2s infinite' }}>
            Actualisation des données en direct...
          </div>
        )}

        <div className="matches-grid">
          {matches.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()).map(match => {
            const isUnlocked = isUnlockedGlobally(match.competition);
            
            return (
            <div key={match.id} className="match-card" onClick={() => setSelectedMatch(match)} style={{ cursor: 'pointer' }}>
              <div className="match-header">
                <span className="competition-badge">{match.competition}</span>
                <div style={{display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 500}}>
                  <Icons.calendar size={14} /> {new Date(match.date).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', '')}
                </div>
              </div>

              {match.valueBet?.active && (
                <div className={`badge badge-value ${!isUnlocked ? 'blurred' : ''}`} style={{ width: 'fit-content' }}>
                  <Icons.trendingUp size={14} /> VALUE BET ({isUnlocked ? `${match.valueBet.edge}% EDGE` : 'EDGE RÉSERVÉ'})
                </div>
              )}

              <div className={`recommendation-banner ${!isUnlocked ? 'blurred' : ''}`}>
                 <Icons.zap size={14} /> {isUnlocked ? match.recommendation : 'Abonnement requis'}
              </div>
              
              <div className="match-teams">
                <div className="team home">
                  <span className="team-name">{match.homeTeam}</span>
                  {match.injuries && match.injuries.map((inj: string, i: number) => 
                    inj.includes(match.homeTeam) && (
                      <span key={`h-${i}`} className="badge badge-injury"><Icons.alertCircle size={12} /> Alerte Info</span>
                    )
                  )}
                </div>
                
                <div className="vs">VS</div>
                
                <div className="team away">
                  <span className="team-name">{match.awayTeam}</span>
                  {match.injuries && match.injuries.map((inj: string, i: number) => 
                    inj.includes(match.awayTeam) && (
                      <span key={`a-${i}`} className="badge badge-injury"><Icons.alertCircle size={12} /> Alerte Info</span>
                    )
                  )}
                </div>
              </div>

              <div className="prediction-section">
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end'}}>
                  <span style={{fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px'}}>
                    Probabilités AI
                  </span>
                </div>
                
                {isUnlocked ? (
                  <>
                    <div className="prob-bar-container">
                      <div className="prob-segment prob-1" style={{ width: `${match.probs.p1}%` }}></div>
                      <div className="prob-segment prob-n" style={{ width: `${match.probs.pn}%` }}></div>
                      <div className="prob-segment prob-2" style={{ width: `${match.probs.p2}%` }}></div>
                    </div>
                    
                    <div className="prob-labels">
                      <span className="label-1">{match.homeTeam} {match.probs.p1}%</span>
                      <span className="label-n">Nul {match.probs.pn}%</span>
                      <span className="label-2">{match.awayTeam} {match.probs.p2}%</span>
                    </div>
                  </>
                ) : (
                  <div className="auth-gate-inline">
                    <button onClick={(e) => { e.stopPropagation(); window.location.href='/pricing'; }}>🎯 Débloquer l'accès</button>
                  </div>
                )}
              </div>
            </div>
            );
          })}
        </div>

        {/* Modal Structure */}
        {selectedMatch && (
          <div className="modal-overlay" onClick={closeModal}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
              <button className="close-button" onClick={closeModal}><Icons.x size={24} /></button>
              
              <div style={{marginBottom: '2rem'}}>
                <h2 style={{fontSize: '1rem', color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1.5rem', fontWeight: 600}}>
                   Analyse Détaillée IA
                </h2>
                
                <div className="match-teams" style={{marginBottom: '1rem', background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '16px', border: '1px solid var(--glass-border)'}}>
                  <div className="team home">
                    <span className="team-name" style={{fontSize: '1.8rem', background: 'var(--color-home-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>{selectedMatch.homeTeam}</span>
                  </div>
                  <div className="vs" style={{fontSize: '1rem', padding: '0.6rem'}}>VS</div>
                  <div className="team away">
                    <span className="team-name" style={{fontSize: '1.8rem', background: 'var(--color-away-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>{selectedMatch.awayTeam}</span>
                  </div>
                </div>
              </div>

              {isUnlockedGlobally(selectedMatch.competition) ? (
                <div className="modal-grid-2">
                  <div className="data-box">
                    <div className="data-box-title">Forme du moment</div>
                    <div className="metric-row">
                      <span style={{color: 'var(--color-home)'}}>{Math.round(selectedMatch.details.formHome * 100)} / 100</span>
                      <span style={{color: 'var(--text-muted)'}}>Note globale</span>
                      <span style={{color: 'var(--color-away)'}}>{Math.round(selectedMatch.details.formAway * 100)} / 100</span>
                    </div>
                  </div>

                  <div className="data-box">
                    <div className="data-box-title">Repos & Classement</div>
                    <div className="metric-row">
                      <span style={{color: 'var(--text-primary)'}}>{selectedMatch.details.homeDaysRest} jours</span>
                      <span style={{color: 'var(--text-muted)'}}>Jours de repos</span>
                      <span style={{color: 'var(--text-primary)'}}>{selectedMatch.details.awayDaysRest} jours</span>
                    </div>
                    <div className="metric-row">
                      <span style={{color: 'var(--color-home)'}}>{selectedMatch.details.homeElo}</span>
                      <span style={{color: 'var(--text-muted)'}}>Puissance (Elo)</span>
                      <span style={{color: 'var(--color-away)'}}>{selectedMatch.details.awayElo}</span>
                    </div>
                  </div>

                  <div className="data-box" style={{gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '1.5rem'}}>
                    <div style={{fontSize: '3rem', lineHeight: 1, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.3))'}}>
                      {selectedMatch.details.weatherCode === 1 ? '☀️' : selectedMatch.details.weatherCode === 2 ? '🌥️' : '🌧️'}
                    </div>
                    <div>
                      <div className="data-box-title" style={{marginBottom: '0.3rem'}}>Impact de la Météo</div>
                      <div style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>
                        {selectedMatch.details.weatherCode === 1 ? 'Condition optimale (Terrain sec, jeu de passe rapide favorisé)' : 
                         selectedMatch.details.weatherCode === 2 ? 'Ciel très nuageux/Vent (Trajectoires de balle potentiellement impactées)' : 
                         'Forte Pluie (Terrain lourd, favorise les erreurs techniques et les combats physiques)'}
                      </div>
                    </div>
                  </div>

                  <div className="data-box" style={{gridColumn: '1 / -1', background: 'var(--instruction-bg)', borderColor: 'var(--glass-border)'}}>
                    <div className="data-box-title" style={{color: 'var(--color-accent)'}}>NOTRE CONSEIL PARIS</div>
                    <div style={{fontSize: '1.2rem', fontWeight: 600, color: 'var(--instruction-text)', display: 'flex', alignItems: 'center', gap: '10px'}}>
                      <Icons.zap size={24} /> {selectedMatch.recommendation}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="auth-gate-modal">
                  <div style={{fontSize: '3rem', marginBottom: '1rem'}}>🔒</div>
                  <h2>Analyse Verrouillée</h2>
                  <p>Inscrivez-vous ou activez un forfait pour débloquer les scores xG, les ratings Elo et l'instruction algorithmique finale.</p>
                  <button onClick={() => window.location.href='/pricing'} className="auth-submit">Voir les forfaits (Essai 7j)</button>
                  {!user && <Link href="/login" style={{marginTop: '1rem', color: 'var(--color-accent)', textDecoration: 'none', fontSize: '0.9rem'}}>Déjà inscrit ? Se connecter</Link>}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
      )}
    </>
  );
}
