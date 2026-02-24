'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { DashboardData, PeerSearchResult, PeerValuationResult, COLORS, IndexRegressionResult, CompositeValuation } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import { fetchPeerValuation } from '../lib/api';

interface PeerValuationViewProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function PeerValuationView({ data, state, dispatch }: PeerValuationViewProps) {
  const [ticker, setTicker] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const handleTickerInput = (val: string) => {
    setTicker(val.toUpperCase());
    if (val.length >= 1) {
      const matches = data.tickers.filter((t) =>
        t.toUpperCase().startsWith(val.toUpperCase()),
      ).slice(0, 8);
      setSuggestions(matches);
    } else {
      setSuggestions([]);
    }
  };

  const selectTicker = (t: string) => {
    setTicker(t);
    setSuggestions([]);
    dispatch({ type: 'SET_PEER_VAL_TICKER', payload: t });
  };

  const runValuation = useCallback(async () => {
    const target = state.peerValTicker || ticker;
    if (!target || !data.tickers.includes(target)) return;

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'SET_PEER_VAL_LOADING', payload: true });
    dispatch({ type: 'SET_PEER_VAL_RESULTS', payload: null });
    dispatch({ type: 'SET_PEER_VAL_ERROR', payload: null });

    try {
      const fm = data.fm[target];
      const di = data.dates.length - 1;
      const rg = fm?.rg?.[di];
      const xg = fm?.xg?.[di];

      const result = await fetchPeerValuation({
        ticker: target,
        revenue_growth: rg ?? 0.1,
        eps_growth: xg ?? 0.1,
        top_k_peers: 20,
        dcf_discount_rate: state.dcfDiscountRate,
        dcf_terminal_growth: state.dcfTerminalGrowth,
        dcf_fade_period: state.dcfFadePeriod,
      });

      if (controller.signal.aborted) return;
      dispatch({ type: 'SET_PEER_VAL_RESULTS', payload: result });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      dispatch({
        type: 'SET_PEER_VAL_ERROR',
        payload: err instanceof Error ? err.message : 'Peer valuation failed',
      });
    } finally {
      dispatch({ type: 'SET_PEER_VAL_LOADING', payload: false });
    }
  }, [state.peerValTicker, ticker, data, dispatch, state.dcfDiscountRate, state.dcfTerminalGrowth, state.dcfFadePeriod]);

  const result = state.peerValResults;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <div className="font-bold" style={{ fontSize: '14px', letterSpacing: '-0.2px' }}>
            Peer-Based Valuation
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>
            Similarity search + index regression composite
          </div>
        </div>
      </div>

      {/* Target Ticker Selector */}
      <div
        className="rounded-xl p-4 mb-4"
        style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
      >
        <label
          className="block mb-1 font-bold uppercase"
          style={{ fontSize: '9.5px', color: 'var(--t3)', letterSpacing: '1px' }}
        >
          Target Ticker
        </label>
        <div className="flex gap-2 items-center">
          <div className="relative flex-1" style={{ maxWidth: '200px' }}>
            <input
              type="text"
              value={ticker}
              onChange={(e) => handleTickerInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  selectTicker(ticker);
                  runValuation();
                }
              }}
              placeholder="e.g. AAPL"
              className="w-full px-3 py-1.5 rounded outline-none"
              style={{
                background: 'var(--bg0)',
                border: '1px solid var(--brd)',
                color: 'var(--t1)',
                fontSize: '12px',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            />
            {suggestions.length > 0 && (
              <div
                className="absolute z-10 w-full rounded shadow-lg mt-0.5"
                style={{ background: 'var(--bg1)', border: '1px solid var(--brd)' }}
              >
                {suggestions.map((s) => (
                  <div
                    key={s}
                    onClick={() => selectTicker(s)}
                    className="px-3 py-1 cursor-pointer hover:opacity-80"
                    style={{
                      fontSize: '11px',
                      color: 'var(--t1)',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {s}
                    {data.industries[s] && (
                      <span style={{ color: 'var(--t3)', marginLeft: '8px', fontSize: '9px' }}>
                        {data.industries[s]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={runValuation}
            disabled={state.peerValLoading || !data.tickers.includes(ticker)}
            className="px-3 py-1.5 rounded text-xs font-semibold cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: 'var(--blue)', color: '#fff' }}
          >
            {state.peerValLoading ? 'Running...' : 'Run Valuation'}
          </button>
        </div>
        {state.peerValError && (
          <p className="text-xs mt-2" style={{ color: '#ef4444' }}>
            {state.peerValError}
          </p>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <SimilarCompaniesCard data={data} peers={result.similar_tickers} peerCount={result.peer_count} />
          {result.index_regressions.length > 0 && (
            <IndexRegressionsCard regressions={result.index_regressions} />
          )}
          <CompositeValuationCard ticker={result.ticker} items={result.composite_valuation} historicalItems={result.historical_composite_valuation} />
          <PeerStatsCard stats={result.peer_stats} />
        </div>
      )}
    </div>
  );
}


function SimilarCompaniesCard({ data, peers, peerCount }: {
  data: DashboardData;
  peers: PeerSearchResult[];
  peerCount: number;
}) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
      <div className="font-bold uppercase mb-2" style={{ fontSize: '9.5px', color: 'var(--t3)', letterSpacing: '1px' }}>
        Similar Companies ({peerCount} peers)
      </div>
      <div className="grid gap-1.5" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
        {peers.slice(0, 15).map((peer) => (
          <div key={peer.ticker} className="rounded p-2" style={{ background: 'var(--bg0)', fontSize: '10px' }}>
            <div className="flex items-center gap-1.5">
              <span className="font-bold" style={{ color: 'var(--t1)', fontFamily: "'JetBrains Mono', monospace", fontSize: '10.5px' }}>
                {peer.ticker}
              </span>
              <span className="px-1 py-0.5 rounded font-semibold" style={{ fontSize: '8px', background: 'rgba(16,185,129,.15)', color: '#10b981', fontFamily: "'JetBrains Mono', monospace" }}>
                {(peer.score * 100).toFixed(0)}%
              </span>
              {data.indices?.[peer.ticker]?.map((idx) => (
                <span key={idx} className="px-1 py-0.5 rounded" style={{ fontSize: '7.5px', background: 'rgba(245,158,11,.12)', color: '#f59e0b', fontWeight: 600 }}>
                  {idx}
                </span>
              ))}
            </div>
            {peer.description && (
              <p className="mt-0.5 line-clamp-2" style={{ color: 'var(--t3)', fontSize: '8.5px', lineHeight: '1.2' }}>
                {peer.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


function IndexRegressionsCard({ regressions }: { regressions: IndexRegressionResult[] }) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
      <div className="font-bold uppercase mb-2" style={{ fontSize: '9.5px', color: 'var(--t3)', letterSpacing: '1px' }}>
        Index Regressions
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
        {regressions.map((ir) => (
          <div key={ir.index_name} className="rounded p-3" style={{ background: 'var(--bg0)', border: '1px solid var(--brd)' }}>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-bold" style={{ fontSize: '12px', color: 'var(--t1)' }}>{ir.index_name}</span>
              <span className="px-1.5 py-0.5 rounded" style={{ fontSize: '8.5px', background: 'rgba(245,158,11,.12)', color: '#f59e0b', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                {ir.peer_count_in_index} peers / {ir.total_index_tickers} total
              </span>
            </div>
            {ir.regressions.map((reg) => {
              if (!reg.regression) return null;
              const col = COLORS[reg.metric_type as keyof typeof COLORS];
              return (
                <div key={reg.metric_type} className="mb-1.5">
                  <div className="flex items-center justify-between">
                    <span style={{ fontSize: '9.5px', color: 'var(--t2)' }}>{reg.metric_label}</span>
                    <div className="text-right">
                      {reg.implied_multiple !== null && (
                        <span className="font-bold" style={{ fontSize: '11px', color: col?.m ?? 'var(--t1)', fontFamily: "'JetBrains Mono', monospace" }}>
                          {reg.implied_multiple.toFixed(2)}x
                        </span>
                      )}
                      {reg.historical_implied_multiple !== null && (
                        <span className="ml-2" style={{ fontSize: '9px', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
                          hist {reg.historical_implied_multiple.toFixed(2)}x
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3 mt-0.5" style={{ fontSize: '8.5px', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
                    <span>R²={reg.regression.r2.toFixed(3)}</span>
                    <span>n={reg.regression.n}</span>
                    {reg.historical && (
                      <>
                        <span style={{ color: 'var(--t3)', opacity: 0.7 }}>|</span>
                        <span>hist R²={reg.historical.avg_r2.toFixed(3)}</span>
                        <span>{reg.historical.period_count}p</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}


interface CompositeValuationCardProps {
  ticker: string;
  items: CompositeValuation[];
  historicalItems?: CompositeValuation[];
}

function CompositeValuationCard({ ticker, items, historicalItems }: CompositeValuationCardProps) {
  const histMap = new Map(historicalItems?.map((h) => [h.metric_type, h]));

  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
      <div className="font-bold uppercase mb-2" style={{ fontSize: '9.5px', color: 'var(--t3)', letterSpacing: '1px' }}>
        Composite Valuation — {ticker}
      </div>
      <div className="grid gap-3 grid-cols-1 md:grid-cols-3">
        {items.map((cv) => {
          const col = COLORS[cv.metric_type as keyof typeof COLORS];
          const hist = histMap.get(cv.metric_type);
          return (
            <div key={cv.metric_type} className="rounded p-3 text-center" style={{ background: 'var(--bg0)' }}>
              <label className="block mb-1" style={{ fontSize: '8.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.7px', color: 'var(--t3)' }}>
                {cv.metric_label}
              </label>
              {cv.weighted_implied_multiple !== null ? (
                <>
                  <span className="font-bold block" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '18px', color: col?.m ?? 'var(--t1)' }}>
                    {cv.weighted_implied_multiple.toFixed(2)}x
                  </span>
                  {cv.actual_multiple !== null && (
                    <span className="block mt-0.5" style={{ fontSize: '9px', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
                      Actual: {cv.actual_multiple.toFixed(2)}x
                      {cv.deviation_pct !== null && (
                        <span style={{ color: cv.deviation_pct > 0 ? '#ef4444' : '#10b981', marginLeft: '4px' }}>
                          ({cv.deviation_pct > 0 ? '+' : ''}{cv.deviation_pct.toFixed(1)}%)
                        </span>
                      )}
                    </span>
                  )}
                  {hist?.weighted_implied_multiple != null && (
                    <span className="block mt-1" style={{ fontSize: '9px', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
                      Hist: {hist.weighted_implied_multiple.toFixed(2)}x
                      {hist.deviation_pct != null && (
                        <span style={{ color: hist.deviation_pct > 0 ? '#ef4444' : '#10b981', marginLeft: '4px' }}>
                          ({hist.deviation_pct > 0 ? '+' : ''}{hist.deviation_pct.toFixed(1)}%)
                        </span>
                      )}
                    </span>
                  )}
                  <span className="block mt-0.5" style={{ fontSize: '8px', color: 'var(--t3)' }}>
                    {cv.num_indices} index{cv.num_indices !== 1 ? 'es' : ''}
                  </span>
                </>
              ) : (
                <span style={{ fontSize: '11px', color: 'var(--t3)' }}>N/A</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


function PeerStatsCard({ stats }: { stats: PeerValuationResult['peer_stats'] }) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
      <div className="font-bold uppercase mb-2" style={{ fontSize: '9.5px', color: 'var(--t3)', letterSpacing: '1px' }}>
        Peer Distribution Stats
      </div>
      <div className="grid gap-3 grid-cols-1 md:grid-cols-3">
        {stats.map((ps) => {
          const col = COLORS[ps.metric_type as keyof typeof COLORS];
          return (
            <div key={ps.metric_type} className="rounded p-3" style={{ background: 'var(--bg0)', fontSize: '10px' }}>
              <div className="font-bold mb-1" style={{ color: col?.m ?? 'var(--t1)', fontSize: '10.5px' }}>
                {ps.metric_label}
              </div>
              <div className="grid gap-0.5" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: 'var(--t2)' }}>
                <div className="flex justify-between">
                  <span>Count</span><span>{ps.count}</span>
                </div>
                {ps.mean !== null && (
                  <div className="flex justify-between">
                    <span>Mean</span><span>{ps.mean.toFixed(2)}x</span>
                  </div>
                )}
                {ps.median !== null && (
                  <div className="flex justify-between">
                    <span>Median</span><span>{ps.median.toFixed(2)}x</span>
                  </div>
                )}
                {ps.p25 !== null && ps.p75 !== null && (
                  <div className="flex justify-between">
                    <span>IQR</span><span>{ps.p25.toFixed(2)} – {ps.p75.toFixed(2)}x</span>
                  </div>
                )}
                {ps.ticker_percentile !== null && (
                  <div className="flex justify-between">
                    <span>Percentile</span><span>{ps.ticker_percentile.toFixed(0)}th</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
