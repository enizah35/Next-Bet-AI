import { createBrowserClient } from "@supabase/ssr";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseKey);

export const createClient = () => {
  if (!supabaseUrl || !supabaseKey) {
    const emptyAuth = {
      getSession: async () => ({ data: { session: null }, error: null }),
      getUser: async () => ({ data: { user: null }, error: null }),
      onAuthStateChange: () => ({
        data: { subscription: { unsubscribe: () => {} } },
      }),
      signInWithOAuth: async () => ({
        data: null,
        error: { message: "Supabase is not configured" },
      }),
      signInWithPassword: async () => ({
        data: null,
        error: { message: "Supabase is not configured" },
      }),
      signUp: async () => ({
        data: null,
        error: { message: "Supabase is not configured" },
      }),
      signOut: async () => ({ error: null }),
    };

    const emptyQuery = {
      select: () => emptyQuery,
      eq: () => emptyQuery,
      single: async () => ({ data: null, error: null }),
      update: () => emptyQuery,
      delete: () => emptyQuery,
    };

    return {
      auth: emptyAuth,
      from: () => emptyQuery,
    } as unknown as ReturnType<typeof createBrowserClient>;
  }

  if (!browserClient) {
    browserClient = createBrowserClient(
      supabaseUrl,
      supabaseKey,
    );
  }

  return browserClient;
};
