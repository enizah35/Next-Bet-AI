import React from 'react';
import ContentHeader from '@/components/ContentHeader';

export default function ResponsibleGamingPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem', background: 'linear-gradient(to right, #ef4444, #f59e0b)', WebkitBackgroundClip: 'text' }}>Jeu Responsable</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>
            Chez Next-Bet-AI, bien que nous traitions les paris sportifs comme un marché d'investissement boursier guidé par les statistiques,
            nous tenons à vous rappeler que les paris impliquent des risques financiers importants.
          </p>

          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '2rem', borderRadius: '16px', color: '#fca5a5' }}>
            <h2 style={{ color: '#ef4444', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '1.5rem' }}>⚠️</span> Prévention de l'addiction
            </h2>
            <p>
              Jouez avec modération. <strong>L'argent doit avant tout servir à vivre.</strong><br/>
              Si vous sentez que vous perdez le contrôle, que vous jouez pour vous refaire ou que cela impacte votre santé mentale, 
              arrêtez immédiatement et cherchez de l'aide professionnelle.
            </p>
            <p style={{ marginTop: '1rem' }}>
              En France, contacter <strong>Joueurs Info Service</strong> : 09 74 75 13 13 (Appel non surtaxé).
            </p>
          </div>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>Gestion de Bankroll</h2>
          <p>
            Même avec un algorithme présentant un 'Edge' (Avantage) de 55%, vous doper sur la variance reste dangereux.
            Nous déconseillons fortement de miser plus de <strong>1.5% de votre capital total (Bankroll)</strong> par "Value Bet" conseillé par l'IA.
          </p>
          
          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>Auto-Exclusion</h2>
          <p>
            Si vous souhaitez bloquer votre accès à nos prédictions d'IA afin de limiter vos tentations de jeu, contactez instantanément notre équipe de support. Nous procèderons à la clôture immédiate de votre compte Next-Bet-AI sans possibilité de réactivation sous 6 mois.
          </p>
        </div>
      </main>
    </>
  );
}
