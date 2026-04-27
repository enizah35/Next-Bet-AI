import ResultsClient from "./ResultsClient";

export const revalidate = 60; // optionally cache results, or set to 0 for always dynamic

type ResultStats = { total: number; won: number; lost: number; pending: number; winRate: number };
type PredictionEntry = {
  id: number;
  homeTeam: string;
  awayTeam: string;
  league: string;
  matchDate: string | null;
  prediction: string;
  tipType: string;
  confidence: number;
  odds: number | null;
  actualResult: string | null;
  actualScore: string | null;
  isWon: boolean | null;
  createdAt: string | null;
  verifiedAt: string | null;
};
type BetBuilderEntry = {
  matchKey: string;
  homeTeam: string;
  awayTeam: string;
  league: string;
  matchDate: string | null;
  actualScore: string | null;
  selections: PredictionEntry[];
  combinedOdds: number;
  isWon: boolean | null;
};

export default async function ResultsPage() {
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();
  let initialStats: ResultStats = { total: 0, won: 0, lost: 0, pending: 0, winRate: 0 };
  let initialHistory: PredictionEntry[] = [];
  let initialBetBuilders: BetBuilderEntry[] = [];

  try {
    const res = await fetch(`${apiUrl}/predictions/results`, {
      signal: AbortSignal.timeout(8000),
    });
    if (res.ok) {
      const data = await res.json();
      initialStats = data.stats || initialStats;
      initialHistory = data.history || initialHistory;
      initialBetBuilders = data.betBuilders || initialBetBuilders;
    }
  } catch {
    initialStats = { total: 0, won: 0, lost: 0, pending: 0, winRate: 0 };
    initialHistory = [];
    initialBetBuilders = [];
  }

  return (
    <ResultsClient
      initialStats={initialStats}
      initialHistory={initialHistory}
      initialBetBuilders={initialBetBuilders}
    />
  );
}
