import TipsClient from "./TipsClient";

export const revalidate = 60;

export default async function TipsPage() {
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();
  let initialMatches = [];

  try {
    const res = await fetch(`${apiUrl}/predictions/upcoming?fast=true&limit=40`, {
      signal: AbortSignal.timeout(25000),
    });
    if (res.ok) {
      initialMatches = await res.json();
    }
  } catch {
    initialMatches = [];
  }

  return <TipsClient initialMatches={initialMatches} />;
}
