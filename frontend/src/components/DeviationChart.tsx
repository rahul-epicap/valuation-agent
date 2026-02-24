'use client';

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
import { DeviationPoint } from '../lib/valueScore';
import { COLORS, MetricType } from '../lib/types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

interface DeviationChartProps {
  fullHistory: DeviationPoint[];
  ex2021: DeviationPoint[];
  currentDateIndex: number;
  metricType: MetricType;
  p10?: number;
  p90?: number;
}

export default function DeviationChart({
  fullHistory,
  ex2021,
  currentDateIndex,
  metricType,
  p10,
  p90,
}: DeviationChartProps) {
  const col = COLORS[metricType];

  const labels = fullHistory.map((p) => p.date);

  const fullData = fullHistory.map((p) => p.pctDiff);
  const ex2021Data = ex2021.map((p) => p.pctDiff);

  // Vertical line annotation for current date
  const currentDatePlugin = {
    id: 'currentDateLine',
    afterDraw(chart: ChartJS) {
      if (currentDateIndex < 0 || currentDateIndex >= labels.length) return;
      const { ctx } = chart;
      const xScale = chart.scales['x'];
      const yScale = chart.scales['y'];
      if (!xScale || !yScale) return;
      const x = xScale.getPixelForValue(currentDateIndex);
      ctx.save();
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(255,255,255,0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.moveTo(x, yScale.top);
      ctx.lineTo(x, yScale.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 200 },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          boxWidth: 10,
          padding: 8,
          font: { size: 9.5 },
          usePointStyle: true,
          pointStyle: 'circle' as const,
          filter: (item: { text: string }) =>
            item.text !== '90th Percentile' && item.text !== '10th Percentile',
        },
      },
      tooltip: {
        backgroundColor: '#1a2440',
        borderColor: '#253252',
        borderWidth: 1,
        cornerRadius: 5,
        titleFont: { family: "'JetBrains Mono', monospace", size: 11, weight: 'bold' as const },
        bodyFont: { size: 10.5 },
        padding: 8,
        callbacks: {
          label: (item: { parsed: { y: number | null }; dataset: { label?: string } }) => {
            const y = item.parsed.y ?? 0;
            return `${item.dataset.label ?? ''}: ${y >= 0 ? '+' : ''}${y.toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: 'Date', font: { weight: 'bold' as const } },
        grid: { color: 'rgba(28,40,66,.25)' },
        ticks: { maxTicksLimit: 14, font: { size: 9.5 } },
      },
      y: {
        title: { display: true, text: 'Deviation from Predicted (%)', font: { weight: 'bold' as const } },
        grid: {
          color: (ctx: { tick: { value: number } }) =>
            ctx.tick.value === 0 ? 'rgba(136,146,166,.5)' : 'rgba(28,40,66,.25)',
          lineWidth: (ctx: { tick: { value: number } }) =>
            ctx.tick.value === 0 ? 1.5 : 1,
        },
      },
    },
    elements: {
      point: { radius: 0, hoverRadius: 4 },
      line: { tension: 0.3, borderWidth: 2 },
    },
  };

  const bandDatasets = p10 != null && p90 != null
    ? [
        {
          label: '90th Percentile',
          data: fullData.map(() => p90),
          borderColor: 'rgba(136,146,166,.35)',
          backgroundColor: 'rgba(136,146,166,.07)',
          borderDash: [3, 3],
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: '+1' as const,
          order: 4,
        },
        {
          label: '10th Percentile',
          data: fullData.map(() => p10),
          borderColor: 'rgba(136,146,166,.35)',
          backgroundColor: 'transparent',
          borderDash: [3, 3],
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: false as const,
          order: 5,
        },
      ]
    : [];

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Full History',
        data: fullData,
        borderColor: col.m,
        backgroundColor: col.b,
        pointBackgroundColor: col.m,
        fill: false,
        order: 1,
      },
      {
        label: 'Ex-2021',
        data: ex2021Data,
        borderColor: 'rgba(136,146,166,.8)',
        backgroundColor: 'rgba(136,146,166,.2)',
        pointBackgroundColor: 'rgba(136,146,166,.8)',
        borderDash: [4, 3],
        fill: false,
        order: 2,
      },
      ...bandDatasets,
    ],
  };

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <div className="mb-2">
        <h3
          className="text-sm font-bold"
          style={{ color: 'var(--t1)' }}
        >
          Deviation Over Time
        </h3>
        <p className="text-xs" style={{ color: 'var(--t3)' }}>
          How this ticker&apos;s under/overvaluation has evolved — per-period regression
        </p>
      </div>
      <div className="h-[220px] md:h-[280px]">
        <Line data={chartData} options={options} plugins={[currentDatePlugin]} />
      </div>
    </div>
  );
}
