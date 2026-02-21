'use client';

import { DashboardData } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';

interface TickerHighlightProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function TickerHighlight({ data, state, dispatch }: TickerHighlightProps) {
  const q = state.hlSrch.toLowerCase();
  const visible = data.tickers.filter((t) => !q || t.toLowerCase().includes(q));

  return (
    <div className="mb-4">
      <div
        className="font-bold uppercase mb-1.5 pl-0.5"
        style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
      >
        Highlight Tickers
      </div>
      <div className="flex gap-1 mb-1.5 flex-wrap">
        {state.hlTk.size > 0 ? (
          <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'var(--amber-d)', color: 'var(--amber)', fontFamily: "'JetBrains Mono', monospace" }}>
            {state.hlTk.size} highlighted
          </span>
        ) : (
          <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'rgba(255,255,255,.04)', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
            none highlighted
          </span>
        )}
      </div>
      <input
        value={state.hlSrch}
        onChange={(e) => dispatch({ type: 'SET_HL_SEARCH', payload: e.target.value })}
        placeholder="Search to highlight…"
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
          onClick={() => dispatch({ type: 'CLEAR_HIGHLIGHTS' })}
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{ fontSize: '9.5px', border: '1px solid var(--brd)', background: 'var(--bg2)', color: 'var(--t2)' }}
        >
          Clear Highlights
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-56 overflow-y-auto">
        {visible.map((tk) => {
          if (state.exTk.has(tk)) return null;
          const hl = state.hlTk.has(tk);
          return (
            <div
              key={tk}
              onClick={() => dispatch({ type: 'TOGGLE_HIGHLIGHT', payload: tk })}
              className="cursor-pointer select-none transition-all"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                padding: '2px 6px',
                borderRadius: '3px',
                fontSize: '10px',
                fontWeight: hl ? 700 : 500,
                border: `1px solid ${hl ? 'var(--amber)' : 'var(--brd)'}`,
                background: hl ? 'var(--amber-d)' : 'var(--bg2)',
                color: hl ? 'var(--amber)' : 'var(--t2)',
                boxShadow: hl ? '0 0 0 1px var(--amber)' : 'none',
              }}
            >
              {tk}
              <span style={{ fontSize: '8.5px', color: hl ? 'var(--amber)' : 'var(--t3)', opacity: hl ? 0.7 : 1 }}>
                {data.industries[tk] || ''}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
