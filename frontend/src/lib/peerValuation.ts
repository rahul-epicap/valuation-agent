import { DashboardData, MetricType, ScatterPoint } from './types';
import { filterPoints } from './filters';
import { linearRegressionTrimmed } from './regression';

/**
 * Get available index keys with ticker counts from dashboard data.
 */
export function getAvailableIndices(data: DashboardData): { key: string; count: number }[] {
  if (!data.indices) return [];

  const counts: Record<string, number> = {};
  for (const tickerIndices of Object.values(data.indices)) {
    for (const idx of tickerIndices) {
      counts[idx] = (counts[idx] || 0) + 1;
    }
  }

  return Object.entries(counts)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => a.key.localeCompare(b.key));
}

/**
 * Get all tickers belonging to a specific index.
 */
export function getTickersForIndex(data: DashboardData, indexKey: string): string[] {
  if (!data.indices) return [];
  return data.tickers.filter((t) => data.indices![t]?.includes(indexKey));
}

interface IndexRegressionPrediction {
  indexKey: string;
  indexTickerCount: number;
  regression: { slope: number; intercept: number; r2: number; n: number } | null;
  impliedMultiple: number | null;
}

/**
 * For each peer index, run regression on full index membership and predict implied multiple.
 */
export function computePeerIndexRegressions(
  data: DashboardData,
  targetGrowthPct: number,
  peerTickers: string[],
  metric: MetricType,
  dateIdx: number,
): IndexRegressionPrediction[] {
  if (!data.indices) return [];

  // Determine which indices the peers belong to
  const indexPeers: Record<string, string[]> = {};
  for (const t of peerTickers) {
    const tIndices = data.indices[t];
    if (!tIndices) continue;
    for (const idx of tIndices) {
      (indexPeers[idx] = indexPeers[idx] || []).push(t);
    }
  }

  const results: IndexRegressionPrediction[] = [];
  for (const [indexKey] of Object.entries(indexPeers)) {
    const indexTickers = getTickersForIndex(data, indexKey);
    if (indexTickers.length < 10) continue;

    const pts = filterPoints(data, metric, dateIdx, indexTickers, null, null, null, null);
    const pairs = pts.map((p: ScatterPoint) => [p.x, p.y] as [number, number]);
    const reg = linearRegressionTrimmed(pairs);

    let implied: number | null = null;
    if (reg) {
      implied = reg.slope * targetGrowthPct + reg.intercept;
    }

    results.push({
      indexKey,
      indexTickerCount: indexTickers.length,
      regression: reg,
      impliedMultiple: implied,
    });
  }

  return results;
}

/**
 * R²-weighted average of implied multiples from index regressions.
 */
export function computeCompositeValuation(
  regressions: IndexRegressionPrediction[],
): number | null {
  const valid = regressions.filter(
    (r) => r.regression && r.impliedMultiple !== null && r.impliedMultiple > 0,
  );
  if (valid.length === 0) return null;

  let totalWeight = 0;
  let weightedSum = 0;
  for (const r of valid) {
    const w = r.regression!.r2;
    weightedSum += r.impliedMultiple! * w;
    totalWeight += w;
  }

  return totalWeight > 0 ? weightedSum / totalWeight : null;
}
