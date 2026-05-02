import type { CapacitorConfig } from "@capacitor/cli";

const appUrl = process.env.NEXT_PUBLIC_APP_URL;

const config: CapacitorConfig = {
  appId: "com.nextbetai.app",
  appName: "Next Bet AI",
  webDir: "out",
  server: appUrl
    ? {
        url: appUrl,
        cleartext: appUrl.startsWith("http://"),
      }
    : undefined,
};

export default config;
