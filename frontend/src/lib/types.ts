export interface DashboardData {
  dates: string[];
  tickers: string[];
  industries: Record<string, string>;
  fm: Record<string, TickerMetrics>;
}

export interface TickerMetrics {
  er: (number | null)[];
  eg: (number | null)[];
  pe: (number | null)[];
  rg: (number | null)[];
  xg: (number | null)[];
  fe: (number | null)[];
}

export type MetricType = 'evRev' | 'evGP' | 'pEPS';

export interface RegressionResult {
  slope: number;
  intercept: number;
  r2: number;
  n: number;
}

export interface ScatterPoint {
  x: number;
  y: number;
  t: string;
}

export interface SnapshotMeta {
  id: number;
  name: string;
  created_at: string;
  source_filename: string | null;
  ticker_count: number | null;
  date_count: number | null;
  industry_count: number | null;
}

export const MULTIPLE_KEYS: Record<MetricType, keyof TickerMetrics> = {
  evRev: 'er',
  evGP: 'eg',
  pEPS: 'pe',
};

export const GROWTH_KEYS: Record<MetricType, keyof TickerMetrics> = {
  evRev: 'rg',
  evGP: 'rg',
  pEPS: 'xg',
};

export const COLORS: Record<MetricType, { m: string; b: string; l: string }> = {
  evRev: { m: '#3b82f6', b: 'rgba(59,130,246,.45)', l: '#60a5fa' },
  evGP:  { m: '#f59e0b', b: 'rgba(245,158,11,.45)', l: '#fbbf24' },
  pEPS:  { m: '#10b981', b: 'rgba(16,185,129,.45)', l: '#34d399' },
};

export const HIGHLIGHT_COLORS = [
  '#f59e0b', '#ec4899', '#06b6d4', '#a78bfa',
  '#fb923c', '#22d3ee', '#e879f9', '#facc15',
];

export const METRIC_LABELS: Record<MetricType, string> = {
  evRev: 'EV / Revenue',
  evGP: 'EV / Gross Profit',
  pEPS: 'Price / EPS',
};

export const METRIC_TITLES: Record<MetricType, string> = {
  evRev: 'EV / Fwd Revenue × Revenue Growth',
  evGP: 'EV / Fwd Gross Profit × Revenue Growth',
  pEPS: 'Price / Fwd Adj. EPS × EPS Growth',
};

export const Y_LABELS: Record<MetricType, string> = {
  evRev: 'EV / Fwd Revenue',
  evGP: 'EV / Fwd Gross Profit',
  pEPS: 'Price / Fwd Adj. EPS',
};

export const X_LABELS: Record<MetricType, string> = {
  evRev: 'Revenue Growth (%)',
  evGP: 'Revenue Growth (%)',
  pEPS: 'EPS Growth (%)',
};

export const Y_LABELS_TIME: Record<MetricType, string> = {
  evRev: 'EV / Fwd Revenue (x)',
  evGP: 'EV / Gross Profit (x)',
  pEPS: 'Price / Fwd EPS (x)',
};
