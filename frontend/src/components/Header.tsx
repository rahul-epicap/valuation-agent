'use client';

import { DashboardData, SnapshotMeta } from '../lib/types';
import { DashboardState } from '../hooks/useDashboardState';

interface HeaderProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
  snapshots: SnapshotMeta[];
  activeSnapshotId?: number;
  onSnapshotChange: (id: number) => void;
  onUploadClick: () => void;
}

export default function Header({
  data,
  state,
  dispatch,
  snapshots,
  activeSnapshotId,
  onSnapshotChange,
  onUploadClick,
}: HeaderProps) {
  return (
    <header
      className="px-6 py-4 flex items-center justify-between flex-wrap gap-2.5"
      style={{
        borderBottom: '1px solid var(--brd)',
        background: 'linear-gradient(180deg, rgba(59,130,246,.03), transparent)',
      }}
    >
      <div>
        <h1 className="text-lg font-bold" style={{ letterSpacing: '-0.4px' }}>
          <span style={{ color: 'var(--blue)', fontWeight: 700 }}>Epicenter</span> Valuation Dashboard
        </h1>
        <p className="mt-0.5" style={{ color: 'var(--t3)', fontSize: '10.5px' }}>
          Regression Analysis · {data.tickers.length} Tickers · {data.dates[0]?.slice(0, 4)}–{data.dates[data.dates.length - 1]?.slice(0, 4)}
        </p>
      </div>
      <div className="flex items-center gap-2.5 flex-wrap">
        {/* EPS Cap Toggle */}
        <div className="flex items-center gap-1.5" style={{ fontSize: '11px', color: 'var(--t2)' }}>
          <label className="cursor-pointer select-none flex items-center gap-1.5">
            <span className="relative inline-block" style={{ width: 34, height: 18 }}>
              <input
                type="checkbox"
                checked={state.epsCap}
                onChange={(e) => dispatch({ type: 'SET_EPS_CAP', payload: e.target.checked })}
                className="opacity-0 w-0 h-0 absolute"
              />
              <span
                className="absolute inset-0 rounded-full transition-colors duration-200"
                style={{
                  background: state.epsCap ? 'var(--amber)' : 'var(--bg3)',
                  border: `1px solid ${state.epsCap ? 'var(--amber)' : 'var(--brd)'}`,
                }}
              >
                <span
                  className="absolute rounded-full transition-transform duration-200"
                  style={{
                    height: 12,
                    width: 12,
                    left: 2,
                    bottom: 2,
                    background: state.epsCap ? '#fff' : 'var(--t3)',
                    transform: state.epsCap ? 'translateX(16px)' : 'translateX(0)',
                  }}
                />
              </span>
            </span>
            Cap EPS Growth &gt;150%
          </label>
        </div>

        {/* Date Selector */}
        <select
          value={state.di}
          onChange={(e) => dispatch({ type: 'SET_DATE', payload: Number(e.target.value) })}
          className="outline-none cursor-pointer"
          style={{
            background: 'var(--bg2)',
            border: '1px solid var(--brd)',
            color: 'var(--t1)',
            padding: '6px 10px',
            borderRadius: '7px',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '11.5px',
          }}
        >
          {data.dates.map((d, i) => (
            <option key={i} value={i}>{d}</option>
          ))}
        </select>

        {/* Snapshot Selector */}
        {snapshots.length > 1 && (
          <select
            value={activeSnapshotId}
            onChange={(e) => onSnapshotChange(Number(e.target.value))}
            className="outline-none cursor-pointer"
            style={{
              background: 'var(--bg2)',
              border: '1px solid var(--brd)',
              color: 'var(--t1)',
              padding: '6px 10px',
              borderRadius: '7px',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11.5px',
            }}
          >
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        )}

        {/* Upload Button */}
        <button
          onClick={onUploadClick}
          className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer"
          style={{ background: 'var(--blue)', color: '#fff' }}
        >
          Upload Data
        </button>
      </div>
    </header>
  );
}
