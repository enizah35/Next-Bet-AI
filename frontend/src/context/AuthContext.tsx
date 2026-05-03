'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { createClient, isSupabaseConfigured } from '@/utils/supabase/client';
import { AuthChangeEvent, Session, User } from '@supabase/supabase-js';

type UserProfile = {
  id: string;
  full_name?: string | null;
  subscription_tier?: string | null;
  billing_cycle?: string | null;
  is_trial_used?: boolean | null;
  updated_at?: string | null;
};

interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  profile: null,
  loading: true,
  refreshProfile: async () => {},
});

const isSupabaseLockAbort = (err: unknown) => {
  if (!err || typeof err !== 'object') return false;
  const candidate = err as { name?: string; message?: string };
  return candidate.name === 'AbortError' && (candidate.message ?? '').includes('Lock broken');
};

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async (userId: string) => {
    if (!isSupabaseConfigured) return;

    try {
      const supabase = createClient();
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();
      
      if (!error) {
        setProfile(data);
      }
    } catch (err) {
      if (isSupabaseLockAbort(err)) return;
      console.error("AuthContext: Error fetching profile:", err);
    }
  }, []);

  const refreshProfile = async () => {
    if (user) {
      await fetchProfile(user.id);
    }
  };

  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (isSupabaseLockAbort(event.reason)) {
        event.preventDefault();
      }
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    if (!isSupabaseConfigured) {
      setUser(null);
      setProfile(null);
      setLoading(false);
      return () => {
        window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      };
    }

    const supabase = createClient();

    const initAuth = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (error) throw error;
        
        const currentUser = session?.user ?? null;
        setUser(currentUser);
        
        if (currentUser) {
          await fetchProfile(currentUser.id);
        }
      } catch (err) {
        if (isSupabaseLockAbort(err)) return;
        console.error("AuthContext: Init error:", err);
      } finally {
        setLoading(false);
      }
    };

    initAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event: AuthChangeEvent, session: Session | null) => {
      void event;
      const currentUser = session?.user ?? null;
      setUser(currentUser);
      
      if (currentUser) {
        await fetchProfile(currentUser.id);
      } else {
        setProfile(null);
      }
      
      setLoading(false);
    });

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      subscription.unsubscribe();
    };
  }, [fetchProfile]);

  return (
    <AuthContext.Provider value={{ user, profile, loading, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
