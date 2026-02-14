'use client';

import { HistoricalBaseline } from '../lib/valueScore';
import { MetricType, COLORS } from '../lib/types';

interface ValueScoreBaselineProps {
  baseline: HistoricalBaseline | null;
  metricType: MetricType;
}

export default function ValueScoreBaseline({ baseline, metricType }: ValueScoreBaselineProps) {
  const color = COLORS[metricType].m;

  const stats: [string, string][] = baseline
    ? [
        ['Avg Slope', baseline.avgSlope.toFixed(3)],
        ['Avg Intercept', baseline.avgIntercept.toFixed(2)],
        ['Periods', String(baseline.periodCount)],
        ['Avg R\u00B2', baseline.avgR2.toFixed(3)],
      ]
    : [
        ['Avg Slope', '\u2014'],
        ['Avg Intercept', '\u2014'],
        ['Periods', '0'],
        ['Avg R\u00B2', '\u2014'],
      ];

  return (
    <div className="grid gap-2 mb-3" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
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
              fontSize: '14px',
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
