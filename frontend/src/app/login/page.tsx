'use client'

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { login } from '../auth/actions';
import Logo from '@/components/Logo';

function LoginContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get('error');
  const message = searchParams.get('message');

  return (
    <div className="auth-container">
      <div className="auth-card">
        <Link href="/" className="back-to-home">← Retour</Link>
        <div className="auth-header">
          <Logo width={200} height={50} />
          <h1 style={{ marginTop: '1.5rem', fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Connexion
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.5rem' }}>
            Accédez aux prédictions neuronales avancées
          </p>
        </div>

        <form action={login} className="auth-form">
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
              placeholder="••••••••"
              required
              className="auth-input"
            />
          </div>

          {error && (
            <div className="auth-error">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          {message && (
            <div className="auth-message">
              {message}
            </div>
          )}

          <button type="submit" className="auth-submit">
            Se connecter
          </button>
        </form>

        <div className="auth-footer">
          Nouveau sur Next-Bet-AI ?{' '}
          <Link href="/register" className="auth-link">
            Créer un compte
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

        .auth-submit:active {
          transform: translateY(0);
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

        .auth-message {
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.2);
          color: #6ee7b7;
          padding: 0.8rem;
          border-radius: 10px;
          font-size: 0.9rem;
        }

        .auth-footer {
          text-align: center;
          margin-top: 2rem;
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        .auth-link {
          color: var(--color-accent);
          font-weight: 700;
          text-decoration: none;
          transition: filter 0.2s;
        }

        .auth-link:hover {
          filter: brightness(1.2);
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

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-darker)', color: 'var(--color-accent)' }}>Chargement en cours...</div>}>
      <LoginContent />
    </Suspense>
  );
}
