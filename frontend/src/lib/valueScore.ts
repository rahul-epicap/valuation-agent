import { DashboardData, MetricType } from './types';
import { filterPoints, getActiveTickers } from './filters';
import { linearRegression } from './regression';

export interface HistoricalBaseline {
  avgSlope: number;
  avgIntercept: number;
  periodCount: number;
  avgR2: number;
  avgN: number;
}

export interface ValueScoreEntry {
  ticker: string;
  industry: string;
  growth: number;
  actual: number;
  predicted: number;
  pctDiff: number;
}

export function computeHistoricalBaseline(
  data: DashboardData,
  type: MetricType,
  activeTickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null,
  excludeYear?: number
): HistoricalBaseline | null {
  let totalSlope = 0;
  let totalIntercept = 0;
  let totalR2 = 0;
  let totalN = 0;
  let periodCount = 0;

  for (let di = 0; di < data.dates.length; di++) {
    if (excludeYear != null) {
      const year = parseInt(data.dates[di].slice(0, 4), 10);
      if (year === excludeYear) continue;
    }

    const pts = filterPoints(
      data, type, di, activeTickers,
      revGrMin, revGrMax, epsGrMin, epsGrMax
    );
    const reg = linearRegression(pts.map((p) => [p.x, p.y]));
    if (!reg) continue;

    totalSlope += reg.slope;
    totalIntercept += reg.intercept;
    totalR2 += reg.r2;
    totalN += reg.n;
    periodCount++;
  }

  if (periodCount < 1) return null;

  return {
    avgSlope: totalSlope / periodCount,
    avgIntercept: totalIntercept / periodCount,
    periodCount,
    avgR2: totalR2 / periodCount,
    avgN: totalN / periodCount,
  };
}

export function computeValueScores(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  activeTickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null,
  baseline: HistoricalBaseline
): ValueScoreEntry[] {
  const pts = filterPoints(
    data, type, dateIndex, activeTickers,
    revGrMin, revGrMax, epsGrMin, epsGrMax
  );

  const entries: ValueScoreEntry[] = [];
  for (const p of pts) {
    const predicted = baseline.avgSlope * p.x + baseline.avgIntercept;
    if (predicted <= 0) continue;
    const pctDiff = ((p.y - predicted) / predicted) * 100;

    entries.push({
      ticker: p.t,
      industry: data.industries[p.t] || '',
      growth: p.x,
      actual: p.y,
      predicted,
      pctDiff,
    });
  }

  entries.sort((a, b) => a.pctDiff - b.pctDiff);
  return entries;
}

/** Helper to get active tickers from state params */
export function getActiveTickersFromState(
  data: DashboardData,
  exTk: Set<string>,
  indOn: Set<string>
): string[] {
  return getActiveTickers(data, exTk, indOn);
}
