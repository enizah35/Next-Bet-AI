import StatsClient from "./StatsClient";
import { getServerApiUrl } from "@/utils/api";

export const revalidate = 60;

export default async function StatsPage() {
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

  return <StatsClient initialMatches={initialMatches} />;
}
