'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';
import { updateSubscription } from '@/app/auth/actions';
import { useAuth } from '@/context/AuthContext';

export default function PricingPage() {
  const { user, profile, loading, refreshProfile } = useAuth();
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [expandedTiers, setExpandedTiers] = useState<Record<string, boolean>>({});
  const router = useRouter();

  const toggleDetails = (tierId: string) => {
    setExpandedTiers(prev => ({
      ...prev,
      [tierId]: !prev[tierId]
    }));
  };

  const handleSubscribe = async (tier: string) => {
    if (!user) {
      router.push(`/register?message=Créez un compte pour profiter de l'essai gratuit`);
      return;
    }

    setPurchasing(tier);
    
    try {
      const response = await fetch('http://localhost:8000/api/stripe/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user.id,
          tier: tier,
          cycle: billingCycle,
        }),
      });

      const data = await response.json();
      
      if (data.url) {
        // Redirection vers Stripe Checkout
        window.location.href = data.url;
      } else {
        throw new Error(data.detail || "Erreur lors de la création de la session Stripe");
      }
    } catch (err: any) {
      console.error("Stripe Error:", err);
      alert(`Erreur : ${err.message || "Impossible de lancer le paiement"}`);
      setPurchasing(null);
    }
  };

  const tiers = [
    {
      id: 'ligue1',
      name: 'Ligue 1 Origin',
      price: billingCycle === 'monthly' ? '14.99' : '12.49',
      features: ['Accès illimité aux matchs de Ligue 1', 'Pronostics IA (Scores)', 'Infos blessures en temps réel'],
      technical: ['Algorithme xG & xPts', 'Calculateur d\'avantage ELO', 'Index de forme Understat'],
      color: 'var(--color-home)',
      grad: 'linear-gradient(135deg, #0ea5e9, #2563eb)',
      trial: true
    },
    {
      id: 'pl',
      name: 'Premier League Elite',
      price: billingCycle === 'monthly' ? '14.99' : '12.49',
      features: ['Accès illimité aux matchs de Premier League', 'Pronostics IA (Scores)', 'Infos blessures en temps réel'],
      technical: ['Algorithme xG & xPts', 'Calculateur d\'avantage ELO', 'Index de forme Understat'],
      color: '#a855f7',
      grad: 'linear-gradient(135deg, #a855f7, #7c3aed)',
      trial: true
    },
    {
      id: 'ultimate',
      name: 'Ultimate AI Pass',
      price: billingCycle === 'monthly' ? '24.99' : '19.99',
      features: ['Ligue 1 + Premier League', 'Détection des Value Bets (Edge)', 'Impact météo & Actus'],
      technical: ['Pipeline d\'agrégation RSS', 'Réseau de neurones PyTorch', 'Données météo Open-Meteo'],
      color: 'var(--color-accent)',
      grad: 'linear-gradient(135deg, #f59e0b, #d97706)',
      trial: false,
      popular: true
    }
  ];

  return (
    <div className="pricing-wrapper">
      <header className="pricing-header">
        <Logo width={220} height={55} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <Link href="/" className="back-link">← Retour à l'accueil</Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ThemeToggle />
            <UserNav />
          </div>
        </div>
      </header>

      <main className="pricing-container">
        <div className="pricing-intro">
          <h1 className="title">Choisissez votre Arsenal</h1>
          <p className="subtitle">
            Passez au niveau supérieur avec nos analyses neuronales avancées.
          </p>

          <div className="billing-toggle-container">
            <span className={billingCycle === 'monthly' ? 'active' : ''}>Mensuel</span>
            <button
              className="billing-switch"
              onClick={() => setBillingCycle(prev => prev === 'monthly' ? 'yearly' : 'monthly')}
            >
              <div className={`switch-knob ${billingCycle === 'yearly' ? 'yearly' : ''}`} />
            </button>
            <span className={billingCycle === 'yearly' ? 'active' : ''}>
              Annuel <span className="discount-tag">-20%</span>
            </span>
          </div>
        </div>

        <div className="pricing-grid">
          {tiers.map((tier) => (
            <div key={tier.id} className={`pricing-card ${tier.popular ? 'popular' : ''} ${profile?.subscription_tier === tier.id ? 'current' : ''}`}>
              {tier.popular && <div className="popular-badge">Plus Populaire</div>}

              <div className="card-header">
                <h2 className="tier-name">{tier.name}</h2>
                <div className="price-box">
                  <span className="currency">€</span>
                  <span className="amount">{tier.price}</span>
                  <span className="period">/mois</span>
                </div>
                {tier.trial && !profile?.is_trial_used && (
                  <div className="trial-badge">7 jours d'essai offerts</div>
                )}
              </div>

              <ul className="features-list">
                {tier.features.map((feat, i) => (
                  <li key={i} className="feature-item">
                    <svg className="check-icon" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {feat}
                  </li>
                ))}
              </ul>

              <div className="technical-section">
                <button
                  className="details-toggle"
                  onClick={() => toggleDetails(tier.id)}
                >
                  {expandedTiers[tier.id] ? 'Masquer les détails' : 'Détails techniques...'}
                </button>

                {expandedTiers[tier.id] && (
                  <ul className="technical-list">
                    {tier.technical.map((tech, i) => (
                      <li key={i} className="tech-item">
                        <div className="dot"></div> {tech}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <button
                onClick={() => handleSubscribe(tier.id)}
                disabled={purchasing !== null || profile?.subscription_tier === tier.id}
                className="subscribe-btn"
                style={{ background: tier.grad }}
              >
                {purchasing === tier.id ? 'Traitement...' :
                  profile?.subscription_tier === tier.id ? 'Forfait Actuel' :
                    tier.trial && !profile?.is_trial_used ? 'Démarrer l\'essai' : 'S\'abonner'}
              </button>
            </div>
          ))}
        </div>

        <div className="pricing-faq">
          <p>Pas d'engagement, annulez quand vous voulez.</p>
          <p style={{ marginTop: '0.5rem', opacity: 0.6, fontSize: '0.8rem' }}>
            *L'offre d'essai est réservée aux nouveaux utilisateurs et s'applique uniquement à une ligue individuelle.
          </p>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="footer-grid">
          <div className="footer-col">
            <div className="header-logo" style={{ marginBottom: '1.5rem', justifyContent: 'flex-start' }}>
              <Logo width={180} height={45} />
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6' }}>
              L'intelligence artificielle conçue exclusivement pour surpasser les marchés sportifs. Base ta stratégie sur des mathématiques, pas sur des émotions.
            </p>
          </div>
          <div className="footer-col">
            <h4>Produit</h4>
            <div className="footer-links">
              <Link href="/dashboard">Dashboard Live</Link>
              <Link href="/pricing">Tarifs & Forfaits</Link>
              <Link href="/register">S'inscrire</Link>
            </div>
          </div>
          <div className="footer-col">
            <h4>Ressources</h4>
            <div className="footer-links">
              <Link href="/resources/api">Documentation API</Link>
              <Link href="/resources/model">Modèle PyTorch</Link>
              <Link href="/resources/xg">Méthodologie xG</Link>
            </div>
          </div>
          <div className="footer-col">
            <h4>Légal</h4>
            <div className="footer-links">
              <Link href="/legal/terms">Conditions d'Utilisation</Link>
              <Link href="/legal/privacy">Politique de Confidentialité</Link>
              <Link href="/legal/responsible-gaming">Jeu Responsable</Link>
            </div>
          </div>
        </div>
        <div className="footer-bottom" style={{ textAlign: 'center', paddingTop: '2rem', borderTop: '1px solid var(--glass-border)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          <p>&copy; {new Date().getFullYear()} Next-Bet-AI. Engineered with PyTorch & Next.js. Tous droits réservés.</p>
        </div>
      </footer>

      <style>{`
        .pricing-wrapper {
          min-height: 100vh;
          background: var(--bg-gradient);
          color: var(--text-primary);
          padding: 2rem;
        }

        .pricing-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          max-width: 1200px;
          margin: 0 auto 4rem;
          position: relative;
          z-index: 50;
        }

        .back-link {
          color: var(--text-secondary);
          text-decoration: none;
          font-weight: 600;
          transition: color 0.2s;
        }

        .back-link:hover {
          color: var(--color-accent);
        }

        .pricing-container {
          max-width: 1200px;
          margin: 0 auto;
        }

        .pricing-intro {
          text-align: center;
          margin-bottom: 5rem;
        }

        .title {
          font-size: 3.5rem;
          font-weight: 900;
          margin-bottom: 1rem;
          letter-spacing: -1px;
        }

        .subtitle {
          color: var(--text-secondary);
          font-size: 1.2rem;
          max-width: 600px;
          margin: 0 auto 2.5rem;
        }

        .billing-toggle-container {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 15px;
          margin-bottom: 2rem;
          font-weight: 700;
          font-size: 0.95rem;
        }

        .billing-toggle-container span {
          color: var(--text-muted);
          transition: color 0.3s;
        }

        .billing-toggle-container span.active {
          color: var(--text-primary);
        }

        .discount-tag {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
          padding: 2px 8px;
          border-radius: 8px;
          font-size: 0.75rem;
          margin-left: 4px;
        }

        .billing-switch {
          width: 54px;
          height: 28px;
          background: rgba(255,255,255,0.08);
          border: 1px solid var(--glass-border);
          border-radius: 20px;
          position: relative;
          cursor: pointer;
          transition: all 0.3s;
        }

        .switch-knob {
          width: 20px;
          height: 20px;
          background: var(--color-accent);
          border-radius: 50%;
          position: absolute;
          top: 3.5px;
          left: 4px;
          transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 2px 8px rgba(14, 165, 233, 0.4);
        }

        .switch-knob.yearly {
          transform: translateX(24px);
          background: #f59e0b;
          box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
        }

        .pricing-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 2.5rem;
          margin-bottom: 5rem;
        }

        .pricing-card {
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: 32px;
          padding: 3rem 2rem;
          display: flex;
          flex-direction: column;
          position: relative;
          transition: transform 0.3s ease, border-color 0.3s ease;
        }

        .pricing-card:hover {
          transform: translateY(-10px);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .pricing-card.popular {
          border-color: var(--color-accent);
          background: rgba(245, 158, 11, 0.05);
          backdrop-filter: blur(40px);
        }

        .popular-badge {
          position: absolute;
          top: 0;
          left: 50%;
          transform: translate(-50%, -50%);
          background: var(--color-accent);
          color: white;
          padding: 8px 20px;
          border-radius: 20px;
          font-weight: 800;
          font-size: 0.8rem;
          text-transform: uppercase;
        }

        .card-header {
          text-align: center;
          margin-bottom: 2.5rem;
        }

        .tier-name {
          font-size: 1.5rem;
          font-weight: 800;
          margin-bottom: 1.5rem;
        }

        .price-box {
          display: flex;
          align-items: baseline;
          justify-content: center;
          margin-bottom: 1rem;
        }

        .currency { font-size: 1.5rem; font-weight: 600; margin-right: 2px; }
        .amount { font-size: 4rem; font-weight: 900; letter-spacing: -2px; }
        .period { color: var(--text-secondary); font-size: 1rem; }

        .trial-badge {
          color: #34d399;
          font-size: 0.9rem;
          font-weight: 700;
        }

        .features-list {
          list-style: none;
          padding: 0;
          margin: 0 0 3rem;
          flex-grow: 1;
        }

        .feature-item {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 1rem;
          color: var(--text-secondary);
          font-weight: 500;
        }

        .check-icon {
          width: 20px;
          height: 20px;
          color: #34d399;
        }

        .subscribe-btn {
          width: 100%;
          padding: 1.2rem;
          border: none;
          border-radius: 16px;
          color: white;
          font-size: 1.1rem;
          font-weight: 800;
          cursor: pointer;
          transition: transform 0.2s, box-shadow 0.2s;
        }

        .subscribe-btn:hover:not(:disabled) {
          transform: scale(1.02);
          box-shadow: 0 15px 30px -10px rgba(0,0,0,0.3);
        }

        .subscribe-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          filter: grayscale(1);
        }

        .technical-section {
          margin-bottom: 2rem;
          padding-top: 1rem;
          border-top: 1px solid var(--glass-border);
        }

        .details-toggle {
          background: transparent;
          border: none;
          color: var(--color-accent);
          font-size: 0.85rem;
          font-weight: 700;
          cursor: pointer;
          padding: 0;
          margin-bottom: 1rem;
          text-decoration: underline;
          text-underline-offset: 4px;
          opacity: 0.8;
          transition: opacity 0.2s;
        }

        .details-toggle:hover {
          opacity: 1;
        }

        .technical-list {
          list-style: none;
          padding: 0;
          margin: 0;
          animation: slideDown 0.3s ease-out;
        }

        .tech-item {
          font-size: 0.8rem;
          color: var(--text-muted);
          margin-bottom: 0.5rem;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .tech-item .dot {
          width: 4px;
          height: 4px;
          background: var(--text-muted);
          border-radius: 50%;
        }

        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-5px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .pricing-faq {
          text-align: center;
          color: var(--text-secondary);
          font-weight: 500;
          margin-bottom: 6rem;
        }

        /* Enhanced Footer Compatibility */
        .landing-footer { border-top: 1px solid var(--glass-border); padding: 5rem 2rem 2rem; background: rgba(0,0,0,0.2); margin-top: 8rem; margin-left: -2rem; margin-right: -2rem; }
        [data-theme='light'] .landing-footer { background: rgba(255,255,255,0.5); }
        .footer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 3rem; max-width: 1100px; margin: 0 auto 4rem; }
        .footer-col h4 { font-size: 1.1rem; margin-bottom: 1.5rem; color: var(--text-primary); }
        .footer-links { display: flex; flex-direction: column; gap: 0.8rem; }
        .footer-links a { color: var(--text-secondary); text-decoration: none; transition: color 0.2s; font-size: 0.95rem; }
        .footer-links a:hover { color: var(--color-accent); }

        @media (max-width: 768px) {
          .title { font-size: 2.5rem; }
        }
      `}</style>
    </div>
  );
}
