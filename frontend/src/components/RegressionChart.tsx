'use client';

import { useMemo } from 'react';
import { Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { DashboardData, COLORS, METRIC_TITLES, Y_LABELS, X_LABELS, HIGHLIGHT_COLORS } from '../lib/types';
import { DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers, filterPoints } from '../lib/filters';
import { linearRegression } from '../lib/regression';
import MetricToggle from './MetricToggle';
import RegressionStats from './RegressionStats';

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

interface RegressionChartProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
}

export default function RegressionChart({ data, state, dispatch }: RegressionChartProps) {
  const type = state.reg;
  const col = COLORS[type];

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn),
    [data, state.exTk, state.indOn]
  );

  const pts = useMemo(
    () => filterPoints(data, type, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax),
    [data, type, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  const regression = useMemo(
    () => linearRegression(pts.map((p) => [p.x, p.y] as [number, number])),
    [pts]
  );

  const { datasets, hlLegend } = useMemo(() => {
    const norm = pts.filter((p) => !state.hlTk.has(p.t));
    const hlP = pts.filter((p) => state.hlTk.has(p.t));
    const hlA = [...state.hlTk];
    const hlCM: Record<string, string> = {};
    hlA.forEach((tk, i) => (hlCM[tk] = HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length]));

    const xs = pts.map((p) => p.x);
    const xMin = xs.length > 0 ? Math.min(...xs) : 0;
    const xMax = xs.length > 0 ? Math.max(...xs) : 100;
    const sl = regression?.slope ?? 0;
    const ic = regression?.intercept ?? 0;

    const ds: any[] = [
      {
        label: 'Tickers',
        data: norm.map((p) => ({ x: p.x, y: p.y, t: p.t })),
        backgroundColor: 'rgba(255,255,255,.12)',
        borderColor: 'rgba(255,255,255,.2)',
        borderWidth: 1,
        pointRadius: 3,
        pointHoverRadius: 5,
        order: 3,
      },
      {
        label: 'Regression',
        data: pts.length >= 3 ? [{ x: xMin, y: sl * xMin + ic }, { x: xMax, y: sl * xMax + ic }] : [],
        borderColor: col.l,
        borderWidth: 2,
        borderDash: [6, 3],
        pointRadius: 0,
        showLine: true,
        fill: false,
        order: 2,
      },
    ];

    const byTk: Record<string, typeof hlP> = {};
    hlP.forEach((p) => {
      (byTk[p.t] = byTk[p.t] || []).push(p);
    });
    Object.entries(byTk).forEach(([tk, tp]) => {
      const c = hlCM[tk];
      ds.push({
        label: tk,
        data: tp.map((p) => ({ x: p.x, y: p.y, t: p.t })),
        backgroundColor: c,
        borderColor: c,
        borderWidth: 2,
        pointRadius: 7,
        pointHoverRadius: 10,
        pointStyle: 'triangle' as const,
        order: 1,
      });
    });

    const legend = hlA.map((tk, i) => ({
      ticker: tk,
      color: HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length],
    }));

    return { datasets: ds, hlLegend: legend };
  }, [pts, state.hlTk, regression, col]);

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 200 },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a2440',
        borderColor: '#253252',
        borderWidth: 1,
        cornerRadius: 5,
        titleFont: { family: "'JetBrains Mono', monospace", size: 11, weight: '600' },
        bodyFont: { size: 10.5 },
        padding: 8,
        callbacks: {
          title: (items: any[]) => items[0]?.raw?.t || '',
          label: (item: any) =>
            `Multiple: ${item.parsed.y.toFixed(2)}x  |  Growth: ${item.parsed.x.toFixed(1)}%`,
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: X_LABELS[type], font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { callback: (v: number) => v + '%' },
      },
      y: {
        title: { display: true, text: Y_LABELS[type], font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { callback: (v: number) => v + 'x' },
      },
    },
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="font-bold" style={{ fontSize: '13.5px', letterSpacing: '-0.2px' }}>
            {METRIC_TITLES[type]}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>
            Linear regression — highlighted tickers shown in colour
          </div>
        </div>
        <MetricToggle active={type} onChange={(t) => dispatch({ type: 'SET_REG', payload: t })} />
      </div>
      <RegressionStats regression={regression} date={data.dates[state.di]} metricType={type} />
      <div className="relative w-full" style={{ height: 380 }}>
        <Scatter data={{ datasets }} options={options} />
      </div>
      <div className="flex flex-wrap gap-1 mt-1.5">
        {hlLegend.length > 0 ? (
          hlLegend.map(({ ticker, color }) => (
            <span
              key={ticker}
              className="px-1.5 py-0.5 rounded font-semibold"
              style={{
                fontSize: '9.5px',
                background: color + '22',
                color: color,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              &#9650; {ticker}
            </span>
          ))
        ) : (
          <span style={{ fontSize: '10px', color: 'var(--t3)' }}>Click a ticker to highlight</span>
        )}
      </div>
    </div>
  );
}
