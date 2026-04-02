import React from 'react';
import ContentHeader from '@/components/ContentHeader';
import Link from 'next/link';

export default function XGMethodologyPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <div style={{ display: 'inline-flex', padding: '6px 12px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 700, marginBottom: '1rem', letterSpacing: '1px' }}>
          DATA SCIENCE
        </div>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem' }}>Méthodologie xG (Expected Goals)</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>
            Pourquoi Next-Bet-AI ignorait-il délibérément le nombre de buts marqués dans ses calculs d'entraînement pour se fier presque uniquement aux <strong>xG (Expected Goals)</strong> ?
          </p>
          
          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>1. La faille du tableau des scores</h2>
          <p>
            Au football, le score final ment souvent. Une équipe peut dominer 90 minutes, tirer 25 fois, toucher le poteau 3 fois et perdre 1-0 sur un contre chanceux. 
            Modéliser la future performance d'une équipe sur ses buts effectifs incorpore une <strong>variance massive et de la chance</strong> dans l'équation.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>2. La Révolution xG</h2>
          <p>
            L'Expected Goal quantifie la <strong>qualité</strong> d'une occasion. Un penalty vaut 0.79 xG. Un tir de 35 mètres vaut 0.02 xG.
            En faisant la somme des xG sur un match, nous obtenons la production <em>réelle</em> et méritée de l'équipe.
          </p>
          <p>
            Next-Bet-AI (via Understat) calcule la forme "Glissante" (Rolling Form) des 5 derniers matchs d'une équipe en se basant sur le différentiel moyen xG (xG Créés - xG Concédés).
            C'est l'indicateur le plus puissant à ce jour pour prédire le momentum d'un club.
          </p>

          <div style={{ background: 'url(/assets/noise.png), linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9))', padding: '2rem', borderRadius: '16px', border: '1px solid var(--glass-border)', marginTop: '1rem' }}>
            <h3 style={{ color: 'white', marginBottom: '1rem', fontSize: '1.3rem' }}>L'intégration dans PyTorch</h3>
            <p style={{ color: '#cbd5e1' }}>
              Le réseau neuronal de notre <Link href="/resources/model" style={{color: 'var(--color-accent)'}}>système central</Link> reçoit ces données normalisées via un StandardScaler. L'IA apprend ainsi à reconnaître des clubs sous-performants (qui ont un gros xG mais n'arrivent pas encore à marquer) avant que le marché des bookmakers ne s'en rende compte.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
