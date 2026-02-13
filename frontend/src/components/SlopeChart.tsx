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
import { DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers, filterPoints } from '../lib/filters';
import { linearRegression } from '../lib/regression';
import MetricToggle from './MetricToggle';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

interface SlopeChartProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
}

export default function SlopeChart({ data, state, dispatch }: SlopeChartProps) {
  const type = state.slp;
  const col = COLORS[type];

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn),
    [data, state.exTk, state.indOn]
  );

  const slopes = useMemo(() => {
    const result: (number | null)[] = [];
    for (let di = 0; di < data.dates.length; di++) {
      const pts = filterPoints(data, type, di, activeTickers, state.epsCap);
      if (pts.length < 5) {
        result.push(null);
        continue;
      }
      const rg = linearRegression(pts.map((p) => [p.x, p.y] as [number, number]));
      result.push(rg ? +rg.slope.toFixed(6) : null);
    }
    return result;
  }, [data, type, activeTickers, state.epsCap]);

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
          label: (item: any) => `Slope: ${item.parsed.y.toFixed(4)}`,
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
      data: slopes,
      borderColor: col.m,
      backgroundColor: col.b,
      fill: { target: 'origin', above: col.m + '12' },
      pointBackgroundColor: col.m,
    },
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
      <div className="relative w-full" style={{ height: 320 }}>
        <Line data={{ labels: data.dates, datasets }} options={options} />
      </div>
    </div>
  );
}
