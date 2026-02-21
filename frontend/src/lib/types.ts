export interface DashboardData {
  dates: string[];
  tickers: string[];
  industries: Record<string, string>;
  indices?: Record<string, string[]>;
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

export type RegressionMethodName = 'ols' | 'trimmed' | 'cooks' | 'robust' | 'logLinear';

export interface ComparisonResult {
  method: RegressionMethodName;
  label: string;
  r2: number;
  n: number;
  nOriginal: number;
  slope: number;
  intercept: number;
  predict: (x: number) => number;
}

export interface AggregateMethodResult {
  method: RegressionMethodName;
  label: string;
  avgR2: number;
  medianR2: number;
  avgN: number;
  avgNOriginal: number;
  avgSlope: number;
  avgIntercept: number;
  periodCount: number;
  /** How many periods this method had the highest R² */
  winCount: number;
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

export interface IndexInfo {
  id: number;
  bbg_ticker: string;
  short_name: string;
  display_name: string;
  member_count: number;
  latest_as_of_date: string | null;
}

export interface PeerSearchResult {
  ticker: string;
  score: number;
  description: string;
}

export interface PeerSearchResponse {
  query_ticker: string | null;
  query_text: string | null;
  results: PeerSearchResult[];
}

export interface IndexRegressionResult {
  index_name: string;
  peer_count_in_index: number;
  total_index_tickers: number;
  avg_peer_similarity: number;
  regressions: {
    metric_type: MetricType;
    metric_label: string;
    regression: RegressionResult | null;
    implied_multiple: number | null;
    historical_implied_multiple: number | null;
    historical: {
      avg_slope: number;
      avg_intercept: number;
      avg_r2: number;
      avg_n: number;
      period_count: number;
    } | null;
  }[];
}

export interface CompositeValuation {
  metric_type: MetricType;
  metric_label: string;
  weighted_implied_multiple: number | null;
  actual_multiple: number | null;
  deviation_pct: number | null;
  num_indices: number;
}

export interface PeerValuationResult {
  ticker: string;
  industry: string | null;
  peer_count: number;
  similar_tickers: PeerSearchResult[];
  index_regressions: IndexRegressionResult[];
  composite_valuation: CompositeValuation[];
  historical_composite_valuation: CompositeValuation[];
  peer_stats: {
    metric_type: MetricType;
    metric_label: string;
    count: number;
    mean: number | null;
    median: number | null;
    p25: number | null;
    p75: number | null;
    min: number | null;
    max: number | null;
    ticker_percentile: number | null;
  }[];
  dcf: Record<string, unknown> | null;
  snapshot_id: number;
}
