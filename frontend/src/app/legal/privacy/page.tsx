import React from 'react';
import ContentHeader from '@/components/ContentHeader';

export default function PrivacyPage() {
  return (
    <>
      <ContentHeader />
      <main className="container" style={{ paddingTop: '4rem', maxWidth: '800px', minHeight: '80vh' }}>
        <h1 className="dashboard-title" style={{ marginBottom: '2rem', fontSize: '2.5rem' }}>Politique de Confidentialité</h1>
        
        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '1.05rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <p>Chez Next-Bet-AI, la confidentialité de vos données est une priorité absolue.</p>
          
          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>1. Collecte des Données</h2>
          <p>
            Nous collectons uniquement les données strictement nécessaires au fonctionnement de votre abonnement (Adresse e-mail, identifiant de compte Supabase). 
            Nous ne stockons pas directement de méthodes de paiement, ces données étant traitées de manière sécurisée par notre prestataire (Stripe).
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>2. Utilisation des Données</h2>
          <p>
            Votre adresse e-mail est utilisée exclusivement pour vous identifier sur le système, vous envoyer des récapitulatifs d'abonnement et des alertes sur des modifications majeures de l'algorithme.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>3. Non-Revente</h2>
          <p>
            <strong>Next-Bet-AI ne vendra jamais vos données.</strong> Contrairement aux courtiers et bookmakers, notre modèle économique repose à 100% sur l'efficacité technologique de notre SaaS et les abonnements premium de nos utilisateurs.
          </p>

          <h2 style={{ color: 'var(--text-primary)', marginTop: '1rem', fontSize: '1.5rem' }}>4. RGPD et Droits</h2>
          <p>
            Conformément à la réglementation européenne (RGPD), vous disposez d'un droit d'accès, de rectification et d'effacement inconditionnel de vos données depuis un simple clic dans les paramètres de votre compte.
          </p>
        </div>
      </main>
    </>
  );
}
