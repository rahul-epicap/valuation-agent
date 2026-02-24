'use client';

import { useMemo } from 'react';
import { DashboardData, MetricType, METRIC_LABELS, COLORS } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import { getActiveTickers } from '../lib/filters';
import {
  computeHistoricalBaselineWeighted,
  computeSingleTickerScore,
  computeDeviationTimeSeries,
  computeSpotScore,
  computePercentileRank,
  HistoricalBaseline,
  SingleTickerScore,
  SpotScore,
  PercentileResult,
} from '../lib/valueScore';
import MetricToggle from './MetricToggle';
import ValueScoreBaseline from './ValueScoreBaseline';
import TickerSearchSelect from './TickerSearchSelect';
import CompanyHeader from './CompanyHeader';
import DeviationChart from './DeviationChart';
import RegressionComparison from './RegressionComparison';

interface ValueScoreViewProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function ValueScoreView({ data, state, dispatch }: ValueScoreViewProps) {
  const metricType: MetricType = state.reg;
  const ticker = state.vsTicker;

  const activeTickers = useMemo(
    () => getActiveTickers(data, state.exTk, state.indOn, state.idxOn),
    [data, state.exTk, state.indOn, state.idxOn]
  );

  // Expensive: historical baselines (recompute only when data/metric/filters change)
  const baselineFull = useMemo(
    () =>
      computeHistoricalBaselineWeighted(
        data, metricType, activeTickers,
        state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax
      ),
    [data, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  const baselineEx2021 = useMemo(
    () =>
      computeHistoricalBaselineWeighted(
        data, metricType, activeTickers,
        state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax,
        2021
      ),
    [data, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  // Cheap: single-ticker scores against each baseline
  const scoreFull = useMemo(
    () =>
      ticker && baselineFull
        ? computeSingleTickerScore(data, ticker, metricType, state.di, baselineFull)
        : null,
    [data, ticker, metricType, state.di, baselineFull]
  );

  const scoreEx2021 = useMemo(
    () =>
      ticker && baselineEx2021
        ? computeSingleTickerScore(data, ticker, metricType, state.di, baselineEx2021)
        : null,
    [data, ticker, metricType, state.di, baselineEx2021]
  );

  // Expensive: deviation time series (only compute when ticker is selected)
  const deviationFull = useMemo(
    () =>
      ticker
        ? computeDeviationTimeSeries(
            data, ticker, metricType, activeTickers,
            state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax
          )
        : [],
    [data, ticker, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  const deviationEx2021 = useMemo(
    () =>
      ticker
        ? computeDeviationTimeSeries(
            data, ticker, metricType, activeTickers,
            state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax,
            2021
          )
        : [],
    [data, ticker, metricType, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  // Spot score: single-period regression at current date
  const spotScore = useMemo(
    () =>
      ticker
        ? computeSpotScore(
            data, ticker, metricType, state.di, activeTickers,
            state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax
          )
        : null,
    [data, ticker, metricType, state.di, activeTickers, state.revGrMin, state.revGrMax, state.epsGrMin, state.epsGrMax]
  );

  // Percentile rank: where current deviation sits in its own history
  const percentileResult = useMemo(
    () =>
      deviationFull.length > 0
        ? computePercentileRank(deviationFull, state.di)
        : null,
    [deviationFull, state.di]
  );

  return (
    <div>
      {/* Header row: ticker search + metric toggle */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <TickerSearchSelect
          tickers={data.tickers}
          industries={data.industries}
          selected={ticker}
          onSelect={(t) => dispatch({ type: 'SET_VS_TICKER', payload: t })}
        />
        <MetricToggle
          active={metricType}
          onChange={(t) => dispatch({ type: 'SET_REG', payload: t })}
        />
      </div>

      {/* Empty state */}
      {!ticker && (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
        >
          <div
            className="text-lg font-bold mb-2"
            style={{ color: 'var(--t2)' }}
          >
            Select a Ticker
          </div>
          <p className="text-xs" style={{ color: 'var(--t3)', maxWidth: 360, margin: '0 auto' }}>
            Search for a company above to see its regression-based valuation analysis.
            The analysis compares the ticker&apos;s current multiple to what the historical
            regression predicts given its growth rate.
          </p>
        </div>
      )}

      {/* Analysis content */}
      {ticker && (
        <>
          <CompanyHeader data={data} ticker={ticker} dateIndex={state.di} />

          {/* Historical Regression Analysis */}
          <div
            className="rounded-xl p-4 mb-4"
            style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
          >
            <h3
              className="text-sm font-bold mb-3"
              style={{ color: 'var(--t1)' }}
            >
              Historical Regression Analysis
            </h3>

            {/* Three-column result cards */}
            <div className="grid gap-3 md:gap-4 mb-4 grid-cols-1 md:grid-cols-3">
              <ScorePanel
                title="Full History"
                subtitle={`${data.dates[0]?.slice(0, 4)}\u2013${data.dates[data.dates.length - 1]?.slice(0, 4)}`}
                baseline={baselineFull}
                score={scoreFull}
                metricType={metricType}
              />
              <ScorePanel
                title="Excluding 2021"
                subtitle="Removes COVID distortion"
                baseline={baselineEx2021}
                score={scoreEx2021}
                metricType={metricType}
              />
              <SpotPanel
                spotScore={spotScore}
                metricType={metricType}
                date={data.dates[state.di] ?? ''}
              />
            </div>

            {/* Deviation chart */}
            {deviationFull.length > 0 && (
              <DeviationChart
                fullHistory={deviationFull}
                ex2021={deviationEx2021}
                currentDateIndex={state.di}
                metricType={metricType}
                p10={percentileResult?.p10}
                p90={percentileResult?.p90}
              />
            )}
          </div>

          {/* Regression Method Comparison */}
          <RegressionComparison
            data={data}
            metricType={metricType}
            dateIndex={state.di}
            activeTickers={activeTickers}
            ticker={ticker}
            tickerGrowth={spotScore?.growth ?? null}
            tickerActual={spotScore?.actual ?? null}
            revGrMin={state.revGrMin}
            revGrMax={state.revGrMax}
            epsGrMin={state.epsGrMin}
            epsGrMax={state.epsGrMax}
          />

          {/* Historical Percentile Context */}
          {percentileResult && (
            <PercentilePanel result={percentileResult} metricType={metricType} />
          )}

          {/* How to Read */}
          <div
            className="rounded-xl p-4"
            style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
          >
            <h3
              className="text-xs font-bold mb-2"
              style={{ color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}
            >
              How to Read
            </h3>
            <p className="text-xs leading-relaxed" style={{ color: 'var(--t3)' }}>
              The analysis compares this ticker&apos;s current {METRIC_LABELS[metricType]} multiple
              to what regression predicts given its growth rate.{' '}
              <strong style={{ color: 'var(--green)' }}>Negative %</strong> = trading below the
              predicted value (potentially undervalued).{' '}
              <strong style={{ color: 'var(--red)' }}>Positive %</strong> = trading above
              (potentially overvalued).{' '}
              <strong>Full History</strong> and <strong>Ex-2021</strong> use the average
              regression line across all periods.{' '}
              <strong>Spot</strong> uses only today&apos;s cross-sectional regression.{' '}
              The <strong>percentile</strong> shows where today&apos;s deviation sits in the
              ticker&apos;s own history (low = unusually cheap for this stock; high = unusually
              expensive).
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function ScorePanel({
  title,
  subtitle,
  baseline,
  score,
  metricType,
}: {
  title: string;
  subtitle: string;
  baseline: HistoricalBaseline | null;
  score: SingleTickerScore | null;
  metricType: MetricType;
}) {
  const col = COLORS[metricType];

  return (
    <div
      className="rounded-lg p-4"
      style={{ background: 'var(--bg0)', border: '1px solid var(--brd)' }}
    >
      <div className="mb-3">
        <h4 className="text-sm font-bold" style={{ color: 'var(--t1)' }}>
          {title}
        </h4>
        <p className="text-xs" style={{ color: 'var(--t3)' }}>
          {subtitle}
        </p>
      </div>

      {/* Score values */}
      {score ? (
        <div className="mb-3">
          <div
            className="grid gap-2 mb-2 grid-cols-3"
          >
            <StatCell label="Actual" value={`${score.actual.toFixed(1)}x`} color={col.m} />
            <StatCell label="Predicted" value={`${score.predicted.toFixed(1)}x`} color="var(--t2)" />
            <DeviationBadge pctDiff={score.pctDiff} />
          </div>
        </div>
      ) : (
        <p className="text-xs py-4 text-center mb-3" style={{ color: 'var(--t3)' }}>
          No data for this ticker / date / metric
        </p>
      )}

      {/* Baseline stats */}
      <ValueScoreBaseline baseline={baseline} metricType={metricType} />
    </div>
  );
}

function StatCell({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded text-center" style={{ background: 'var(--bg2)', padding: '9px' }}>
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
          fontSize: '16px',
          color,
        }}
      >
        {value}
      </span>
    </div>
  );
}

function DeviationBadge({ pctDiff }: { pctDiff: number }) {
  const isUnder = pctDiff < 0;
  const badgeColor = isUnder ? 'var(--green)' : 'var(--red)';
  const badgeBg = isUnder ? 'var(--green-d)' : 'var(--red-d)';

  return (
    <div className="rounded text-center" style={{ background: badgeBg, padding: '9px' }}>
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
        Deviation
      </label>
      <span
        className="font-bold"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '16px',
          color: badgeColor,
        }}
      >
        {pctDiff > 0 ? '+' : ''}{pctDiff.toFixed(1)}%
      </span>
    </div>
  );
}

function SpotPanel({
  spotScore,
  metricType,
  date,
}: {
  spotScore: SpotScore | null;
  metricType: MetricType;
  date: string;
}) {
  const col = COLORS[metricType];

  return (
    <div
      className="rounded-lg p-4"
      style={{ background: 'var(--bg0)', border: '1px solid var(--brd)' }}
    >
      <div className="mb-3">
        <h4 className="text-sm font-bold" style={{ color: 'var(--t1)' }}>
          Spot (Today)
        </h4>
        <p className="text-xs" style={{ color: 'var(--t3)' }}>
          Cross-section at {date.slice(0, 7)}
        </p>
      </div>

      {spotScore ? (
        <div className="mb-3">
          <div
            className="grid gap-2 mb-2 grid-cols-3"
          >
            <StatCell label="Actual" value={`${spotScore.actual.toFixed(1)}x`} color={col.m} />
            <StatCell label="Predicted" value={`${spotScore.predicted.toFixed(1)}x`} color="var(--t2)" />
            <DeviationBadge pctDiff={spotScore.pctDiff} />
          </div>
        </div>
      ) : (
        <p className="text-xs py-4 text-center mb-3" style={{ color: 'var(--t3)' }}>
          No data for this ticker / date / metric
        </p>
      )}

      {/* Spot regression stats */}
      <div
        className="rounded p-2"
        style={{ background: 'var(--bg2)' }}
      >
        <div className="grid gap-1 grid-cols-4">
          <MiniStat label="Slope" value={spotScore ? spotScore.slope.toFixed(2) : '—'} />
          <MiniStat label="Intercept" value={spotScore ? spotScore.intercept.toFixed(1) : '—'} />
          <MiniStat label="R²" value={spotScore ? spotScore.r2.toFixed(2) : '—'} />
          <MiniStat label="N" value={spotScore ? String(spotScore.n) : '—'} />
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <label
        className="block"
        style={{
          fontSize: '7.5px',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          color: 'var(--t3)',
        }}
      >
        {label}
      </label>
      <span
        className="font-bold"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '12px',
          color: 'var(--t2)',
        }}
      >
        {value}
      </span>
    </div>
  );
}

function PercentilePanel({
  result,
  metricType,
}: {
  result: PercentileResult;
  metricType: MetricType;
}) {
  const col = COLORS[metricType];
  const isUnder = result.currentDeviation < 0;
  const devColor = isUnder ? 'var(--green)' : 'var(--red)';

  // Color the percentile: low = green (cheap for this stock), high = red (expensive)
  const pctColor = result.percentile <= 30
    ? 'var(--green)'
    : result.percentile >= 70
      ? 'var(--red)'
      : col.m;

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3
        className="text-sm font-bold mb-3"
        style={{ color: 'var(--t1)' }}
      >
        Historical Percentile Context
      </h3>

      <div className="grid gap-3 md:gap-4 grid-cols-2 md:grid-cols-4">
        <div className="rounded-lg p-3 text-center" style={{ background: 'var(--bg0)' }}>
          <label
            className="block mb-1"
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.7px',
              color: 'var(--t3)',
            }}
          >
            Current Deviation
          </label>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '18px',
              color: devColor,
            }}
          >
            {result.currentDeviation > 0 ? '+' : ''}{result.currentDeviation.toFixed(1)}%
          </span>
        </div>

        <div className="rounded-lg p-3 text-center" style={{ background: 'var(--bg0)' }}>
          <label
            className="block mb-1"
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.7px',
              color: 'var(--t3)',
            }}
          >
            Percentile
          </label>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '18px',
              color: pctColor,
            }}
          >
            {result.percentile.toFixed(0)}th
          </span>
          <p className="text-xs mt-1" style={{ color: 'var(--t3)' }}>
            of {result.sampleCount} periods
          </p>
        </div>

        <div className="rounded-lg p-3 text-center" style={{ background: 'var(--bg0)' }}>
          <label
            className="block mb-1"
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.7px',
              color: 'var(--t3)',
            }}
          >
            Historical Range
          </label>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '13px',
              color: 'var(--t2)',
            }}
          >
            {result.p10 > 0 ? '+' : ''}{result.p10.toFixed(1)}%
          </span>
          <span className="text-xs mx-1" style={{ color: 'var(--t3)' }}>to</span>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '13px',
              color: 'var(--t2)',
            }}
          >
            {result.p90 > 0 ? '+' : ''}{result.p90.toFixed(1)}%
          </span>
          <p className="text-xs mt-1" style={{ color: 'var(--t3)' }}>10th – 90th pctl</p>
        </div>

        <div className="rounded-lg p-3 text-center" style={{ background: 'var(--bg0)' }}>
          <label
            className="block mb-1"
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.7px',
              color: 'var(--t3)',
            }}
          >
            Median
          </label>
          <span
            className="font-bold"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '18px',
              color: 'var(--t2)',
            }}
          >
            {result.median > 0 ? '+' : ''}{result.median.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
