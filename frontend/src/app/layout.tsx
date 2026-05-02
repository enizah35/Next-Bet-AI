import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { AuthProvider } from "@/context/AuthContext";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";

export const metadata: Metadata = {
  applicationName: "Next Bet AI",
  title: "Next Bet AI - Predictions football calibrees par l'IA",
  description:
    "10 666 matchs d'entrainement. 14 features selectionnees. Un modele qui bat la baseline marche sur 5 ligues europeennes.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Next Bet AI",
    statusBarStyle: "black-translucent",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/icons/icon-180.png", sizes: "180x180", type: "image/png" },
    ],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0e0e10",
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
        <ServiceWorkerRegistration />
        <AuthProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
