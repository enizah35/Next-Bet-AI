'use client';

import React from 'react';
import Link from 'next/link';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';

export default function ContentHeader() {
  return (
    <header className="header" style={{ background: "var(--header-bg)" }}>
      <div className="header-logo">
        <Logo width={220} height={55} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
        <Link href="/" className="nav-link" style={{ fontSize: '0.9rem', fontWeight: 600 }}>Retour à l'accueil</Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <ThemeToggle />
          <UserNav />
        </div>
      </div>
    </header>
  );
}
