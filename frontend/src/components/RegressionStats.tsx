'use client';

import { useState } from 'react';
import { RegressionResult, MetricType, MultiFactorRegressionResult, COLORS } from '../lib/types';

interface RegressionStatsProps {
  regression: RegressionResult | null;
  date: string;
  metricType: MetricType;
  nRemoved?: number;
  activeIndexNames?: string[];
  mfRegression?: MultiFactorRegressionResult | null;
  singleFactorR2?: number | null;
}

export default function RegressionStats({
  regression,
  date,
  metricType,
  nRemoved,
  activeIndexNames,
  mfRegression,
  singleFactorR2,
}: RegressionStatsProps) {
  const [showFactors, setShowFactors] = useState(false);
  const color = COLORS[metricType].m;
  const isMf = mfRegression != null;

  const r2 = isMf ? mfRegression.r2 : (regression?.r2 ?? 0);
  const n = isMf ? mfRegression.n : (regression?.n ?? 0);

  // R² improvement delta
  const r2Delta = isMf && singleFactorR2 != null ? r2 - singleFactorR2 : null;

  const stats: [string, string][] = isMf
    ? [
        ['R\u00B2', r2.toFixed(3) + (r2Delta != null && r2Delta > 0 ? ` (+${r2Delta.toFixed(3)})` : '')],
        ['Adj. R\u00B2', mfRegression.adjustedR2.toFixed(3)],
        ['Growth Coeff', mfRegression.growthCoefficient.toFixed(3)],
        ['Factors', String(mfRegression.factors.length)],
        ['Points', String(n)],
        ['Date', date],
      ]
    : [
        ['R\u00B2', (regression?.r2 ?? 0).toFixed(3)],
        ['Slope', (regression?.slope ?? 0).toFixed(3)],
        ['Intercept', (regression?.intercept ?? 0).toFixed(2)],
        ['Points', nRemoved && nRemoved > 0 ? `${n} (\u2212${nRemoved})` : String(n)],
        ['Date', date],
      ];

  return (
    <div>
      <div className={`grid gap-1.5 md:gap-2 mb-3 ${isMf ? 'grid-cols-3 md:grid-cols-6' : 'grid-cols-3 md:grid-cols-5'}`}>
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
                fontSize: label === 'R\u00B2' && r2Delta != null && r2Delta > 0 ? '13px' : '16px',
                color,
              }}
            >
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* Factor coefficients table (multi-factor mode) */}
      {isMf && mfRegression.factors.length > 0 && (
        <div className="mb-2">
          <button
            onClick={() => setShowFactors(!showFactors)}
            className="cursor-pointer"
            style={{
              fontSize: '9.5px',
              fontWeight: 600,
              color: 'var(--t3)',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
          >
            {showFactors ? '\u25BC' : '\u25B6'} Factor Coefficients ({mfRegression.factors.length})
          </button>
          {showFactors && (
            <div
              className="mt-1 rounded overflow-hidden"
              style={{ background: 'var(--bg0)', fontSize: '10px' }}
            >
              <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--brd)' }}>
                    <th
                      className="text-left px-2 py-1"
                      style={{ color: 'var(--t3)', fontWeight: 700, fontSize: '8.5px', textTransform: 'uppercase', letterSpacing: '0.5px' }}
                    >
                      Factor
                    </th>
                    <th
                      className="text-right px-2 py-1"
                      style={{ color: 'var(--t3)', fontWeight: 700, fontSize: '8.5px', textTransform: 'uppercase', letterSpacing: '0.5px' }}
                    >
                      Coefficient
                    </th>
                    <th
                      className="text-right px-2 py-1"
                      style={{ color: 'var(--t3)', fontWeight: 700, fontSize: '8.5px', textTransform: 'uppercase', letterSpacing: '0.5px' }}
                    >
                      Interpretation
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[...mfRegression.factors]
                    .sort((a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient))
                    .map((f) => (
                      <tr key={f.name} style={{ borderBottom: '1px solid var(--brd)' }}>
                        <td
                          className="px-2 py-1 font-semibold"
                          style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--t1)' }}
                        >
                          {f.name}
                        </td>
                        <td
                          className="text-right px-2 py-1 font-bold"
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            color: f.coefficient > 0 ? '#10b981' : f.coefficient < 0 ? '#ef4444' : 'var(--t2)',
                          }}
                        >
                          {f.coefficient >= 0 ? '+' : ''}{f.coefficient.toFixed(3)}
                        </td>
                        <td
                          className="text-right px-2 py-1"
                          style={{ color: 'var(--t3)' }}
                        >
                          {f.coefficient >= 0
                            ? `+${Math.abs(f.coefficient).toFixed(1)}x premium`
                            : `\u2212${Math.abs(f.coefficient).toFixed(1)}x discount`}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeIndexNames && activeIndexNames.length > 0 && (
        <div className="flex gap-1 mb-2 flex-wrap">
          <span style={{ fontSize: '8.5px', color: 'var(--t3)', fontWeight: 600 }}>
            Index Filter:
          </span>
          {activeIndexNames.map((name) => (
            <span
              key={name}
              className="px-1.5 py-0.5 rounded font-semibold"
              style={{
                fontSize: '8.5px',
                background: 'rgba(245,158,11,.12)',
                color: '#f59e0b',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
