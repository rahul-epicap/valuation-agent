import { DashboardData, MetricType, MULTIPLE_KEYS, GROWTH_KEYS } from './types';
import { filterPoints, okEps, percentile } from './filters';
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

export interface SingleTickerScore {
  growth: number;
  actual: number;
  predicted: number;
  pctDiff: number;
}

export function computeSingleTickerScore(
  data: DashboardData,
  ticker: string,
  type: MetricType,
  dateIndex: number,
  baseline: HistoricalBaseline
): SingleTickerScore | null {
  const mk = MULTIPLE_KEYS[type];
  const gk = GROWTH_KEYS[type];
  const d = data.fm[ticker];
  if (!d) return null;

  const m = d[mk][dateIndex];
  const g = d[gk][dateIndex];
  if (m == null || g == null) return null;

  // Apply same outlier caps as filterPoints
  if (type === 'pEPS') {
    if (!okEps(data, ticker, dateIndex)) return null;
    if (m > 200) return null;
  }
  if (type === 'evRev' && m > 80) return null;
  if (type === 'evGP' && m > 120) return null;

  const gPct = g * 100;
  const predicted = baseline.avgSlope * gPct + baseline.avgIntercept;
  if (predicted <= 0) return null;
  const pctDiff = ((m - predicted) / predicted) * 100;

  return { growth: gPct, actual: m, predicted, pctDiff };
}

export interface DeviationPoint {
  date: string;
  pctDiff: number | null;
}

export function computeDeviationTimeSeries(
  data: DashboardData,
  ticker: string,
  type: MetricType,
  activeTickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null,
  excludeYear?: number
): DeviationPoint[] {
  const mk = MULTIPLE_KEYS[type];
  const gk = GROWTH_KEYS[type];
  const result: DeviationPoint[] = [];

  for (let di = 0; di < data.dates.length; di++) {
    if (excludeYear != null) {
      const year = parseInt(data.dates[di].slice(0, 4), 10);
      if (year === excludeYear) {
        result.push({ date: data.dates[di], pctDiff: null });
        continue;
      }
    }

    // Run regression on all active tickers at this date
    const pts = filterPoints(
      data, type, di, activeTickers,
      revGrMin, revGrMax, epsGrMin, epsGrMax
    );
    const reg = linearRegression(pts.map((p) => [p.x, p.y]));
    if (!reg) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }

    // Get the selected ticker's values at this date
    const d = data.fm[ticker];
    if (!d) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }
    const m = d[mk][di];
    const g = d[gk][di];
    if (m == null || g == null) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }

    // Apply outlier caps
    if (type === 'pEPS' && (!okEps(data, ticker, di) || m > 200)) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }
    if (type === 'evRev' && m > 80) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }
    if (type === 'evGP' && m > 120) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }

    const gPct = g * 100;
    const predicted = reg.slope * gPct + reg.intercept;
    if (predicted <= 0) {
      result.push({ date: data.dates[di], pctDiff: null });
      continue;
    }

    const pctDiff = ((m - predicted) / predicted) * 100;
    result.push({ date: data.dates[di], pctDiff });
  }

  return result;
}

export interface SpotScore {
  growth: number;
  actual: number;
  predicted: number;
  pctDiff: number;
  slope: number;
  intercept: number;
  r2: number;
  n: number;
}

export function computeSpotScore(
  data: DashboardData,
  ticker: string,
  type: MetricType,
  dateIndex: number,
  activeTickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null
): SpotScore | null {
  const mk = MULTIPLE_KEYS[type];
  const gk = GROWTH_KEYS[type];
  const d = data.fm[ticker];
  if (!d) return null;

  const m = d[mk][dateIndex];
  const g = d[gk][dateIndex];
  if (m == null || g == null) return null;

  // Apply outlier caps
  if (type === 'pEPS') {
    if (!okEps(data, ticker, dateIndex)) return null;
    if (m > 200) return null;
  }
  if (type === 'evRev' && m > 80) return null;
  if (type === 'evGP' && m > 120) return null;

  const pts = filterPoints(
    data, type, dateIndex, activeTickers,
    revGrMin, revGrMax, epsGrMin, epsGrMax
  );
  const reg = linearRegression(pts.map((p) => [p.x, p.y]));
  if (!reg) return null;

  const gPct = g * 100;
  const predicted = reg.slope * gPct + reg.intercept;
  if (predicted <= 0) return null;

  const pctDiff = ((m - predicted) / predicted) * 100;

  return {
    growth: gPct,
    actual: m,
    predicted,
    pctDiff,
    slope: reg.slope,
    intercept: reg.intercept,
    r2: reg.r2,
    n: reg.n,
  };
}

export interface PercentileResult {
  currentDeviation: number;
  percentile: number;
  median: number;
  p10: number;
  p90: number;
  sampleCount: number;
}

export function computePercentileRank(
  deviationSeries: DeviationPoint[],
  currentDateIndex: number
): PercentileResult | null {
  const currentPoint = deviationSeries[currentDateIndex];
  if (!currentPoint || currentPoint.pctDiff == null) return null;

  const values = deviationSeries
    .map((p) => p.pctDiff)
    .filter((v): v is number => v != null);

  if (values.length < 3) return null;

  const sorted = [...values].sort((a, b) => a - b);
  const currentDev = currentPoint.pctDiff;

  // Percentile rank: fraction of values <= current
  const belowOrEqual = sorted.filter((v) => v <= currentDev).length;
  const pctRank = (belowOrEqual / sorted.length) * 100;

  return {
    currentDeviation: currentDev,
    percentile: pctRank,
    median: percentile(sorted, 0.5),
    p10: percentile(sorted, 0.1),
    p90: percentile(sorted, 0.9),
    sampleCount: sorted.length,
  };
}

