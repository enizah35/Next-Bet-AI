import React from 'react';
import ContentHeader from '@/components/ContentHeader';

export default function TermsPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem' }}>Conditions d'Utilisation</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>Dernière mise à jour : 2 Avril 2026</p>
          
          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>1. Acceptation des conditions</h2>
          <p>
            En accédant au service Next-Bet-AI, vous acceptez d'être lié par les présentes Conditions d'Utilisation, 
            toutes les lois et réglementations applicables, et acceptez que vous êtes responsable du respect des lois locales applicables.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>2. Absence de Garantie Financière</h2>
          <p>
            Next-Bet-AI fournit des analyses statistiques et des probabilités basées sur des modèles de Machine Learning (PyTorch). 
            Aucun résultat sportif n'est garanti. Les "Value Bets" identifiés représentent un avantage <strong>mathématique</strong> sur le long terme, mais n'éliminent en aucun cas la variance. 
            L'entreprise n'est pas responsable de vos pertes financières.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>3. Propriété Intellectuelle</h2>
          <p>
            L'algorithme de détection, les modèles pré-entrainés, l'interface graphique et l'ensemble du code de calcul xG 
            sont la propriété exclusive de Next-Bet-AI. Toute rétro-ingénierie ou revente des pronostics sans licence d'API commerciale est strictement interdite.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>4. Abonnements et Remboursements</h2>
          <p>
            Les abonnements récurrents sont facturés mensuellement ou annuellement et s'annulent à tout moment depuis votre tableau de bord. 
            Étant donné la nature numérique et instantanée de nos analyses, aucun remboursement partiel ou total ne sera accordé pour la période en cours.
          </p>
        </div>
      </main>
    </>
  );
}
