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
import { DashboardData, COLORS, HIGHLIGHT_COLORS, MULTIPLE_KEYS, Y_LABELS_TIME } from '../lib/types';
import { DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers, filterMultiples, percentile } from '../lib/filters';
import MetricToggle from './MetricToggle';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

interface MultiplesChartProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
  startDi: number;
  endDi: number;
  chartHeight: number;
}

export default function MultiplesChart({ data, state, dispatch, startDi, endDi, chartHeight }: MultiplesChartProps) {
  const type = state.mul;
  const col = COLORS[type];
  const mk = MULTIPLE_KEYS[type];

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn),
    [data, state.exTk, state.indOn]
  );

  const { avgs, q75s } = useMemo(() => {
    const avgs: (number | null)[] = [];
    const q75s: (number | null)[] = [];
    for (let di = 0; di < data.dates.length; di++) {
      const vals = filterMultiples(data, type, di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax);
      if (vals.length < 4) {
        avgs.push(null);
        q75s.push(null);
        continue;
      }
      vals.sort((a, b) => a - b);
      avgs.push(+(vals.reduce((s, v) => s + v, 0) / vals.length).toFixed(2));
      q75s.push(+vals[Math.floor(vals.length * 0.75)].toFixed(2));
    }
    return { avgs, q75s };
  }, [data, type, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]);

  const slicedAvgs = useMemo(() => avgs.slice(startDi, endDi + 1), [avgs, startDi, endDi]);
  const slicedQ75s = useMemo(() => q75s.slice(startDi, endDi + 1), [q75s, startDi, endDi]);

  const percentileDatasets = useMemo(() => {
    const valid = slicedAvgs.filter((v): v is number => v != null);
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
        order: 5,
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
        order: 5,
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
        order: 5,
      },
    ];
  }, [slicedAvgs, startDi, endDi]);

  const datasets = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ds: any[] = [
      {
        label: 'Top Quartile',
        data: slicedQ75s,
        borderColor: col.m,
        backgroundColor: col.m + '18',
        fill: true,
        borderWidth: 2,
        order: 2,
      },
      {
        label: 'Average',
        data: slicedAvgs,
        borderColor: '#8892a6',
        backgroundColor: 'rgba(136,146,166,.08)',
        fill: true,
        borderWidth: 2,
        borderDash: [5, 3],
        order: 3,
      },
      ...percentileDatasets,
    ];

    const hlA = [...state.hlTk];
    hlA.forEach((tk, i) => {
      const fm = data.fm[tk];
      if (!fm) return;
      ds.push({
        label: tk,
        data: fm[mk].slice(startDi, endDi + 1),
        borderColor: HIGHLIGHT_COLORS[i % HIGHLIGHT_COLORS.length],
        backgroundColor: 'transparent',
        borderWidth: 2.5,
        fill: false,
        order: 1,
        pointRadius: 0,
        pointHoverRadius: 4,
      });
    });

    return ds;
  }, [slicedAvgs, slicedQ75s, percentileDatasets, state.hlTk, data, mk, col, startDi, endDi]);

  const options: Record<string, unknown> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 200 },
    plugins: {
      legend: {
        display: true,
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
        mode: 'index',
        intersect: false,
        callbacks: {
          label: (item: { dataset: { label: string }; parsed: { y: number | null } }) =>
            `${item.dataset.label}: ${item.parsed.y != null ? item.parsed.y.toFixed(1) + 'x' : 'n/a'}`,
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: 'Date', font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.2)' },
        ticks: { maxTicksLimit: 14, font: { size: 9.5 } },
      },
      y: {
        title: { display: true, text: Y_LABELS_TIME[type], font: { weight: '600' } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { callback: (v: number) => v + 'x' },
      },
    },
    elements: {
      point: { radius: 0, hoverRadius: 4 },
      line: { tension: 0.3, borderWidth: 2 },
    },
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="font-bold" style={{ fontSize: '13.5px', letterSpacing: '-0.2px' }}>
            Multiples Over Time
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>
            Average vs Top Quartile — responds to all filters
          </div>
        </div>
        <MetricToggle active={type} onChange={(t) => dispatch({ type: 'SET_MUL', payload: t })} />
      </div>
      <div className={`relative w-full ${chartHeight === 0 ? 'flex-1 min-h-0' : ''}`} style={chartHeight > 0 ? { height: chartHeight } : undefined}>
        <Line data={{ labels: data.dates.slice(startDi, endDi + 1), datasets }} options={options} />
      </div>
    </div>
  );
}
