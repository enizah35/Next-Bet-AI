"use client";

import React, { useState } from 'react';
import Logo from '@/components/Logo';
import ThemeToggle from '@/components/ThemeToggle';
import UserNav from '@/components/UserNav';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { cancelSubscription, updateProfile, deleteUserAccount } from '@/app/auth/actions';

import { Icons } from '@/components/Icons';

export default function ProfilePage() {
  const { user, profile, loading, refreshProfile } = useAuth();
  const [cancelling, setCancelling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [fullName, setFullName] = useState(profile?.full_name || '');

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'var(--text-secondary)' }}>
        Chargement des informations du compte...
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column', gap: '20px' }}>
        <h2>Vous devez être connecté pour voir cette page.</h2>
        <Link href="/login" className="btn-primary" style={{ padding: '10px 20px', background: 'var(--color-accent)', color: 'white', borderRadius: '12px', textDecoration: 'none' }}>Se connecter</Link>
      </div>
    );
  }

  const isTrialActive = profile?.trial_started_at && 
    (new Date().getTime() - new Date(profile.trial_started_at).getTime()) < (7 * 24 * 60 * 60 * 1000);
  
  const getSubscriptionName = (tier: string | null) => {
    if (tier === 'ultimate') return "Ultimate AI Pass (L1 + PL)";
    if (tier === 'ligue1') return "Ligue 1 Origin";
    if (tier === 'pl') return "Premier League Elite";
    return "Aucun abonnement actif";
  };

  const handleCancelSub = async () => {
    if (!window.confirm("Êtes-vous sûr de vouloir résilier votre abonnement ? Vous perdrez l'accès aux analyses premium immédiatement.")) return;
    
    setCancelling(true);
    const res = await cancelSubscription();
    if (res.success) {
      await refreshProfile();
      alert("Abonnement résilié avec succès.");
    } else {
      alert("Erreur lors de la résiliation.");
    }
    setCancelling(false);
  };

  const calculateTrialDaysLeft = () => {
    if (!profile?.trial_started_at || !isTrialActive) return 0;
    const end = new Date(profile.trial_started_at).getTime() + (7 * 24 * 60 * 60 * 1000);
    const diff = end - new Date().getTime();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpdating(true);
    const res = await updateProfile({ full_name: fullName });
    if (res.success) {
      await refreshProfile();
      alert("Profil mis à jour !");
    } else {
      alert("Erreur de mise à jour.");
    }
    setUpdating(false);
  };

  const handleDeleteAccount = async () => {
    const confirm = window.confirm("ATTENTION : Cette action est irréversible. Toutes vos données seront supprimées définitivement. Souhaitez-vous continuer ?");
    if (!confirm) return;

    setDeleting(true);
    const res = await deleteUserAccount();
    if (!res.success) {
      alert("Erreur lors de la suppression.");
      setDeleting(false);
    }
  };

  return (
    <>
      <header className="header" style={{ background: "var(--header-bg)" }}>
        <div className="header-logo">
          <Logo width={220} height={55} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <Link href="/dashboard" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 }}>
            Retour au Dashboard
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ThemeToggle />
            <UserNav />
          </div>
        </div>
      </header>

      <main className="container profile-container">
        <h1 className="dashboard-title" style={{ marginBottom: '2rem' }}>Mon Compte</h1>

        <div className="profile-grid">
          {/* Informations Personnelles */}
          <div className="profile-card">
            <div className="card-header">
              <div className="icon-wrapper"><Icons.user size={24} /></div>
              <h2>Informations Personnelles</h2>
            </div>
            <div className="card-content">
              <form onSubmit={handleUpdateProfile} className="profile-form">
                <div className="form-group">
                  <label className="info-label">Email (Non modifiable)</label>
                  <input type="text" value={user.email} disabled className="profile-input disabled" />
                </div>
                <div className="form-group">
                  <label className="info-label">Nom Complet</label>
                  <input 
                    type="text" 
                    value={fullName} 
                    onChange={(e) => setFullName(e.target.value)} 
                    placeholder="Ex: Jean Dupont"
                    className="profile-input" 
                  />
                </div>
                <button type="submit" disabled={updating || fullName === profile?.full_name} className="update-btn">
                  {updating ? 'Enregistrement...' : 'Enregistrer les modifications'}
                </button>
              </form>
              
              <div className="info-row" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--glass-border)' }}>
                <span className="info-label">ID Utilisateur</span>
                <span className="info-val" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{user.id}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Membre depuis</span>
                <span className="info-val">{new Date(user.created_at).toLocaleDateString('fr-FR')}</span>
              </div>
            </div>
          </div>

          {/* Abonnement et Facturation */}
          <div className="profile-card">
            <div className="card-header">
              <div className="icon-wrapper"><Icons.creditCard size={24} /></div>
              <h2>Abonnement & Facturation</h2>
            </div>
            <div className="card-content">
              
              <div className="subscription-status">
                <h3 style={{ fontSize: '1.2rem', marginBottom: '8px', color: 'var(--text-primary)' }}>
                  {getSubscriptionName(profile?.subscription_tier)}
                </h3>
                
                {profile?.subscription_tier && profile.subscription_tier !== 'free' ? (
                  <>
                    <div className="status-badge active">
                      <Icons.checkCircle size={20} /> Abonnement Actif
                    </div>
                    <div style={{ marginTop: '10px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Cycle : <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{profile.billing_cycle === 'yearly' ? 'Annuel' : 'Mensuel'}</span>
                    </div>
                  </>
                ) : isTrialActive ? (
                  <div className="status-badge trial">
                    Essai gratuit en cours ({calculateTrialDaysLeft()} jours restants)
                  </div>
                ) : (
                  <div className="status-badge inactive">
                    Aucun abonnement
                  </div>
                )}
              </div>

              <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <Link href="/pricing" className="manage-btn">
                  {profile?.subscription_tier && profile.subscription_tier !== 'free' ? 'Modifier mon offre' : 'Découvrir les offres'}
                </Link>
                
                {profile?.subscription_tier && profile.subscription_tier !== 'free' && (
                  <button 
                    onClick={handleCancelSub}
                    disabled={cancelling}
                    className="cancel-btn"
                  >
                    {cancelling ? 'Résiliation...' : 'Résilier l\'abonnement'}
                  </button>
                )}

                <p style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  La résiliation prend effet immédiatement. Pour modifier votre moyen de paiement, contactez le support.
                </p>
              </div>

              <div className="danger-zone">
                 <h4 className="danger-title">Zone de Danger</h4>
                 <p className="danger-text">Supprimez définitivement votre compte et toutes ses données associées.</p>
                 <button onClick={handleDeleteAccount} disabled={deleting} className="delete-account-btn">
                   {deleting ? 'Suppression...' : 'Supprimer mon compte'}
                 </button>
              </div>

            </div>
          </div>
        </div>
      </main>

      <style>{`
        .profile-container {
          padding-top: 3rem;
          max-width: 900px;
        }

        .profile-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 2rem;
        }

        @media (min-width: 768px) {
          .profile-grid {
            grid-template-columns: 1fr 1fr;
          }
        }

        .profile-card {
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          border-radius: 20px;
          padding: 2rem;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
        }

        .card-header {
          display: flex;
          align-items: center;
          gap: 15px;
          margin-bottom: 2rem;
          padding-bottom: 1rem;
          border-bottom: 1px solid var(--glass-border);
        }

        .card-header h2 {
          font-size: 1.3rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .icon-wrapper {
          background: rgba(14, 165, 233, 0.1);
          color: var(--color-accent);
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .info-row {
          display: flex;
          flex-direction: column;
          gap: 5px;
          margin-bottom: 1.5rem;
        }

        .info-row:last-child {
          margin-bottom: 0;
        }

        .info-label {
          font-size: 0.85rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
        }

        .info-val {
          font-size: 1.05rem;
          color: var(--text-primary);
          font-weight: 500;
        }

        .subscription-status {
          background: rgba(255, 255, 255, 0.03);
          border-radius: 16px;
          padding: 1.5rem;
          border: 1px dashed var(--glass-border);
        }

        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 0.85rem;
          font-weight: 600;
        }

        .status-badge.active {
          background: rgba(16, 185, 129, 0.15);
          color: #34d399;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .status-badge.trial {
          background: rgba(245, 158, 11, 0.15);
          color: #fbbf24;
          border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .status-badge.inactive {
          background: rgba(100, 116, 139, 0.15);
          color: #94a3b8;
          border: 1px solid rgba(100, 116, 139, 0.3);
        }

        .profile-form {
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
        }

        .profile-input {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--glass-border);
          border-radius: 10px;
          padding: 0.8rem;
          color: var(--text-primary);
          font-family: inherit;
          font-size: 0.95rem;
          transition: all 0.2s;
        }

        .profile-input:focus {
          outline: none;
          border-color: var(--color-accent);
          background: rgba(255, 255, 255, 0.08);
        }

        .profile-input.disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .update-btn {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--glass-border);
          color: white;
          padding: 10px;
          border-radius: 10px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .update-btn:hover:not(:disabled) {
          background: var(--glass-hover);
          border-color: var(--color-accent);
        }

        .update-btn:disabled {
          opacity: 0.3;
          cursor: default;
        }

        .danger-zone {
          margin-top: 3rem;
          padding-top: 2rem;
          border-top: 1px solid rgba(239, 68, 68, 0.2);
          text-align: center;
        }

        .danger-title {
          color: #ef4444;
          font-size: 0.9rem;
          font-weight: 800;
          text-transform: uppercase;
          margin-bottom: 0.5rem;
        }

        .danger-text {
          font-size: 0.85rem;
          color: var(--text-muted);
          margin-bottom: 1.5rem;
        }

        .delete-account-btn {
          background: transparent;
          border: 1px solid rgba(239, 68, 68, 0.3);
          color: #ef4444;
          padding: 10px 20px;
          border-radius: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .delete-account-btn:hover:not(:disabled) {
          background: rgba(239, 68, 68, 0.1);
          border-color: #ef4444;
        }

        .delete-account-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .manage-btn {
          display: inline-block;
          width: 100%;
          text-align: center;
          background: var(--color-accent);
          color: white;
          padding: 12px 20px;
          border-radius: 12px;
          font-weight: 700;
          text-decoration: none;
          transition: all 0.2s;
        }

        .manage-btn:hover {
          background: #0284c7;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
        }

        .cancel-btn {
          width: 100%;
          background: transparent;
          border: 1px solid var(--glass-border);
          color: var(--color-danger);
          padding: 10px 20px;
          border-radius: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          font-family: inherit;
        }

        .cancel-btn:hover:not(:disabled) {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.4);
        }

        .cancel-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </>
  );
}
