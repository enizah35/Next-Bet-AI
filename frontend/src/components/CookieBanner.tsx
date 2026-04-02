'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

export default function CookieBanner() {
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem('cookie-consent');
    if (!consent) {
      setShowBanner(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookie-consent', 'accepted');
    setShowBanner(false);
  };

  if (!showBanner) return null;

  return (
    <div className="cookie-banner">
      <div className="cookie-content">
        <p>
          Next-Bet-AI utilise des cookies pour améliorer votre expérience et sécuriser votre session. 
          En continuant, vous acceptez notre <Link href="/legal/privacy">Politique de Confidentialité</Link>.
        </p>
        <button onClick={handleAccept} className="cookie-btn">Accepter</button>
      </div>

      <style jsx>{`
        .cookie-banner {
          position: fixed;
          bottom: 2rem;
          left: 50%;
          transform: translateX(-50%);
          width: 90%;
          max-width: 600px;
          background: rgba(10, 17, 40, 0.95);
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: 16px;
          padding: 1.2rem 2rem;
          z-index: 9999;
          box-shadow: 0 20px 40px rgba(0,0,0,0.5);
          animation: slideUp 0.5s ease-out;
        }

        .cookie-content {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 2rem;
        }

        .cookie-content p {
          font-size: 0.9rem;
          color: var(--text-secondary);
          line-height: 1.5;
          margin: 0;
        }

        .cookie-content a {
          color: var(--color-accent);
          text-decoration: underline;
        }

        .cookie-btn {
          background: var(--color-accent);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 8px;
          font-weight: 700;
          font-size: 0.85rem;
          cursor: pointer;
          white-space: nowrap;
          transition: transform 0.2s;
        }

        .cookie-btn:hover {
          transform: scale(1.05);
        }

        @keyframes slideUp {
          from { transform: translate(-50%, 100%); opacity: 0; }
          to { transform: translate(-50%, 0); opacity: 1; }
        }

        @media (max-width: 640px) {
          .cookie-content { flex-direction: column; text-align: center; gap: 1rem; }
        }
      `}</style>
    </div>
  );
}
