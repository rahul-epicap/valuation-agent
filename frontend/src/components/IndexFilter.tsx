'use client';

import { DashboardData } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';

interface IndexFilterProps {
  data: DashboardData;
  state: DashboardState;
  allIndices: string[];
  dispatch: React.Dispatch<Action>;
}

export default function IndexFilter({ data, state, allIndices, dispatch }: IndexFilterProps) {
  if (!data.indices || allIndices.length === 0) return null;

  const q = state.idxSrch.toLowerCase();
  const visible = allIndices.filter((idx) => !q || idx.toLowerCase().includes(q));

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
      <div className="flex gap-1 mb-1.5 flex-wrap">
        <span
          className="px-1.5 py-0.5 rounded font-semibold"
          style={{
            fontSize: '9.5px',
            background: 'var(--blue-d)',
            color: 'var(--blue)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {state.idxOn.size} selected
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
          {allIndices.length} total
        </span>
      </div>
      <input
        value={state.idxSrch}
        onChange={(e) => dispatch({ type: 'SET_IDX_SEARCH', payload: e.target.value })}
        placeholder="Search indices…"
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
      <div className="flex flex-wrap gap-1 max-h-56 overflow-y-auto">
        {visible.map((idx) => {
          const active = state.idxOn.has(idx);
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
    </div>
  );
}
