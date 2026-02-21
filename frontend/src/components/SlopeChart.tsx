'use client';

import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { DashboardData, COLORS } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers, filterPoints, percentile } from '../lib/filters';
import { linearRegressionCooks } from '../lib/regression';
import MetricToggle from './MetricToggle';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

interface SlopeChartProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
  startDi: number;
  endDi: number;
  chartHeight: number;
}

export default function SlopeChart({ data, state, dispatch, startDi, endDi, chartHeight }: SlopeChartProps) {
  const type = state.slp;
  const col = COLORS[type];

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn, state.idxOn, state.idxFilterMode),
    [data, state.exTk, state.indOn, state.idxOn, state.idxFilterMode]
  );

  const slopes = useMemo(() => {
    const result: (number | null)[] = [];
    for (let di = 0; di < data.dates.length; di++) {
      const pts = filterPoints(data, type, di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax);
      if (pts.length < 5) {
        result.push(null);
        continue;
      }
      const rg = linearRegressionCooks(pts.map((p) => [p.x, p.y] as [number, number]));
      result.push(rg ? +rg.slope.toFixed(6) : null);
    }
    return result;
  }, [data, type, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]);

  const slicedSlopes = useMemo(() => slopes.slice(startDi, endDi + 1), [slopes, startDi, endDi]);

  const percentileDatasets = useMemo(() => {
    const valid = slicedSlopes.filter((v): v is number => v != null);
    if (valid.length < 4) return [];
    const sorted = [...valid].sort((a, b) => a - b);
    const p25 = percentile(sorted, 0.25);
    const p50 = percentile(sorted, 0.5);
    const p75 = percentile(sorted, 0.75);
    const len = endDi - startDi + 1;
    return [
      {
        label: 'P25',
        data: Array(len).fill(p25),
        borderColor: 'rgba(136,146,166,.7)',
        borderDash: [4, 4],
        borderWidth: 1,
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        order: 4,
      },
      {
        label: 'Median',
        data: Array(len).fill(p50),
        borderColor: 'rgba(136,146,166,.9)',
        borderDash: [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        order: 4,
      },
      {
        label: 'P75',
        data: Array(len).fill(p75),
        borderColor: 'rgba(136,146,166,.7)',
        borderDash: [4, 4],
        borderWidth: 1,
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        order: 4,
      },
    ];
  }, [slicedSlopes, startDi, endDi]);

  const options: Record<string, unknown> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 200 },
    plugins: {
      legend: {
        display: percentileDatasets.length > 0,
        position: 'top',
        labels: { boxWidth: 10, padding: 8, font: { size: 9.5 }, usePointStyle: true, pointStyle: 'circle' },
      },
      tooltip: {
        backgroundColor: '#1a2440',
        borderColor: '#253252',
        borderWidth: 1,
        cornerRadius: 5,
        titleFont: { family: "'JetBrains Mono', monospace", size: 11, weight: '600' },
        bodyFont: { size: 10.5 },
        padding: 8,
        callbacks: {
          label: (item: { parsed: { y: number }; dataset: { label: string } }) => {
            if (['P25', 'Median', 'P75'].includes(item.dataset.label)) {
              return `${item.dataset.label}: ${item.parsed.y.toFixed(4)}`;
            }
            return `Slope: ${item.parsed.y.toFixed(4)}`;
          },
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: 'Date', font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { maxTicksLimit: 14, font: { size: 9.5 } },
      },
      y: {
        title: { display: true, text: 'Regression Slope', font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.25)' },
      },
    },
    elements: {
      point: { radius: 1.5, hoverRadius: 5 },
      line: { tension: 0.3, borderWidth: 2.5 },
    },
  };

  const datasets = [
    {
      label: 'Slope',
      data: slicedSlopes,
      borderColor: col.m,
      backgroundColor: col.b,
      fill: { target: 'origin', above: col.m + '12' },
      pointBackgroundColor: col.m,
      order: 1,
    },
    ...percentileDatasets,
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="font-bold" style={{ fontSize: '13.5px', letterSpacing: '-0.2px' }}>
            Regression Slope Over Time
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>
            Slope trend — responds to all filters
          </div>
        </div>
        <MetricToggle active={type} onChange={(t) => dispatch({ type: 'SET_SLP', payload: t })} />
      </div>
      <div className={`relative w-full ${chartHeight === 0 ? 'flex-1 min-h-0' : ''}`} style={chartHeight > 0 ? { height: chartHeight } : undefined}>
        <Line data={{ labels: data.dates.slice(startDi, endDi + 1), datasets }} options={options} />
      </div>
    </div>
  );
}
