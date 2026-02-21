import { DashboardData, MetricType, ScatterPoint, MULTIPLE_KEYS, GROWTH_KEYS } from './types';

export function getActiveTickers(
  data: DashboardData,
  excludedTickers: Set<string>,
  activeIndustries: Set<string>,
  activeIndices?: Set<string>,
  indexFilterMode?: 'off' | 'on',
): string[] {
  const hasIndustries = Object.keys(data.industries).length > 0;
  const indexFilterActive = indexFilterMode === 'on' && activeIndices && activeIndices.size > 0 && data.indices;
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

export function okEps(
  data: DashboardData,
  ticker: string,
  dateIndex: number
): boolean {
  const d = data.fm[ticker];
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
  const mk = MULTIPLE_KEYS[type];
  const gk = GROWTH_KEYS[type];
  const pts: ScatterPoint[] = [];

  for (const t of tickers) {
    const d = data.fm[t];
    if (!d) continue;
    const m = d[mk][dateIndex];
    const g = d[gk][dateIndex];
    if (m == null || g == null) continue;
    if (type === 'pEPS') {
      if (!okEps(data, t, dateIndex)) continue;
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
  const mk = MULTIPLE_KEYS[type];
  const vals: number[] = [];

  for (const t of tickers) {
    const d = data.fm[t];
    if (!d) continue;
    const m = d[mk][dateIndex];
    if (m == null) continue;
    if (type === 'pEPS') {
      if (!okEps(data, t, dateIndex)) continue;
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

export function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const i = (sorted.length - 1) * p;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}
