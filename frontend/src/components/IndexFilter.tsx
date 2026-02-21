'use client';

import { DashboardData } from '../lib/types';
import { Action, IndexFilterMode } from '../hooks/useDashboardState';

interface IndexFilterProps {
  data: DashboardData;
  activeIndices: Set<string>;
  indexFilterMode: IndexFilterMode;
  allIndices: string[];
  dispatch: React.Dispatch<Action>;
}

export default function IndexFilter({
  data,
  activeIndices,
  indexFilterMode,
  allIndices,
  dispatch,
}: IndexFilterProps) {
  if (!data.indices || allIndices.length === 0) return null;

  // Count tickers per index
  const indexCounts: Record<string, number> = {};
  for (const tickerIndices of Object.values(data.indices)) {
    for (const idx of tickerIndices) {
      indexCounts[idx] = (indexCounts[idx] || 0) + 1;
    }
  }

  return (
    <div className="mb-4">
      <div
        className="font-bold uppercase mb-1.5 pl-0.5"
        style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
      >
        Index Filter
      </div>
      <div className="flex gap-1 mb-1.5 items-center">
        <button
          onClick={() =>
            dispatch({
              type: 'SET_INDEX_FILTER_MODE',
              payload: indexFilterMode === 'on' ? 'off' : 'on',
            })
          }
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{
            fontSize: '9.5px',
            border: `1px solid ${indexFilterMode === 'on' ? '#2563eb' : 'var(--brd)'}`,
            background: indexFilterMode === 'on' ? '#2563eb' : 'var(--bg2)',
            color: indexFilterMode === 'on' ? '#fff' : 'var(--t2)',
          }}
        >
          {indexFilterMode === 'on' ? 'ON' : 'OFF'}
        </button>
        <span
          className="px-1.5 py-0.5 rounded font-semibold"
          style={{
            fontSize: '9.5px',
            background: 'var(--blue-d)',
            color: 'var(--blue)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {activeIndices.size} selected
        </span>
      </div>
      {indexFilterMode === 'on' && (
        <>
          <div className="flex gap-1 mb-1.5">
            <button
              onClick={() => dispatch({ type: 'SELECT_ALL_INDICES', payload: allIndices })}
              className="px-2 py-1 rounded font-semibold cursor-pointer"
              style={{
                fontSize: '9.5px',
                border: '1px solid var(--brd)',
                background: 'var(--bg2)',
                color: 'var(--t2)',
              }}
            >
              Select All
            </button>
            <button
              onClick={() => dispatch({ type: 'CLEAR_ALL_INDICES' })}
              className="px-2 py-1 rounded font-semibold cursor-pointer"
              style={{
                fontSize: '9.5px',
                border: '1px solid var(--brd)',
                background: 'var(--bg2)',
                color: 'var(--t2)',
              }}
            >
              Clear All
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            {allIndices.map((idx) => {
              const active = activeIndices.has(idx);
              return (
                <div
                  key={idx}
                  onClick={() => dispatch({ type: 'TOGGLE_INDEX', payload: idx })}
                  className="cursor-pointer select-none transition-all"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: active ? 600 : 500,
                    border: `1px solid ${active ? '#2563eb' : 'var(--brd)'}`,
                    background: active ? '#2563eb' : 'var(--bg2)',
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
                    {indexCounts[idx] || 0}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
