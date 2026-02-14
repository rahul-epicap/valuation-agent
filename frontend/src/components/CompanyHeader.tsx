'use client';

import { DashboardData } from '../lib/types';

interface CompanyHeaderProps {
  data: DashboardData;
  ticker: string;
  dateIndex: number;
}

export default function CompanyHeader({ data, ticker, dateIndex }: CompanyHeaderProps) {
  const industry = data.industries[ticker] || 'Unknown';
  const d = data.fm[ticker];

  const dateLabel = data.dates[dateIndex]
    ? new Date(data.dates[dateIndex] + 'T00:00:00').toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
      })
    : '';

  const rg = d?.rg[dateIndex];
  const xg = d?.xg[dateIndex];
  const fe = d?.fe[dateIndex];

  const fmt = (v: number | null, suffix: string, multiplier = 100) =>
    v != null ? `${(v * multiplier).toFixed(1)}${suffix}` : '\u2014';

  const fmtDollar = (v: number | null) =>
    v != null ? `$${v.toFixed(2)}` : '\u2014';

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <div className="flex items-center gap-3 mb-2">
        <span
          className="text-lg font-bold"
          style={{
            color: 'var(--t1)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {ticker}
        </span>
        <span
          className="px-2 py-0.5 rounded text-xs font-semibold"
          style={{
            background: 'var(--bg0)',
            color: 'var(--t2)',
            border: '1px solid var(--brd)',
          }}
        >
          {industry}
        </span>
        <span className="text-xs" style={{ color: 'var(--t3)' }}>
          {dateLabel}
        </span>
      </div>
      <div
        className="flex gap-6 text-xs"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          color: 'var(--t2)',
        }}
      >
        <span>Rev Growth: <strong style={{ color: 'var(--t1)' }}>{fmt(rg, '%')}</strong></span>
        <span>EPS Growth: <strong style={{ color: 'var(--t1)' }}>{fmt(xg, '%')}</strong></span>
        <span>Fwd EPS: <strong style={{ color: 'var(--t1)' }}>{fmtDollar(fe)}</strong></span>
      </div>
    </div>
  );
}
