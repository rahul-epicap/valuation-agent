'use client';

import { DashboardData, SnapshotMeta } from '../lib/types';
import { Action, DashboardState, ViewMode } from '../hooks/useDashboardState';
import DatePicker from './DatePicker';

interface HeaderProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
  snapshots: SnapshotMeta[];
  activeSnapshotId?: number;
  onSnapshotChange: (id: number) => void;
  onUploadClick: () => void;
  onUpdateClick: () => void;
  updating: boolean;
  onMenuToggle: () => void;
}

export default function Header({
  data,
  state,
  dispatch,
  snapshots,
  activeSnapshotId,
  onSnapshotChange,
  onUploadClick,
  onUpdateClick,
  updating,
  onMenuToggle,
}: HeaderProps) {
  return (
    <header
      className="px-3 md:px-6 py-2 md:py-4 flex items-center justify-between flex-wrap gap-2 md:gap-2.5"
      style={{
        borderBottom: '1px solid var(--brd)',
        background: 'linear-gradient(180deg, rgba(59,130,246,.03), transparent)',
      }}
    >
      <div className="flex items-center gap-2">
        {/* Mobile hamburger menu */}
        <button
          onClick={onMenuToggle}
          className="md:hidden p-1.5 rounded cursor-pointer"
          style={{ color: 'var(--t2)', background: 'var(--bg2)', border: '1px solid var(--brd)' }}
          aria-label="Toggle filters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div>
          <h1 className="text-sm md:text-lg font-bold" style={{ letterSpacing: '-0.4px' }}>
            <span style={{ color: 'var(--blue)', fontWeight: 700 }}>Epicenter</span>{' '}
            <span className="hidden sm:inline">Valuation Dashboard</span>
            <span className="sm:hidden">VD</span>
          </h1>
          <p className="mt-0.5 hidden sm:block" style={{ color: 'var(--t3)', fontSize: '10.5px' }}>
            Regression Analysis · {data.tickers.length} Tickers · {data.dates[0]?.slice(0, 4)}–{data.dates[data.dates.length - 1]?.slice(0, 4)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1.5 md:gap-2.5 flex-wrap">
        {/* View Toggle */}
        <ViewToggle
          active={state.view}
          onChange={(v) => dispatch({ type: 'SET_VIEW', payload: v })}
        />

        {/* Date Picker */}
        <DatePicker
          dates={data.dates}
          selectedIndex={state.di}
          onSelect={(i) => dispatch({ type: 'SET_DATE', payload: i })}
        />

        {/* Snapshot Selector */}
        {snapshots.length > 1 && (
          <select
            value={activeSnapshotId}
            onChange={(e) => onSnapshotChange(Number(e.target.value))}
            className="outline-none cursor-pointer hidden sm:block"
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

        {/* Update Button */}
        <button
          onClick={onUpdateClick}
          disabled={updating}
          className="text-xs font-semibold px-2 md:px-3 py-1.5 rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ background: 'var(--green)', color: '#fff' }}
        >
          {updating ? '…' : <><span className="hidden sm:inline">Update Data</span><span className="sm:hidden">Update</span></>}
        </button>

        {/* Upload Button */}
        <button
          onClick={onUploadClick}
          className="text-xs font-semibold px-2 md:px-3 py-1.5 rounded cursor-pointer"
          style={{ background: 'var(--blue)', color: '#fff' }}
        >
          <span className="hidden sm:inline">Upload Data</span>
          <span className="sm:hidden">Upload</span>
        </button>
      </div>
    </header>
  );
}

const VIEW_OPTIONS: { key: ViewMode; label: string }[] = [
  { key: 'charts', label: 'Charts' },
  { key: 'regression', label: 'Regression' },
  { key: 'dcf', label: 'DCF' },
  { key: 'peers', label: 'Peers' },
];

function ViewToggle({ active, onChange }: { active: ViewMode; onChange: (v: ViewMode) => void }) {
  return (
    <div className="flex gap-0.5 rounded p-0.5" style={{ background: 'var(--bg0)' }}>
      {VIEW_OPTIONS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-2.5 py-1 rounded text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
            active === key ? 'bg-blue-500 text-white' : ''
          }`}
          style={active !== key ? { color: 'var(--t3)', background: 'transparent' } : {}}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
