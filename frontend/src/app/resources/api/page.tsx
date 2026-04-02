import React from 'react';
import ContentHeader from '@/components/ContentHeader';

export default function ApiDocumentationPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <div style={{ display: 'inline-flex', padding: '6px 12px', background: 'rgba(14, 165, 233, 0.15)', color: 'var(--color-accent)', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 700, marginBottom: '1rem', letterSpacing: '1px' }}>
          DEVS ONLY
        </div>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem' }}>Documentation API (v2.4)</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>L'API de Next-Bet est construite sur une architecture FastAPI hautement asynchrone pour livrer l'inférence du modèle Deep Learning en moins de 45ms.</p>
          
          <div style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '1.5rem', marginTop: '1rem' }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem', fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ color: '#10b981', fontFamily: 'monospace', background: 'rgba(16,185,129,0.1)', padding: '4px 8px', borderRadius: '6px' }}>GET</span>
              /predict/upcoming
            </h3>
            <p style={{ fontSize: '0.95rem' }}>Retourne les inférences des 7 prochains jours combinant la probabilité native PyTorch et la détection Edge.</p>
            
            <div style={{ background: 'rgba(0,0,0,0.5)', padding: '1rem', borderRadius: '8px', fontFamily: 'monospace', color: '#a78bfa', marginTop: '1rem', overflowX: 'auto' }}>
              {`{
  "competition": "Ligue 1",
  "homeTeam": "PSG",
  "awayTeam": "Marseille",
  "date": "2026-04-12T19:00:00Z",
  "probabilities": {
    "home": 0.68,
    "draw": 0.19,
    "away": 0.13
  },
  "valueBet": { "active": true, "edge": 12.4 },
  "recommendation": "VICTOIRE PSG"
}`}
            </div>
          </div>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '2rem', fontSize: '1.5rem' }}>Accès & Rate Limit</h2>
          <p>
            L'accès programmatique via Clé API est pour l'instant réservé aux abonnements <strong>B2B Enterprise</strong>.
            Le grand public est invité à utiliser le Dashboard UI ou s'exposer à un ban automatique en cas de scraping intensif du frontend.
          </p>

          <p style={{ marginTop: '2rem', fontStyle: 'italic', opacity: 0.7 }}>
            La documentation Swagger complète sera exposée prochainement sur api.next-bet.ai/docs.
          </p>
        </div>
      </main>
    </>
  );
}
