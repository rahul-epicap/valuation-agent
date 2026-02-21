'use client';

import { useEffect, useRef, useCallback } from 'react';
import { DashboardData, PeerSearchResult } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import { searchPeers } from '../lib/api';

interface PeerSearchPanelProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function PeerSearchPanel({ data, state, dispatch }: PeerSearchPanelProps) {
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback(
    async (query: string) => {
      if (abortRef.current) {
        abortRef.current.abort();
      }

      if (!query.trim()) {
        dispatch({ type: 'SET_PEER_RESULTS', payload: [] });
        dispatch({ type: 'SET_PEER_ERROR', payload: null });
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: 'SET_PEER_LOADING', payload: true });
      dispatch({ type: 'SET_PEER_ERROR', payload: null });

      try {
        // Determine if query is a ticker or free text
        const isTicker = data.tickers.includes(query.toUpperCase().trim());
        const params = isTicker
          ? { ticker: query.toUpperCase().trim(), top_k: 20 }
          : { text: query.trim(), top_k: 20 };

        const response = await searchPeers(params, controller.signal);
        dispatch({ type: 'SET_PEER_RESULTS', payload: response.results });
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return;
        dispatch({
          type: 'SET_PEER_ERROR',
          payload: err instanceof Error ? err.message : 'Search failed',
        });
      } finally {
        dispatch({ type: 'SET_PEER_LOADING', payload: false });
      }
    },
    [data.tickers, dispatch],
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(state.peerQuery), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [state.peerQuery, doSearch]);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const handleTickerClick = (ticker: string) => {
    dispatch({ type: 'TOGGLE_HIGHLIGHT', payload: ticker });
  };

  return (
    <div className="mb-4">
      <div
        className="font-bold uppercase mb-1.5 pl-0.5"
        style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
      >
        Peer Search
      </div>
      <input
        type="text"
        value={state.peerQuery}
        onChange={(e) => dispatch({ type: 'SET_PEER_QUERY', payload: e.target.value })}
        placeholder="Search by ticker or description..."
        className="w-full px-2 py-1.5 rounded mb-1.5 outline-none"
        style={{
          background: 'var(--bg2)',
          border: '1px solid var(--brd)',
          color: 'var(--t1)',
          fontSize: '11px',
          fontFamily: "'JetBrains Mono', monospace",
        }}
      />
      {state.peerLoading && (
        <p className="text-xs animate-pulse" style={{ color: 'var(--t3)' }}>
          Searching...
        </p>
      )}
      {state.peerError && (
        <p className="text-xs" style={{ color: '#ef4444' }}>
          {state.peerError}
        </p>
      )}
      {state.peerResults.length > 0 && (
        <div className="max-h-72 overflow-y-auto space-y-1">
          {state.peerResults.map((peer: PeerSearchResult) => (
            <div
              key={peer.ticker}
              onClick={() => handleTickerClick(peer.ticker)}
              className="cursor-pointer rounded p-1.5 transition-all hover:opacity-80"
              style={{
                background: state.hlTk.has(peer.ticker) ? 'rgba(59,130,246,.15)' : 'var(--bg0)',
                border: `1px solid ${state.hlTk.has(peer.ticker) ? '#2563eb' : 'transparent'}`,
              }}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="font-bold"
                  style={{
                    fontSize: '10.5px',
                    color: 'var(--t1)',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {peer.ticker}
                </span>
                <span
                  className="px-1 py-0.5 rounded font-semibold"
                  style={{
                    fontSize: '8.5px',
                    background: 'rgba(16,185,129,.15)',
                    color: '#10b981',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {(peer.score * 100).toFixed(0)}%
                </span>
                {data.indices?.[peer.ticker]?.map((idx) => (
                  <span
                    key={idx}
                    className="px-1 py-0.5 rounded"
                    style={{
                      fontSize: '8px',
                      background: 'rgba(245,158,11,.12)',
                      color: '#f59e0b',
                      fontWeight: 600,
                    }}
                  >
                    {idx}
                  </span>
                ))}
              </div>
              {peer.description && (
                <p
                  className="mt-0.5 line-clamp-2"
                  style={{ fontSize: '9px', color: 'var(--t3)', lineHeight: '1.3' }}
                >
                  {peer.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
