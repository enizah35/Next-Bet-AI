'use client'

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { signup } from '../auth/actions';
import Logo from '@/components/Logo';

function RegisterContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get('error');
  const [agreed, setAgreed] = useState(false);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href="/" className="back-to-home">← Retour</Link>
        <div className="auth-header">
          <Logo width={200} height={50} />
          <h1 style={{ marginTop: '1.5rem', fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Inscription
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.5rem' }}>
            Rejoignez la révolution de la prédiction sportive
          </p>
        </div>

        <form action={signup} className="auth-form">
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              placeholder="votre@email.com"
              required
              className="auth-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Mot de passe</label>
            <input
              id="password"
              name="password"
              type="password"
              placeholder="6+ caractères"
              required
              minLength={6}
              className="auth-input"
            />
          </div>

          <div className="form-group checkbox-group">
            <input 
              type="checkbox" 
              id="rgpd-consent" 
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              required
            />
            <label htmlFor="rgpd-consent">
              J'accepte les <Link href="/legal/terms" target="_blank">Conditions d'Utilisation</Link> et la <Link href="/legal/privacy" target="_blank">Politique de Confidentialité</Link>.
            </label>
          </div>

          {error && (
            <div className="auth-error">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          <button type="submit" className="auth-submit" disabled={!agreed}>
            Créer un compte
          </button>
        </form>

        <div className="auth-footer">
          Déjà un compte ?{' '}
          <Link href="/login" className="auth-link">
            Se connecter
          </Link>
        </div>
      </div>

      <style jsx>{`
        .auth-container {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: radial-gradient(circle at top right, rgba(245, 158, 11, 0.1), transparent),
                      radial-gradient(circle at bottom left, rgba(59, 130, 246, 0.1), transparent),
                      var(--bg-darker);
          padding: 2rem;
          position: relative;
        }

        .back-to-home {
          position: absolute;
          top: 1.5rem;
          left: 1.5rem;
          color: var(--text-muted);
          text-decoration: none;
          font-weight: 700;
          font-size: 0.8rem;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          gap: 6px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .back-to-home:hover {
          color: var(--color-accent);
          transform: translateX(-4px);
        }

        .auth-card {
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: 24px;
          padding: 3rem;
          width: 100%;
          max-width: 450px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          animation: fadeIn 0.5s ease-out;
        }

        .auth-header {
          text-align: center;
          margin-bottom: 2.5rem;
        }

        .auth-form {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .form-group label {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-secondary);
          margin-left: 4px;
        }

        .auth-input {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--glass-border);
          border-radius: 12px;
          padding: 0.8rem 1rem;
          color: var(--text-primary);
          font-size: 1rem;
          transition: all 0.2s ease;
        }

        .auth-input:focus {
          outline: none;
          border-color: var(--color-accent);
          background: rgba(255, 255, 255, 0.08);
          box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1);
        }

        .checkbox-group {
          flex-direction: row !important;
          align-items: flex-start !important;
          gap: 12px !important;
          margin-top: 0.5rem;
        }

        .checkbox-group input {
          width: 18px;
          height: 18px;
          margin-top: 3px;
          cursor: pointer;
        }

        .checkbox-group label {
          font-size: 0.8rem !important;
          font-weight: 500 !important;
          color: var(--text-secondary) !important;
          line-height: 1.4;
          cursor: pointer;
        }

        .checkbox-group label a {
          color: var(--color-accent);
          text-decoration: none;
          font-weight: 700;
        }

        .checkbox-group label a:hover {
          text-decoration: underline;
        }

        .auth-submit:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          filter: grayscale(1);
        }

        .auth-submit {
          background: linear-gradient(135deg, var(--color-accent), #f59e0b);
          color: white;
          border: none;
          border-radius: 12px;
          padding: 1rem;
          font-weight: 700;
          font-size: 1rem;
          cursor: pointer;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
          margin-top: 1rem;
        }

        .auth-submit:hover {
          transform: translateY(-2px);
          box-shadow: 0 10px 20px -5px rgba(245, 158, 11, 0.4);
        }

        .auth-error {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.2);
          color: #fca5a5;
          padding: 0.8rem;
          border-radius: 10px;
          font-size: 0.9rem;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .auth-footer {
          text-align: center;
          margin-top: 2rem;
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        .auth-link {
          color: var(--color-accent);
          font-weight: 600;
          text-decoration: none;
        }

        .auth-link:hover {
          text-decoration: underline;
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-darker)', color: 'var(--color-accent)' }}>Chargement en cours...</div>}>
      <RegisterContent />
    </Suspense>
  );
}
