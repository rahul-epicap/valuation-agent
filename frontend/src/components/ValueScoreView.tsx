'use client';

import { useMemo } from 'react';
import { DashboardData, MetricType, METRIC_LABELS } from '../lib/types';
import { DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers } from '../lib/filters';
import {
  computeHistoricalBaseline,
  computeValueScores,
  HistoricalBaseline,
  ValueScoreEntry,
} from '../lib/valueScore';
import MetricToggle from './MetricToggle';
import ValueScoreBaseline from './ValueScoreBaseline';
import ValueScoreCard from './ValueScoreCard';

interface ValueScoreViewProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
}

export default function ValueScoreView({ data, state, dispatch }: ValueScoreViewProps) {
  const metricType: MetricType = state.reg;

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn),
    [data, state.exTk, state.indOn]
  );

  // Expensive: recompute only when data/metric/filters/tickers change
  const baselineFull = useMemo(
    () =>
      computeHistoricalBaseline(
        data, metricType, activeTickers,
        state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax
      ),
    [data, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  const baselineEx2021 = useMemo(
    () =>
      computeHistoricalBaseline(
        data, metricType, activeTickers,
        state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax,
        2021
      ),
    [data, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  // Cheap: recompute when baseline or selected date changes
  const scoresFull = useMemo(
    () =>
      baselineFull
        ? computeValueScores(
            data, metricType, state.di, activeTickers,
            state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax,
            baselineFull
          )
        : [],
    [data, metricType, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax, baselineFull]
  );

  const scoresEx2021 = useMemo(
    () =>
      baselineEx2021
        ? computeValueScores(
            data, metricType, state.di, activeTickers,
            state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax,
            baselineEx2021
          )
        : [],
    [data, metricType, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax, baselineEx2021]
  );

  // Build highlight index map for highlighted tickers
  const hlIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    let i = 0;
    for (const t of state.hlTk) {
      map.set(t, i++);
    }
    return map;
  }, [state.hlTk]);

  const dateLabel = data.dates[state.di]
    ? new Date(data.dates[state.di] + 'T00:00:00').toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
      })
    : '';

  return (
    <div>
      {/* Header row: metric toggle + date */}
      <div className="flex items-center justify-between mb-4">
        <MetricToggle
          active={metricType}
          onChange={(t) => dispatch({ type: 'SET_REG', payload: t })}
        />
        <span
          className="text-xs font-semibold"
          style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--t3)' }}
        >
          {METRIC_LABELS[metricType]} &middot; {dateLabel}
        </span>
      </div>

      {/* Two-column layout */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <ScoreColumn
          title="Full History"
          subtitle={`${data.dates[0]?.slice(0, 4)}\u2013${data.dates[data.dates.length - 1]?.slice(0, 4)}`}
          baseline={baselineFull}
          scores={scoresFull}
          metricType={metricType}
          hlIndexMap={hlIndexMap}
        />
        <ScoreColumn
          title="Excluding 2021"
          subtitle="Removes COVID distortion"
          baseline={baselineEx2021}
          scores={scoresEx2021}
          metricType={metricType}
          hlIndexMap={hlIndexMap}
        />
      </div>

      {/* How to Read */}
      <div
        className="mt-4 rounded-xl p-4"
        style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
      >
        <h3
          className="text-xs font-bold mb-2"
          style={{ color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}
        >
          How to Read
        </h3>
        <p className="text-xs leading-relaxed" style={{ color: 'var(--t3)' }}>
          Each card compares a ticker&apos;s current {METRIC_LABELS[metricType]} multiple to what a historical average
          regression line would predict given its growth rate. <strong style={{ color: 'var(--green)' }}>Negative %</strong> =
          trading below the historical norm (potentially undervalued). <strong style={{ color: 'var(--red)' }}>Positive %</strong> =
          trading above (potentially overvalued). The &ldquo;Excluding 2021&rdquo; column removes pandemic-era distortion
          from the baseline regression.
        </p>
      </div>
    </div>
  );
}

function ScoreColumn({
  title,
  subtitle,
  baseline,
  scores,
  metricType,
  hlIndexMap,
}: {
  title: string;
  subtitle: string;
  baseline: HistoricalBaseline | null;
  scores: ValueScoreEntry[];
  metricType: MetricType;
  hlIndexMap: Map<string, number>;
}) {
  return (
    <div
      className="rounded-xl p-4 flex flex-col"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <div className="mb-3">
        <h2 className="text-sm font-bold" style={{ color: 'var(--t1)' }}>
          {title}
        </h2>
        <p className="text-xs" style={{ color: 'var(--t3)' }}>
          {subtitle}
        </p>
      </div>

      <ValueScoreBaseline baseline={baseline} metricType={metricType} />

      {scores.length === 0 ? (
        <p className="text-xs py-8 text-center" style={{ color: 'var(--t3)' }}>
          No data for this date / filter combination
        </p>
      ) : (
        <div className="flex flex-col gap-1.5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 320px)' }}>
          {scores.map((entry) => (
            <ValueScoreCard
              key={entry.ticker}
              entry={entry}
              highlightIndex={hlIndexMap.get(entry.ticker) ?? null}
            />
          ))}
        </div>
      )}
    </div>
  );
}
