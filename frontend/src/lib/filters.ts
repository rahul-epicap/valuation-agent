import { DashboardData, MetricType, ScatterPoint, MULTIPLE_KEYS, GROWTH_KEYS } from './types';

export function getActiveTickers(
  data: DashboardData,
  excludedTickers: Set<string>,
  activeIndustries: Set<string>
): string[] {
  const hasIndustries = Object.keys(data.industries).length > 0;
  return data.tickers.filter(
    (t) =>
      !excludedTickers.has(t) &&
      (!hasIndustries || activeIndustries.has(data.industries[t]))
  );
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
  if (xg == null || xg <= 0.02) return false;
  return true;
}

export function filterPoints(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  tickers: string[],
  grMin: number | null,
  grMax: number | null
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
    const gPct = (g as number) * 100;
    if (grMin != null && gPct < grMin) continue;
    if (grMax != null && gPct > grMax) continue;
    pts.push({ x: gPct, y: m as number, t });
  }
  return pts;
}

export function filterMultiples(
  data: DashboardData,
  type: MetricType,
  dateIndex: number,
  tickers: string[],
  grMin: number | null,
  grMax: number | null
): number[] {
  const mk = MULTIPLE_KEYS[type];
  const gk = GROWTH_KEYS[type];
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
    const g = d[gk][dateIndex];
    if (g != null) {
      const gPct = (g as number) * 100;
      if (grMin != null && gPct < grMin) continue;
      if (grMax != null && gPct > grMax) continue;
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
