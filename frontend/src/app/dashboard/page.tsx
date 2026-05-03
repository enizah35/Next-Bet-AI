import DashboardClient from "./DashboardClient";
import { getServerApiUrl } from "@/utils/api";

// Revalidate data every 60 seconds so the server-side payload stays fresh
export const revalidate = 60;

export default async function DashboardPage() {
  const apiUrl = getServerApiUrl();
  let initialMatches = [];

  try {
    const res = await fetch(`${apiUrl}/predictions/upcoming/full-cached?limit=300`, {
      signal: AbortSignal.timeout(25000),
    });
    if (res.ok) {
      initialMatches = await res.json();
    }
  } catch {
    initialMatches = [];
  }

  return <DashboardClient initialMatches={initialMatches} />;
}
