'use client';

import { useMemo } from 'react';
import { Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ChartDataset,
  ChartOptions,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  TooltipItem,
} from 'chart.js';
import { DashboardData, COLORS, METRIC_TITLES, Y_LABELS, X_LABELS, HIGHLIGHT_COLORS, MultiFactorRegressionResult, MultiFactorScatterPoint } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers, filterPoints, filterPointsMultiFactor } from '../lib/filters';
import { linearRegressionCooks } from '../lib/regression';
import { multiFactorOLS, computeAdjustedPoints } from '../lib/multiFactorRegression';
import MetricToggle from './MetricToggle';
import RegressionStats from './RegressionStats';

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

interface RegressionChartProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function RegressionChart({ data, state, dispatch }: RegressionChartProps) {
  const type = state.reg;
  const col = COLORS[type];

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn, state.idxOn),
    [data, state.exTk, state.indOn, state.idxOn]
  );

  const mfActive = state.mfEnabled && state.regFactors.size > 0;
  const regFactorArray = useMemo(() => [...state.regFactors], [state.regFactors]);

  const pts = useMemo(
    () => mfActive
      ? filterPointsMultiFactor(data, type, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax, regFactorArray)
      : filterPoints(data, type, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax),
    [data, type, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax, mfActive, regFactorArray]
  );

  const regression = useMemo(
    () => linearRegressionCooks(pts.map((p) => [p.x, p.y] as [number, number])),
    [pts]
  );

  const mfRegression: MultiFactorRegressionResult | null = useMemo(() => {
    if (!mfActive || pts.length < 3) return null;
    const mfPts = pts as MultiFactorScatterPoint[];
    const y = mfPts.map((p) => p.y);
    const X = mfPts.map((p) => {
      const row = [1, p.x]; // intercept + growth
      for (const factor of regFactorArray) {
        row.push(p.factorValues?.[factor] ?? 0);
      }
      return row;
    });
    return multiFactorOLS(y, X, regFactorArray);
  }, [mfActive, pts, regFactorArray]);

  const adjustedPts: MultiFactorScatterPoint[] = useMemo(() => {
    if (!mfActive || !mfRegression) return pts as MultiFactorScatterPoint[];
    return computeAdjustedPoints(pts as MultiFactorScatterPoint[], mfRegression);
  }, [mfActive, mfRegression, pts]);

  const { datasets, hlLegend } = useMemo(() => {
    const useMf = mfActive && mfRegression != null;
    const displayPts = useMf ? adjustedPts : pts;
    const removedSet = new Set(useMf ? [] : (regression?.removedIndices ?? []));
    const hlA = [...state.hlTk];
    const hlCM: Record<string, string> = {};
    hlA.forEach((tk, i) => (hlCM[tk] = HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length]));

    // Separate points: normal kept, Cook's outliers, and highlighted
    type DisplayPoint = typeof displayPts[number];
    const norm: DisplayPoint[] = [];
    const outliers: DisplayPoint[] = [];
    displayPts.forEach((p, i) => {
      if (state.hlTk.has(p.t)) return;
      if (removedSet.has(i)) {
        outliers.push(p);
      } else {
        norm.push(p);
      }
    });
    const hlP = displayPts.filter((p) => state.hlTk.has(p.t));

    // Get y-value for display (adjustedY in MF mode, raw y otherwise)
    const getY = (p: DisplayPoint): number =>
      useMf ? ((p as MultiFactorScatterPoint).adjustedY ?? p.y) : p.y;

    const xs = displayPts.map((p) => p.x);
    const xMin = xs.length > 0 ? Math.min(...xs) : 0;
    const xMax = xs.length > 0 ? Math.max(...xs) : 100;

    // Regression line coefficients
    const sl = useMf ? mfRegression!.growthCoefficient : (regression?.slope ?? 0);
    const ic = useMf ? mfRegression!.intercept : (regression?.intercept ?? 0);

    const ds: ChartDataset<'scatter'>[] = [
      {
        label: 'Tickers',
        data: norm.map((p) => ({ x: p.x, y: getY(p), t: p.t })),
        backgroundColor: 'rgba(255,255,255,.12)',
        borderColor: 'rgba(255,255,255,.2)',
        borderWidth: 1,
        pointRadius: 3,
        pointHoverRadius: 5,
        order: 3,
      },
    ];

    // Cook's Distance outliers — shown as red crossed-out dots (single-factor mode only)
    if (outliers.length > 0) {
      ds.push({
        label: "Cook's Outliers",
        data: outliers.map((p) => ({ x: p.x, y: getY(p), t: p.t })),
        backgroundColor: 'rgba(239,68,68,.25)',
        borderColor: 'rgba(239,68,68,.5)',
        borderWidth: 1.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointStyle: 'crossRot' as const,
        order: 4,
      });
    }

    ds.push({
      label: 'Regression',
      data: displayPts.length >= 3 ? [{ x: xMin, y: sl * xMin + ic }, { x: xMax, y: sl * xMax + ic }] : [],
      borderColor: col.l,
      borderWidth: 2,
      borderDash: [6, 3],
      pointRadius: 0,
      showLine: true,
      fill: false,
      order: 2,
    });

    const byTk: Record<string, typeof hlP> = {};
    hlP.forEach((p) => {
      (byTk[p.t] = byTk[p.t] || []).push(p);
    });
    Object.entries(byTk).forEach(([tk, tp]) => {
      const c = hlCM[tk];
      ds.push({
        label: tk,
        data: tp.map((p) => ({ x: p.x, y: getY(p), t: p.t })),
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
  }, [pts, adjustedPts, mfActive, mfRegression, state.hlTk, regression, col]);

  const options: ChartOptions<'scatter'> = {
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
        titleFont: { family: "'JetBrains Mono', monospace", size: 11, weight: 'bold' as const },
        bodyFont: { size: 10.5 },
        padding: 8,
        callbacks: {
          title: (items: TooltipItem<'scatter'>[]) => (items[0]?.raw as Record<string, unknown>)?.t as string || '',
          label: (item: TooltipItem<'scatter'>) => {
            const prefix = item.dataset.label === "Cook's Outliers" ? '✕ ' : '';
            return `${prefix}Multiple: ${item.parsed.y?.toFixed(2)}x  |  Growth: ${item.parsed.x?.toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: X_LABELS[type], font: { weight: 'bold' as const } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { callback: (v: string | number) => v + '%' },
      },
      y: {
        title: { display: true, text: Y_LABELS[type], font: { weight: 'bold' as const } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { callback: (v: string | number) => v + 'x' },
      },
    },
  };

  const nRemoved = (mfActive && mfRegression) ? 0 : (regression?.removedIndices?.length ?? 0);
  const mfSubtitle = mfActive && mfRegression
    ? `Partial regression — controlling for ${mfRegression.factors.map((f) => f.name).join(', ')}`
    : "Cook's Distance regression — outliers shown as red ✕";

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="font-bold" style={{ fontSize: '13.5px', letterSpacing: '-0.2px' }}>
            {METRIC_TITLES[type]}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>
            {mfSubtitle}
          </div>
        </div>
        <MetricToggle active={type} onChange={(t) => dispatch({ type: 'SET_REG', payload: t })} />
      </div>
      <RegressionStats
        regression={regression}
        date={data.dates[state.di]}
        metricType={type}
        nRemoved={nRemoved}
        activeIndexNames={[...state.idxOn]}
        mfRegression={mfActive ? mfRegression : null}
        singleFactorR2={regression?.r2 ?? null}
      />
      <div className="relative w-full h-[260px] md:h-[380px]">
        <Scatter data={{ datasets }} options={options} />
      </div>
      <div className="flex flex-wrap gap-1 mt-1.5">
        {nRemoved > 0 && (
          <span
            className="px-1.5 py-0.5 rounded font-semibold"
            style={{
              fontSize: '9.5px',
              background: 'rgba(239,68,68,.12)',
              color: '#ef4444',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            ✕ {nRemoved} outlier{nRemoved !== 1 ? 's' : ''} removed
          </span>
        )}
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
