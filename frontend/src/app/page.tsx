// Server Component Landing Page

import React from 'react';
import Link from 'next/link';
import { cookies } from 'next/headers';
import { createClient } from '@/utils/supabase/server';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';

import { Icons } from '@/components/Icons';

export default async function LandingPage() {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();

  const ctaDashboard = user ? "/dashboard" : "/login";
  const ctaPricing = user ? "/pricing" : "/register";

  return (
    <div className="landing-wrapper">
      <header className="header" style={{ background: "transparent", borderBottom: "none" }}>
        <div className="header-logo">
          <Logo width={220} height={55} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <Link href="/pricing" className="nav-link">Forfaits</Link>
          <ThemeToggle />
          <UserNav />
        </div>
      </header>

      <main className="landing-main">
        {/* Hero Section */}
        <section className="hero">
          <div className="hero-badge">
            <Icons.cpu size={24} /> <span style={{marginLeft: '8px'}}>AI Powered Prediction v2.4</span>
          </div>
          <h1 className="hero-title">
            Dominez le Terrain avec <br />
            <span className="accent-text">l'Intelligence Artificielle</span>
          </h1>
          <p className="hero-subtitle">
            Next-Bet-AI fusionne le Deep Learning PyTorch avec l'analyse xG en temps réel pour vous offrir un avantage mathématique inédit sur la Ligue 1 et la Premier League.
          </p>
          <div className="hero-ctas">
            <Link href={ctaDashboard} className="cta-primary">Consulter les Analyses LIVE</Link>
            <Link href={ctaPricing} className="cta-secondary">Démarrer l'essai 7j gratuit</Link>
          </div>
        </section>

        {/* Feature Grid */}
        <section className="features">
          <div className="feature-card">
            <div className="icon-box"><Icons.zap size={24} /></div>
            <h3>Pipeline Temps Réel</h3>
            <p>Ingestion instantanée des stats Understat, blessures et flux météo locaux.</p>
          </div>
          <div className="feature-card">
            <div className="icon-box"><Icons.trendingUp size={24} /></div>
            <h3>Détection de Value</h3>
            <p>Algorithme exclusif identifiant les écarts de cotes (Edge) avec 55.3% d'accuracy.</p>
          </div>
          <div className="feature-card">
            <div className="icon-box"><Icons.check size={24} /></div>
            <h3>Multi-Ligues</h3>
            <p>Couverture totale de la Ligue 1 et de la Premier League avec modèles dédiés.</p>
          </div>
        </section>

        {/* Mock Card Preview Section */}
        <section className="preview-section">
          <h2 className="section-title">Aperçu de la Performance</h2>
          <div className="preview-container">
            {/* Mock Match Card */}
            <div className="match-card mock-card">
              <div className="match-header">
                <span className="competition-badge">PREMIER LEAGUE</span>
                <span style={{opacity: 0.7}}>Dimanche, 16:30</span>
              </div>
              <div className="badge badge-value" style={{ width: 'fit-content' }}>
                <Icons.trendingUp size={20} /> VALUE BET (8.4% EDGE)
              </div>
              <div className="recommendation-banner" style={{background: 'var(--color-accent)', color: 'white'}}>
                 <Icons.zap size={20} /> VICTOIRE MAN CITY (AI CONFIDENCE: HIGH)
              </div>
              <div className="match-teams" style={{marginTop: '1.5rem'}}>
                <div className="team"><span className="team-name">Man City</span></div>
                <div className="vs">VS</div>
                <div className="team"><span className="team-name">Arsenal</span></div>
              </div>
              <div className="prediction-section">
                <div className="prob-bar-container">
                  <div className="prob-segment" style={{ width: '48%', background: '#3b82f6' }}></div>
                  <div className="prob-segment" style={{ width: '24%', background: '#64748b' }}></div>
                  <div className="prob-segment" style={{ width: '28%', background: '#ef4444' }}></div>
                </div>
                <div className="prob-labels">
                  <span>Home 48%</span>
                  <span>Draw 24%</span>
                  <span>Away 28%</span>
                </div>
              </div>
            </div>
            
            {/* Dark Mode Modal Preview Card */}
            <div className="match-card mock-card detail-preview">
               <h3 style={{color: 'var(--color-accent)', fontSize: '0.9rem', marginBottom: '1rem'}}>AI DEEP EVALUATION</h3>
               <div className="metric-row">
                 <span>84 / 100</span>
                 <span style={{color: 'var(--text-muted)'}}>Index de Forme xG</span>
                 <span>72 / 100</span>
               </div>
               <div className="metric-row" style={{border: 'none'}}>
                 <span>1842 pts</span>
                 <span style={{color: 'var(--text-muted)'}}>ELO Rating</span>
                 <span>1798 pts</span>
               </div>
               <div className="weather-preview">☀️ Terrain sec - Jeu rapide favorisé</div>
            </div>
          </div>
        </section>
        {/* Comment ça marche */}
        <section className="steps-section">
          <h2 className="section-title">Comment ça marche ?</h2>
          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">1</div>
              <h3 style={{marginTop: '1rem', marginBottom: '0.8rem'}}>Synchronisation Live</h3>
              <p style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>L'IA collecte automatiquement les derniers xG, la météo et les rapports de blessures.</p>
            </div>
            <div className="step-card">
              <div className="step-number">2</div>
              <h3 style={{marginTop: '1rem', marginBottom: '0.8rem'}}>Analyse Neuronale</h3>
              <p style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>Le modèle Deep Learning traite instantanément l'historique et génère des probabilités pour chaque issue.</p>
            </div>
            <div className="step-card">
              <div className="step-number">3</div>
              <h3 style={{marginTop: '1rem', marginBottom: '0.8rem'}}>Extraction de Value</h3>
              <p style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>Les probabilités sont comparées aux cotes réelles. Seules les anomalies mathématiques vous sont présentées.</p>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="faq-section">
          <h2 className="section-title" style={{marginBottom: '3rem'}}>Questions Fréquentes</h2>
          <details className="faq-item">
            <summary>Quel est le taux de réussite (Accuracy) du modèle ?</summary>
            <div className="faq-content">
              Notre modèle PyTorch actuel (v2.4) maintient une précision certifiée de 55.3% sur un volume de plus de 10 000 matchs analysés, surpassant significativement la baseline globale du marché des bookmakers.
            </div>
          </details>
          <details className="faq-item">
            <summary>Sur quelles ligues Next-Bet-AI fonctionne-t-il ?</summary>
            <div className="faq-content">
              Actuellement, l'algorithme est formellement calibré et optimisé pour la <strong>Ligue 1 (France)</strong> et la <strong>Premier League (Angleterre)</strong>. Nous intégrons d'autres ligues seulement lorsque l'IA atteint notre seuil d'exigence (edge &gt; 5%).
            </div>
          </details>
          <details className="faq-item">
            <summary>Comment fonctionne la détection de "Value Bet" ?</summary>
            <div className="faq-content">
              L'IA calcule la vraie probabilité mathématique d'un événement (ex: Victoire de l'équipe locale à 50% = cote théorique de 2.0). Si le bookmaker propose une cote à 2.30, l'algorithme identifie une "Value" et la met en évidence.
            </div>
          </details>
          <details className="faq-item">
            <summary>Est-ce que je peux essayer gratuitement ?</summary>
            <div className="faq-content">
              Oui, tout nouveau compte bénéficie automatiquement de 7 jours d'essai gratuit sur toutes les ligues, sans engagement. Vous aurez accès aux analyses complètes du dashboard.
            </div>
          </details>
        </section>
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
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} Next-Bet-AI. Engineered with PyTorch & Next.js. Tous droits réservés.</p>
        </div>
      </footer>

      <style>{`
        .landing-wrapper {
          min-height: 100vh;
          background: radial-gradient(circle at top right, rgba(245, 158, 11, 0.05), transparent),
                      radial-gradient(circle at bottom left, rgba(59, 130, 246, 0.05), transparent),
                      var(--bg-darker);
          padding: 0 2rem;
        }

        .nav-link {
          color: var(--text-secondary);
          text-decoration: none;
          font-weight: 700;
          font-size: 0.95rem;
          transition: all 0.3s ease;
          padding: 8px 16px;
          border-radius: 12px;
        }

        .nav-link:hover { 
          color: var(--text-primary); 
          background: rgba(255, 255, 255, 0.05);
        }

        .landing-main {
          max-width: 1100px;
          margin: 0 auto;
          padding-top: 6rem;
        }

        .hero {
          text-align: center;
          margin-bottom: 8rem;
          animation: fadeInUp 0.8s ease-out;
        }

        .hero-badge {
          display: inline-flex;
          align-items: center;
          background: rgba(255,255,255,0.05);
          padding: 8px 16px;
          border-radius: 20px;
          color: var(--color-accent);
          font-size: 0.85rem;
          font-weight: 700;
          margin-bottom: 2rem;
          border: 1px solid rgba(245, 158, 11, 0.2);
        }

        .hero-title {
          font-size: 4.5rem;
          font-weight: 900;
          line-height: 1.1;
          letter-spacing: -2px;
          margin-bottom: 1.5rem;
        }

        .accent-text {
          background: linear-gradient(135deg, var(--color-accent), #f59e0b);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
          font-size: 1.25rem;
          color: var(--text-secondary);
          max-width: 700px;
          margin: 0 auto 3rem;
          line-height: 1.6;
        }

        .hero-ctas {
          display: flex;
          gap: 1.5rem;
          justify-content: center;
          align-items: center;
        }

        .cta-primary {
          background: linear-gradient(135deg, #f59e0b, var(--color-accent));
          color: white;
          padding: 1.2rem 2.5rem;
          border-radius: 18px;
          font-weight: 900;
          text-decoration: none;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 0 20px rgba(245, 158, 11, 0.3),
                      inset 0 1px 1px rgba(255, 255, 255, 0.2);
          display: flex;
          align-items: center;
          gap: 12px;
          position: relative;
          overflow: hidden;
          animation: buttonPulse 3s infinite;
        }

        @keyframes buttonPulse {
          0% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.3); }
          50% { box-shadow: 0 0 35px rgba(245, 158, 11, 0.6); }
          100% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.3); }
        }

        .cta-primary:hover {
          transform: translateY(-3px) scale(1.02);
          filter: brightness(1.1);
        }

        .cta-secondary {
          background: rgba(255, 255, 255, 0.03);
          color: white;
          padding: 1.2rem 2.5rem;
          border-radius: 18px;
          font-weight: 700;
          text-decoration: none;
          border: 1px solid var(--glass-border);
          transition: all 0.3s ease;
          backdrop-filter: blur(10px);
        }

        .cta-secondary:hover { 
          background: rgba(255, 255, 255, 0.08);
          border-color: rgba(255, 255, 255, 0.3);
          transform: translateY(-2px);
        }

        .features {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 2rem;
          margin-bottom: 8rem;
        }

        .feature-card {
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          padding: 2.5rem;
          border-radius: 24px;
          transition: transform 0.3s;
        }

        .feature-card:hover { transform: translateY(-5px); }

        .icon-box {
          width: 48px;
          height: 48px;
          background: rgba(245, 158, 11, 0.1);
          color: var(--color-accent);
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 1.5rem;
        }

        .feature-card h3 { font-size: 1.3rem; margin-bottom: 1rem; }
        .feature-card p { color: var(--text-secondary); line-height: 1.5; }

        .preview-section {
          background: rgba(245, 158, 11, 0.02);
          border-radius: 40px;
          padding: 4rem;
          border: 1px solid var(--glass-border);
          margin-bottom: 8rem;
        }

        .section-title {
           text-align: center;
           font-size: 2.5rem;
           font-weight: 800;
           margin-bottom: 4rem;
        }

        .preview-container {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
          gap: 3rem;
          perspective: 1000px;
        }

        .mock-card {
          width: 100% !important;
          max-width: 450px;
          margin: 0 auto;
          transform: rotateY(-10deg) rotateX(5deg);
          box-shadow: 0 30px 60px -12px rgba(0,0,0,0.5);
          transition: transform 0.4s;
        }

        .detail-preview {
          transform: rotateY(10deg) rotateX(5deg);
        }

        .mock-card:hover { transform: scale(1.02); }

        .weather-preview {
           margin-top: 1.5rem;
           padding-top: 1rem;
           border-top: 1px solid var(--glass-border);
           color: var(--text-secondary);
           font-size: 0.9rem;
        }

        /* Steps Section */
        .steps-section { margin-bottom: 8rem; }
        .steps-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2.5rem; padding-top: 1rem; }
        .step-card { text-align: center; padding: 2.5rem 1.5rem; background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 24px; position: relative; transition: transform 0.3s ease; }
        .step-card:hover { transform: translateY(-5px); border-color: var(--glass-border-hover); }
        .step-number { position: absolute; top: -20px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, var(--color-accent), #f59e0b); color: white; width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; border: 4px solid var(--bg-darker); box-shadow: 0 4px 10px rgba(0,0,0,0.3); }

        /* FAQ Section */
        .faq-section { max-width: 800px; margin: 0 auto 8rem; }
        .faq-item { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 16px; margin-bottom: 1rem; overflow: hidden; transition: all 0.3s ease; }
        .faq-item:hover { border-color: var(--color-accent); }
        .faq-item summary { padding: 1.5rem; font-size: 1.05rem; font-weight: 600; cursor: pointer; list-style: none; position: relative; display: flex; justify-content: space-between; align-items: center; color: var(--text-primary); }
        .faq-item summary::-webkit-details-marker { display: none; }
        .faq-item summary::after { content: '+'; font-size: 1.5rem; color: var(--color-accent); transition: transform 0.3s ease; font-weight: 400; }
        .faq-item[open] summary::after { transform: rotate(45deg); }
        .faq-content { padding: 0 1.5rem 1.5rem; color: var(--text-secondary); line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 0.5rem; padding-top: 1.2rem; font-size: 0.95rem; }

        /* Enhanced Footer */
        .landing-footer { border-top: 1px solid var(--glass-border); padding: 5rem 2rem 2rem; background: rgba(0,0,0,0.2); margin-top: 4rem; }
        [data-theme='light'] .landing-footer { background: rgba(255,255,255,0.5); }
        .footer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 3rem; max-width: 1100px; margin: 0 auto 4rem; }
        .footer-col h4 { font-size: 1.1rem; margin-bottom: 1.5rem; color: var(--text-primary); }
        .footer-links { display: flex; flex-direction: column; gap: 0.8rem; }
        .footer-links a { color: var(--text-secondary); text-decoration: none; transition: color 0.2s; font-size: 0.95rem; }
        .footer-links a:hover { color: var(--color-accent); }
        .footer-bottom { text-align: center; padding-top: 2rem; border-top: 1px solid var(--glass-border); color: var(--text-muted); font-size: 0.85rem; }

        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 768px) {
          .hero-title { font-size: 2.5rem; }
          .hero-subtitle { font-size: 1rem; }
          .preview-section { padding: 2rem; }
        }
      `}</style>
    </div>
  );
}
