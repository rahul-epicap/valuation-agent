'use client';

import { DashboardData } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';

interface TickerExclusionsProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function TickerExclusions({ data, state, dispatch }: TickerExclusionsProps) {
  const q = state.exSrch.toLowerCase();
  const visible = data.tickers.filter((t) => !q || t.toLowerCase().includes(q));
  const total = data.tickers.length;
  const excluded = state.exTk.size;

  const handleExcludeVisible = () => {
    dispatch({ type: 'EXCLUDE_VISIBLE', payload: visible });
  };

  return (
    <div className="mb-4">
      <div
        className="font-bold uppercase mb-1.5 pl-0.5"
        style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
      >
        Ticker Exclusions
      </div>
      <div className="flex gap-1 mb-1.5 flex-wrap">
        <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'var(--blue-d)', color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>
          {total - excluded} active
        </span>
        {excluded > 0 && (
          <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'var(--red-d)', color: 'var(--red)', fontFamily: "'JetBrains Mono', monospace" }}>
            {excluded} excluded
          </span>
        )}
        <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'rgba(255,255,255,.04)', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
          {total} total
        </span>
      </div>
      <input
        value={state.exSrch}
        onChange={(e) => dispatch({ type: 'SET_EX_SEARCH', payload: e.target.value })}
        placeholder="Search to exclude…"
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
          onClick={() => dispatch({ type: 'CLEAR_EXCLUSIONS' })}
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{ fontSize: '9.5px', border: '1px solid var(--brd)', background: 'var(--bg2)', color: 'var(--t2)' }}
        >
          Include All
        </button>
        <button
          onClick={handleExcludeVisible}
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{ fontSize: '9.5px', border: '1px solid var(--brd)', background: 'var(--bg2)', color: 'var(--t2)' }}
        >
          Exclude Visible
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-56 overflow-y-auto">
        {visible.map((tk) => {
          const ex = state.exTk.has(tk);
          return (
            <div
              key={tk}
              onClick={() => dispatch({ type: 'TOGGLE_EXCLUSION', payload: tk })}
              className="cursor-pointer select-none transition-all"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                padding: '2px 6px',
                borderRadius: '3px',
                fontSize: '10px',
                fontWeight: ex ? 600 : 500,
                border: `1px solid ${ex ? 'var(--red)' : 'var(--brd)'}`,
                background: ex ? 'var(--red-d)' : 'var(--bg2)',
                color: ex ? 'var(--red)' : 'var(--t2)',
                textDecoration: ex ? 'line-through' : 'none',
              }}
            >
              {tk}
              <span style={{ fontSize: '8.5px', color: ex ? 'var(--red)' : 'var(--t3)', opacity: ex ? 0.6 : 1 }}>
                {data.industries[tk] || ''}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
