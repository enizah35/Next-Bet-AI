import DashboardClient from "./DashboardClient";

// Revalidate data every 60 seconds so the server-side payload stays fresh
export const revalidate = 60;

export default async function DashboardPage() {
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();
  let initialMatches = [];

  try {
    const res = await fetch(`${apiUrl}/predictions/upcoming?fast=true`, {
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
