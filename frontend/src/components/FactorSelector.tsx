'use client';

import { useMemo, useState } from 'react';
import { DashboardData } from '../lib/types';
import { CONTINUOUS_FACTORS } from '../lib/filters';
import { Action, DashboardState } from '../hooks/useDashboardState';

interface FactorSelectorProps {
  data: DashboardData;
  state: DashboardState;
  allIndices: string[];
  dispatch: React.Dispatch<Action>;
}

const PRESETS: Record<string, { label: string; filter: (idx: string) => boolean }> = {
  sector: {
    label: 'Sector',
    filter: (idx) => idx.startsWith('MSXX') && !idx.includes('MAG') && !idx.includes('SAAS'),
  },
  thematic: {
    label: 'Thematic',
    filter: (idx) => idx.includes('SAAS') || idx.includes('MAG') || idx.includes('CLOUD'),
  },
  broad: {
    label: 'Broad',
    filter: (idx) => ['SPX', 'NDX', 'RTY'].includes(idx),
  },
};

export default function FactorSelector({ data, state, allIndices, dispatch }: FactorSelectorProps) {
  const [search, setSearch] = useState('');

  const indexCounts = useMemo(() => {
    if (!data.indices) return {};
    const counts: Record<string, number> = {};
    for (const tickerIndices of Object.values(data.indices)) {
      for (const idx of tickerIndices) {
        counts[idx] = (counts[idx] || 0) + 1;
      }
    }
    return counts;
  }, [data.indices]);

  if (!data.indices || allIndices.length === 0) return null;

  const q = search.toLowerCase();
  const visible = allIndices.filter((idx) => !q || idx.toLowerCase().includes(q));

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <div
          className="font-bold uppercase pl-0.5"
          style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
        >
          Multi-Factor Regression
        </div>
        <button
          onClick={() => dispatch({ type: 'TOGGLE_MF' })}
          className="cursor-pointer select-none"
          style={{
            fontSize: '9px',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '9999px',
            border: 'none',
            background: state.mfEnabled ? '#2563eb' : 'var(--bg2)',
            color: state.mfEnabled ? '#fff' : 'var(--t3)',
            transition: 'all 0.15s',
          }}
        >
          {state.mfEnabled ? 'ON' : 'OFF'}
        </button>
      </div>

      {!state.mfEnabled && (
        <div style={{ fontSize: '9.5px', color: 'var(--t3)', padding: '2px 0' }}>
          Enable to add index dummies as regression factors
        </div>
      )}

      {state.mfEnabled && (
        <>
          <div className="flex gap-1 mb-1.5 flex-wrap">
            <span
              className="px-1.5 py-0.5 rounded font-semibold"
              style={{
                fontSize: '9.5px',
                background: '#2563eb22',
                color: '#2563eb',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {state.regFactors.size} factors
            </span>
            <span
              className="px-1.5 py-0.5 rounded font-semibold"
              style={{
                fontSize: '9.5px',
                background: 'rgba(255,255,255,.04)',
                color: 'var(--t3)',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {allIndices.length} available
            </span>
          </div>

          {/* Quick presets */}
          <div className="flex gap-1 mb-1.5 flex-wrap">
            {Object.entries(PRESETS).map(([key, { label, filter }]) => (
              <button
                key={key}
                onClick={() => {
                  const matching = allIndices.filter(filter);
                  dispatch({ type: 'SET_REG_FACTORS', payload: matching });
                }}
                className="px-2 py-0.5 rounded font-semibold cursor-pointer"
                style={{
                  fontSize: '8.5px',
                  border: '1px solid var(--brd)',
                  background: 'var(--bg2)',
                  color: 'var(--t2)',
                }}
              >
                {label}
              </button>
            ))}
            <button
              onClick={() => dispatch({ type: 'CLEAR_REG_FACTORS' })}
              className="px-2 py-0.5 rounded font-semibold cursor-pointer"
              style={{
                fontSize: '8.5px',
                border: '1px solid var(--brd)',
                background: 'var(--bg2)',
                color: 'var(--t2)',
              }}
            >
              Clear
            </button>
          </div>

          {/* Continuous factors */}
          <div className="flex gap-1 mb-1.5 flex-wrap">
            <span style={{ fontSize: '8.5px', color: 'var(--t3)', fontWeight: 600 }}>
              Continuous:
            </span>
            {Object.entries(CONTINUOUS_FACTORS).map(([key, label]) => {
              const active = state.regFactors.has(key);
              return (
                <div
                  key={key}
                  onClick={() => dispatch({ type: 'TOGGLE_REG_FACTOR', payload: key })}
                  className="cursor-pointer select-none transition-all"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: active ? 600 : 500,
                    border: `1px solid ${active ? '#10b981' : 'var(--brd)'}`,
                    background: active ? '#10b981' : 'var(--bg2)',
                    color: active ? '#fff' : 'var(--t2)',
                  }}
                >
                  {label}
                </div>
              );
            })}
          </div>

          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search indices..."
            className="w-full mb-1.5 outline-none"
            style={{
              background: 'var(--bg2)',
              border: '1px solid var(--brd)',
              color: 'var(--t1)',
              padding: '6px 9px',
              borderRadius: '7px',
              fontSize: '11.5px',
            }}
          />

          <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
            {visible.map((idx) => {
              const active = state.regFactors.has(idx);
              const count = indexCounts[idx] || 0;
              return (
                <div
                  key={idx}
                  onClick={() => dispatch({ type: 'TOGGLE_REG_FACTOR', payload: idx })}
                  className="cursor-pointer select-none transition-all"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: active ? 600 : 500,
                    border: `1px solid ${active ? '#8b5cf6' : 'var(--brd)'}`,
                    background: active ? '#8b5cf6' : 'var(--bg2)',
                    color: active ? '#fff' : 'var(--t2)',
                  }}
                >
                  {idx}
                  <span
                    style={{
                      fontSize: '8.5px',
                      opacity: 0.7,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {count}
                    {count > 0 && count < 10 && (
                      <span style={{ color: active ? '#fcd34d' : '#f59e0b', marginLeft: '2px' }}>!</span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>

          {state.regFactors.size > 0 && (
            <div className="mt-1.5 flex gap-1 flex-wrap">
              <span style={{ fontSize: '8.5px', color: 'var(--t3)', fontWeight: 600 }}>
                Active:
              </span>
              {[...state.regFactors].map((name) => (
                <span
                  key={name}
                  className="px-1.5 py-0.5 rounded font-semibold"
                  style={{
                    fontSize: '8.5px',
                    background: 'rgba(139,92,246,.12)',
                    color: '#8b5cf6',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {name}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
