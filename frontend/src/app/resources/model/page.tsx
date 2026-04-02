import React from 'react';
import ContentHeader from '@/components/ContentHeader';

export default function ModelPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <div style={{ display: 'inline-flex', padding: '6px 12px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 700, marginBottom: '1rem', letterSpacing: '1px' }}>
          PAPER & RESEARCH
        </div>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem' }}>Le Modèle Deep Learning</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>
            Depuis la version 2.0, Next-Bet-AI a abandonné les arbres de décision classiques (XGBoost/LightGBM) 
            au profit d'un réseau de neurones <strong>PyTorch</strong> calibré pour le traitement tabulaire de séries temporelles spatiales.
          </p>
          
          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>Architecture</h2>
          <p>
            Notre `MatchPredictor` est un réseau Feed-Forward robuste conçu autour de :
          </p>
          <ul style={{ listStyleType: 'disc', paddingLeft: '2rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            <li><strong>Couches Linéaires Denses</strong> équipées de Batch Normalization pour accélérer la convergence.</li>
            <li><strong>Mish Activations</strong> : Supérieures au classique ReLU pour préserver des petits gradients négatifs cruciaux dans l'analyse de signaux très bruités (le football).</li>
            <li><strong>Dropout (0.3)</strong> : Pour forcer le modèle à généraliser. En football, l'overfitting (surentraînement) est l'ennemi numéro un.</li>
          </ul>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>Entraînement</h2>
          <p>
            L'algorithme s'entraîne sur un dataset compilé via un pipeline complexe de 10 ans de données (Understat, Météo, Classements ELO).
            Il utilise la <strong>Cross Entropy Loss</strong> pour générer des probabilités souples pour les trois issues (1N2) plutôt qu'un choix binaire strict.
          </p>

          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '12px', border: '1px solid var(--glass-border)', marginTop: '1rem' }}>
            <h3 style={{ color: 'white', marginBottom: '0.5rem' }}>Statistiques de Base (Split Clos)</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginTop: '1rem' }}>
              <div>
                <span style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--color-accent)' }}>55.3%</span>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Accuracy de test</div>
              </div>
              <div>
                <span style={{ fontSize: '2rem', fontWeight: 800, color: '#10b981' }}>0.0124</span>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Learning Rate Opti</div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
