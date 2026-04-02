"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { logout } from '@/app/auth/actions';

export default function UserNav() {
  const { user, loading } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  if (loading) return <div className="login-btn" style={{ opacity: 0.3, cursor: 'wait' }}>Chargement...</div>;

  if (!user || !user.email) {
    return (
      <Link href="/login" className="login-btn">
        Se connecter
      </Link>
    );
  }

  return (
    <div className="user-nav-container">
      <button 
        className="user-profile-trigger"
        onClick={() => setDropdownOpen(!dropdownOpen)}
      >
        <div className="avatar">
          {user.email?.[0].toUpperCase()}
        </div>
        <span className="user-email-at">{user.email?.split('@')[0]}</span>
      </button>

      {dropdownOpen && (
        <div className="user-dropdown">
          <div className="dropdown-info">
            <div className="val">{user.email}</div>
          </div>
          <Link href="/dashboard" className="dropdown-item">
            📊 Dashboard
          </Link>
          <Link href="/profile" className="dropdown-item">
            ⚙️ Mon Profil
          </Link>
          <button 
            onClick={() => logout()}
            className="logout-action"
          >
            Déconnexion
          </button>
        </div>
      )}

    </div>
  );
}
