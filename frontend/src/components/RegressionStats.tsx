'use client';

import { RegressionResult, MetricType, COLORS } from '../lib/types';

interface RegressionStatsProps {
  regression: RegressionResult | null;
  date: string;
  metricType: MetricType;
}

export default function RegressionStats({ regression, date, metricType }: RegressionStatsProps) {
  const color = COLORS[metricType].m;
  const sl = regression?.slope ?? 0;
  const ic = regression?.intercept ?? 0;
  const r2 = regression?.r2 ?? 0;
  const n = regression?.n ?? 0;

  const stats = [
    ['R\u00B2', r2.toFixed(3)],
    ['Slope', sl.toFixed(3)],
    ['Intercept', ic.toFixed(2)],
    ['Points', String(n)],
    ['Date', date],
  ];

  return (
    <div className="grid gap-2 mb-3" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
      {stats.map(([label, value]) => (
        <div
          key={label}
          className="rounded text-center"
          style={{ background: 'var(--bg0)', padding: '9px' }}
        >
          <label
            className="block mb-0.5"
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.7px',
              color: 'var(--t3)',
            }}
          >
            {label}
          </label>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '16px',
              color,
            }}
          >
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}
