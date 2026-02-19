'use client';

import { useMemo } from 'react';
import { DashboardData, MetricType, COLORS, METRIC_LABELS } from '../lib/types';
import {
  computeMethodComparison,
  computeHistoricalBaseline,
  computeHistoricalBaselineWeighted,
  HistoricalBaseline,
} from '../lib/valueScore';

interface RegressionComparisonProps {
  data: DashboardData;
  metricType: MetricType;
  dateIndex: number;
  activeTickers: string[];
  ticker: string | null;
  tickerGrowth: number | null; // growth in % (already scaled)
  tickerActual: number | null; // actual multiple
  revGrMin: number | null;
  revGrMax: number | null;
  epsGrMin: number | null;
  epsGrMax: number | null;
}

export default function RegressionComparison({
  data,
  metricType,
  dateIndex,
  activeTickers,
  ticker,
  tickerGrowth,
  tickerActual,
  revGrMin,
  revGrMax,
  epsGrMin,
  epsGrMax,
}: RegressionComparisonProps) {
  const col = COLORS[metricType];

  // Spot: run all 4 regression methods on current scatter data
  const spotResults = useMemo(
    () =>
      computeMethodComparison(
        data, metricType, dateIndex, activeTickers,
        revGrMin, revGrMax, epsGrMin, epsGrMax
      ),
    [data, metricType, dateIndex, activeTickers, revGrMin, revGrMax, epsGrMin, epsGrMax]
  );

  // Historical: equal-weight vs R²-weighted baselines
  const baselineEqual = useMemo(
    () =>
      computeHistoricalBaseline(
        data, metricType, activeTickers,
        revGrMin, revGrMax, epsGrMin, epsGrMax
      ),
    [data, metricType, activeTickers, revGrMin, revGrMax, epsGrMin, epsGrMax]
  );

  const baselineWeighted = useMemo(
    () =>
      computeHistoricalBaselineWeighted(
        data, metricType, activeTickers,
        revGrMin, revGrMax, epsGrMin, epsGrMax
      ),
    [data, metricType, activeTickers, revGrMin, revGrMax, epsGrMin, epsGrMax]
  );

  // Find best R² among spot methods
  const bestR2 = spotResults.length > 0
    ? Math.max(...spotResults.map((r) => r.r2))
    : 0;

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3
        className="text-sm font-bold mb-1"
        style={{ color: 'var(--t1)' }}
      >
        Regression Method Comparison
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--t3)' }}>
        Spot cross-section at {data.dates[dateIndex]?.slice(0, 7)} for {METRIC_LABELS[metricType]}
      </p>

      {/* Spot regression comparison table */}
      <div className="overflow-x-auto mb-4">
        <table
          className="w-full text-xs"
          style={{ borderCollapse: 'separate', borderSpacing: 0 }}
        >
          <thead>
            <tr>
              {['Method', 'R\u00B2', 'N', 'Slope', 'Intercept',
                ...(ticker ? ['Predicted', 'Deviation'] : []),
              ].map((h) => (
                <th
                  key={h}
                  className="text-left px-3 py-2"
                  style={{
                    fontSize: '8.5px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.7px',
                    color: 'var(--t3)',
                    borderBottom: '1px solid var(--brd)',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {spotResults.map((r) => {
              const predicted = ticker && tickerGrowth != null
                ? r.predict(tickerGrowth)
                : null;
              const deviation = predicted && predicted > 0 && tickerActual != null
                ? ((tickerActual - predicted) / predicted) * 100
                : null;
              const isBestR2 = Math.abs(r.r2 - bestR2) < 1e-6;

              return (
                <tr
                  key={r.method}
                  style={{ background: isBestR2 ? 'var(--bg0)' : 'transparent' }}
                >
                  <td
                    className="px-3 py-2 font-bold"
                    style={{ color: 'var(--t1)', whiteSpace: 'nowrap' }}
                  >
                    {r.label}
                    {isBestR2 && (
                      <span
                        className="ml-2 px-1.5 py-0.5 rounded text-xs"
                        style={{
                          fontSize: '7px',
                          fontWeight: 700,
                          background: col.b,
                          color: col.m,
                          textTransform: 'uppercase',
                        }}
                      >
                        Best R²
                      </span>
                    )}
                  </td>
                  <NumCell value={r.r2} decimals={4} highlight={isBestR2} color={col.m} />
                  <td className="px-3 py-2" style={monoStyle}>
                    {r.n}
                    {r.n < r.nOriginal && (
                      <span style={{ color: 'var(--t3)', fontSize: '9px' }}>
                        /{r.nOriginal}
                      </span>
                    )}
                  </td>
                  <NumCell value={r.slope} decimals={3} />
                  <NumCell value={r.intercept} decimals={2} />
                  {ticker && (
                    <>
                      <NumCell
                        value={predicted}
                        decimals={1}
                        suffix="x"
                      />
                      <td className="px-3 py-2" style={monoStyle}>
                        {deviation != null ? (
                          <span
                            style={{
                              color: deviation < 0 ? 'var(--green)' : 'var(--red)',
                              fontWeight: 700,
                            }}
                          >
                            {deviation > 0 ? '+' : ''}{deviation.toFixed(1)}%
                          </span>
                        ) : (
                          <span style={{ color: 'var(--t3)' }}>—</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Historical baseline comparison: Equal-Weight vs R²-Weighted */}
      <h4
        className="text-xs font-bold mb-2"
        style={{ color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}
      >
        Historical Baseline: Equal-Weight vs R²-Weighted (Approach 4)
      </h4>
      <div className="overflow-x-auto">
        <table
          className="w-full text-xs"
          style={{ borderCollapse: 'separate', borderSpacing: 0 }}
        >
          <thead>
            <tr>
              {['Baseline', 'Avg Slope', 'Avg Intercept', 'Avg R²', 'Periods',
                ...(ticker ? ['Predicted', 'Deviation'] : []),
              ].map((h) => (
                <th
                  key={h}
                  className="text-left px-3 py-2"
                  style={{
                    fontSize: '8.5px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.7px',
                    color: 'var(--t3)',
                    borderBottom: '1px solid var(--brd)',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {([
              { label: 'Equal-Weight (Current)', baseline: baselineEqual },
              { label: 'R²-Weighted', baseline: baselineWeighted },
            ] as { label: string; baseline: HistoricalBaseline | null }[]).map(({ label, baseline }) => {
              if (!baseline) return null;
              const predicted = ticker && tickerGrowth != null
                ? baseline.avgSlope * tickerGrowth + baseline.avgIntercept
                : null;
              const deviation = predicted && predicted > 0 && tickerActual != null
                ? ((tickerActual - predicted) / predicted) * 100
                : null;

              return (
                <tr key={label}>
                  <td
                    className="px-3 py-2 font-bold"
                    style={{ color: 'var(--t1)', whiteSpace: 'nowrap' }}
                  >
                    {label}
                  </td>
                  <NumCell value={baseline.avgSlope} decimals={4} />
                  <NumCell value={baseline.avgIntercept} decimals={2} />
                  <NumCell value={baseline.avgR2} decimals={4} />
                  <td className="px-3 py-2" style={monoStyle}>
                    {baseline.periodCount}
                  </td>
                  {ticker && (
                    <>
                      <NumCell value={predicted} decimals={1} suffix="x" />
                      <td className="px-3 py-2" style={monoStyle}>
                        {deviation != null ? (
                          <span
                            style={{
                              color: deviation < 0 ? 'var(--green)' : 'var(--red)',
                              fontWeight: 700,
                            }}
                          >
                            {deviation > 0 ? '+' : ''}{deviation.toFixed(1)}%
                          </span>
                        ) : (
                          <span style={{ color: 'var(--t3)' }}>—</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const monoStyle: React.CSSProperties = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: '12px',
  color: 'var(--t2)',
};

function NumCell({
  value,
  decimals,
  suffix = '',
  highlight = false,
  color,
}: {
  value: number | null;
  decimals: number;
  suffix?: string;
  highlight?: boolean;
  color?: string;
}) {
  return (
    <td className="px-3 py-2" style={monoStyle}>
      {value != null ? (
        <span style={highlight && color ? { color, fontWeight: 700 } : undefined}>
          {value.toFixed(decimals)}{suffix}
        </span>
      ) : (
        <span style={{ color: 'var(--t3)' }}>—</span>
      )}
    </td>
  );
}
