import { createBrowserClient } from "@supabase/ssr";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseKey);

export const createClient = () => {
  if (!supabaseUrl || !supabaseKey) {
    throw new Error("Supabase is not configured");
  }

  return createBrowserClient(
    supabaseUrl,
    supabaseKey,
  );
};
