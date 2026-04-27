import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "Next Bet AI — Prédictions football calibrées par l'IA",
  description:
    "10 666 matchs d'entraînement. 14 features sélectionnées. Un modèle qui bat la baseline marché sur 5 ligues européennes.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="fr"
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{
              var m=localStorage.getItem('nba_mode')||'dark';
              var d=localStorage.getItem('nba_dir')||'safe';
              document.documentElement.setAttribute('data-mode',m);
              document.documentElement.setAttribute('data-dir',d);
            }catch(e){}})();`,
          }}
        />
      </head>
      <body>
        <AuthProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
