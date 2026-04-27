"use client";
import { useState, Suspense } from "react";
import { createClient } from "@/utils/supabase/client";
import { useSearchParams } from "next/navigation";
import { BrandMark } from "@/components/BrandLockup";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { login, signup } from "@/app/auth/actions";

function Field({ label, type = "text", placeholder, name }: { label: string; type?: string; placeholder?: string; name: string }) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-soft)" }}>{label}</span>
      <input
        name={name} type={type} placeholder={placeholder} required
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{
          padding: "11px 14px", fontSize: 14,
          background: "var(--bg-inset)",
          border: "1px solid",
          borderColor: focus ? "var(--text)" : "var(--border)",
          borderRadius: 10, color: "var(--text)",
          outline: "none", transition: "border-color 0.15s",
        }}
      />
    </label>
  );
}

function AuthForm() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") === "register" ? "signup" : "login";
  const [tab, setTab] = useState<"login" | "signup">(initialTab as "login" | "signup");

  const errorMsg = searchParams.get("error");
  const message = searchParams.get("message");
  const [loadingGoogle, setLoadingGoogle] = useState(false);

  const handleGoogleLogin = async () => {
    try {
      setLoadingGoogle(true);
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) throw error;
    } catch (error: unknown) {
      console.error("Google Auth error:", error);
      setLoadingGoogle(false);
      const message = error instanceof Error ? error.message : "Erreur de connexion Google";
      window.location.href = `/login?error=${encodeURIComponent(message)}`;
    }
  };

  const [loadingGuest, setLoadingGuest] = useState(false);
  const handleGuestLogin = () => {
    setLoadingGuest(true);
    // On redirige simplement vers le dashboard, le middleware ne bloque plus
    window.location.href = "/dashboard";
  };

  return (
    <div style={{ background: "var(--bg)", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 24px" }}>
      <div style={{ width: "100%", maxWidth: 440 }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ display: "inline-flex", marginBottom: 20 }}>
            <BrandMark size={40} />
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 6 }}>
            {tab === "login" ? "Content de te revoir." : "Crée ton compte."}
          </h1>
          <p style={{ fontSize: 14, color: "var(--text-soft)" }}>
            {tab === "login" ? "Connecte-toi à ton tableau de bord." : "7 jours d'essai gratuits, sans carte bancaire."}
          </p>
        </div>

        {message && (
          <div style={{ padding: "12px 16px", borderRadius: 10, background: "var(--good-tint)", border: "1px solid var(--good)", color: "var(--good)", fontSize: 13, marginBottom: 16 }}>
            {message}
          </div>
        )}
        {errorMsg && (
          <div style={{ padding: "12px 16px", borderRadius: 10, background: "var(--bad-tint)", color: "var(--bad)", fontSize: 13, marginBottom: 16 }}>
            {decodeURIComponent(errorMsg)}
          </div>
        )}

        <Card pad={28}>
          <div style={{ marginBottom: 20 }}>
            <Segmented
              value={tab}
              onChange={(v) => setTab(v as "login" | "signup")}
              options={[{ value: "login", label: "Connexion" }, { value: "signup", label: "Inscription" }]}
            />
          </div>

          {/* Login form */}
          {tab === "login" && (
            <form action={login} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <Field label="E-mail" name="email" type="email" placeholder="toi@exemple.com" />
              <Field label="Mot de passe" name="password" type="password" placeholder="••••••••" />
              <div style={{ fontSize: 12, textAlign: "right" }}>
                <span style={{ color: "var(--text-soft)", textDecoration: "underline", textUnderlineOffset: 3, cursor: "pointer" }}>
                  Mot de passe oublié ?
                </span>
              </div>
              <Button variant="primary" size="lg" style={{ width: "100%", marginTop: 6 }}>
                Se connecter
              </Button>
            </form>
          )}

          {/* Signup form */}
          {tab === "signup" && (
            <form action={signup} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <Field label="Nom complet" name="name" placeholder="Jean Dupont" />
              <Field label="E-mail" name="email" type="email" placeholder="toi@exemple.com" />
              <Field label="Mot de passe" name="password" type="password" placeholder="••••••••" />
              <Button variant="primary" size="lg" style={{ width: "100%", marginTop: 6 }}>
                Créer mon compte
              </Button>
            </form>
          )}

          <div style={{ margin: "20px 0 16px", display: "flex", alignItems: "center", gap: 10, color: "var(--text-muted)", fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            ou
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          </div>

          <Button 
            variant="secondary" 
            size="lg" 
            style={{ width: "100%" }} 
            type="button" 
            onClick={handleGoogleLogin} 
            disabled={loadingGoogle || loadingGuest}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {loadingGoogle ? <span className="spinner" /> : null}
              {loadingGoogle ? "Redirection..." : "Continuer avec Google"}
            </div>
          </Button>

          <div style={{ marginTop: 12 }}>
            <Button 
              variant="ghost" 
              size="md" 
              style={{ width: "100%", border: "1px dashed var(--border-strong)" }} 
              type="button" 
              onClick={handleGuestLogin}
              disabled={loadingGoogle || loadingGuest}
            >
              {loadingGuest ? "Chargement..." : "Explorer sans compte (Mode Démo)"}
            </Button>
          </div>
        </Card>

        <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", marginTop: 20, lineHeight: 1.6 }}>
          En continuant tu acceptes nos{" "}
          <span style={{ textDecoration: "underline", textUnderlineOffset: 3, cursor: "pointer" }}>conditions</span>{" "}
          et notre{" "}
          <span style={{ textDecoration: "underline", textUnderlineOffset: 3, cursor: "pointer" }}>politique de confidentialité</span>.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <AuthForm />
    </Suspense>
  );
}
