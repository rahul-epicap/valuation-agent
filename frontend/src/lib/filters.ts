import { DashboardData, MetricType, MetricArrayKey, ScatterPoint, MultiFactorScatterPoint, TickerMetrics, MULTIPLE_KEYS, GROWTH_KEYS } from './types';

export function getActiveTickers(
  data: DashboardData,
  excludedTickers: Set<string>,
  activeIndustries: Set<string>,
  activeIndices?: Set<string>,
): string[] {
  const hasIndustries = Object.keys(data.industries).length > 0;
  const indexFilterActive = activeIndices && activeIndices.size > 0 && data.indices;
  return data.tickers.filter((t) => {
    if (excludedTickers.has(t)) return false;
    if (hasIndustries && !activeIndustries.has(data.industries[t])) return false;
    if (indexFilterActive) {
      const tickerIndices = data.indices![t];
      if (!tickerIndices || !tickerIndices.some((idx) => activeIndices!.has(idx))) return false;
    }
    return true;
  });
}

/**
 * Resolve the effective multiple and growth keys for a ticker.
 *
 * For pEPS, if the ticker's epsMarketType is 'GAAP', use the GAAP keys
 * so the scatter chart plots each ticker on its native EPS basis.
 * For pEPS_GAAP, always use GAAP keys regardless of epsMarketType.
 */
export function resolveEpsKeys(
  type: MetricType,
  d: TickerMetrics,
): { mk: MetricArrayKey; gk: MetricArrayKey } {
  if (type === 'pEPS' && d.epsMarketType === 'GAAP') {
    return { mk: 'pe_gaap', gk: 'xg_gaap' };
  }
  return { mk: MULTIPLE_KEYS[type], gk: GROWTH_KEYS[type] };
}

export function okEps(
  data: DashboardData,
  ticker: string,
  dateIndex: number,
  type: MetricType = 'pEPS'
): boolean {
  const d = data.fm[ticker];
  const useGaap = type === 'pEPS_GAAP' || (type === 'pEPS' && d.epsMarketType === 'GAAP');
  if (useGaap) {
    const fe = d.fe_gaap?.[dateIndex];
    const xg = d.xg_gaap?.[dateIndex];
    if (fe == null || fe <= 0.5) return false;
    if (xg == null || xg <= -0.75 || xg > 2.0) return false;
    return true;
  }
  const fe = d.fe[dateIndex];
  const xg = d.xg[dateIndex];
  if (fe == null || fe <= 0.5) return false;
  if (xg == null || xg <= -0.75 || xg > 2.0) return false;
  return true;
}

export function filterPoints(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  tickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null
): ScatterPoint[] {
  const isEps = type === 'pEPS' || type === 'pEPS_GAAP';
  const pts: ScatterPoint[] = [];

  for (const t of tickers) {
    const d = data.fm[t];
    if (!d) continue;
    // Resolve keys — for pEPS, per-ticker based on epsMarketType
    const { mk, gk } = isEps ? resolveEpsKeys(type, d) : { mk: MULTIPLE_KEYS[type], gk: GROWTH_KEYS[type] };
    const mArr = d[mk];
    const gArr = d[gk];
    if (!mArr || !gArr) continue;
    const m = mArr[dateIndex];
    const g = gArr[dateIndex];
    if (m == null || g == null) continue;
    if (isEps) {
      if (!okEps(data, t, dateIndex, type)) continue;
      if (m > 200) continue;
    }
    if (type === 'evRev' && m > 80) continue;
    if (type === 'evGP' && m > 120) continue;
    // Revenue growth filter (always applied)
    const rg = d.rg[dateIndex];
    if (rg != null) {
      const rgPct = (rg as number) * 100;
      if (revGrMin != null && rgPct < revGrMin) continue;
      if (revGrMax != null && rgPct > revGrMax) continue;
    }
    // EPS growth filter (always applied)
    const xg = d.xg[dateIndex];
    if (xg != null) {
      const xgPct = (xg as number) * 100;
      if (epsGrMin != null && xgPct < epsGrMin) continue;
      if (epsGrMax != null && xgPct > epsGrMax) continue;
    }
    const gPct = (g as number) * 100;
    pts.push({ x: gPct, y: m as number, t });
  }
  return pts;
}

export function filterMultiples(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  tickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null
): number[] {
  const isEps = type === 'pEPS' || type === 'pEPS_GAAP';
  const vals: number[] = [];

  for (const t of tickers) {
    const d = data.fm[t];
    if (!d) continue;
    const { mk } = isEps ? resolveEpsKeys(type, d) : { mk: MULTIPLE_KEYS[type] };
    const mArr = d[mk];
    if (!mArr) continue;
    const m = mArr[dateIndex];
    if (m == null) continue;
    if (isEps) {
      if (!okEps(data, t, dateIndex, type)) continue;
      if (m > 200) continue;
    }
    if (type === 'evRev' && (m > 80 || m < 0)) continue;
    if (type === 'evGP' && (m > 120 || m < 0)) continue;
    // Revenue growth filter (always applied)
    const rg = d.rg[dateIndex];
    if (rg != null) {
      const rgPct = (rg as number) * 100;
      if (revGrMin != null && rgPct < revGrMin) continue;
      if (revGrMax != null && rgPct > revGrMax) continue;
    }
    // EPS growth filter (always applied)
    const xg = d.xg[dateIndex];
    if (xg != null) {
      const xgPct = (xg as number) * 100;
      if (epsGrMin != null && xgPct < epsGrMin) continue;
      if (epsGrMax != null && xgPct > epsGrMax) continue;
    }
    vals.push(m as number);
  }
  return vals;
}

/**
 * Enriches filterPoints output with per-ticker factor dummy values.
 * Reuses all existing filter logic, then attaches factorValues for each point.
 */
export function filterPointsMultiFactor(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  tickers: string[],
  revGrMin: number | null,
  revGrMax: number | null,
  epsGrMin: number | null,
  epsGrMax: number | null,
  regressionFactors: string[],
): MultiFactorScatterPoint[] {
  const basePts = filterPoints(data, type, dateIndex, tickers, revGrMin, revGrMax, epsGrMin, epsGrMax);
  if (!data.indices || regressionFactors.length === 0) {
    return basePts;
  }

  return basePts.map((pt) => {
    const tickerIndices = data.indices![pt.t] || [];
    const tickerIndexSet = new Set(tickerIndices);
    const factorValues: Record<string, number> = {};
    for (const factor of regressionFactors) {
      factorValues[factor] = tickerIndexSet.has(factor) ? 1 : 0;
    }
    return { ...pt, factorValues };
  });
}

export function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const i = (sorted.length - 1) * p;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}
