'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';

interface ChartContainerProps {
  dates: string[];
  children: (props: { startDi: number; endDi: number; chartHeight: number }) => React.ReactNode;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

export default function ChartContainer({ dates, children }: ChartContainerProps) {
  const [fullscreen, setFullscreen] = useState(false);
  const [rawStartDi, setStartDi] = useState(0);
  const [rawEndDi, setEndDi] = useState(dates.length - 1);

  // Clamp to valid range without setState in effect
  const maxDi = dates.length - 1;
  const startDi = useMemo(() => Math.min(rawStartDi, maxDi - 1), [rawStartDi, maxDi]);
  const endDi = useMemo(() => Math.max(Math.min(rawEndDi, maxDi), startDi), [rawEndDi, maxDi, startDi]);

  const isNarrowed = startDi !== 0 || endDi !== maxDi;

  const handleReset = () => {
    setStartDi(0);
    setEndDi(maxDi);
  };

  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && fullscreen) setFullscreen(false);
    },
    [fullscreen]
  );

  useEffect(() => {
    if (fullscreen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [fullscreen, handleEscape]);

  const toolbar = (
    <div className="flex items-center gap-2 mb-2 flex-wrap" style={{ fontSize: '11px' }}>
      <label style={{ color: 'var(--t3)' }}>From</label>
      <select
        value={startDi}
        onChange={(e) => {
          const v = Number(e.target.value);
          setStartDi(v);
          if (v >= endDi) setEndDi(Math.min(v + 1, maxDi));
        }}
        className="outline-none rounded cursor-pointer"
        style={{
          background: 'var(--bg0)',
          border: '1px solid var(--brd)',
          color: 'var(--t1)',
          padding: '2px 6px',
          fontSize: '10.5px',
        }}
      >
        {dates.map((d, i) => (
          <option key={i} value={i}>
            {formatDate(d)}
          </option>
        ))}
      </select>

      <label style={{ color: 'var(--t3)' }}>To</label>
      <select
        value={endDi}
        onChange={(e) => {
          const v = Number(e.target.value);
          setEndDi(v);
          if (v <= startDi) setStartDi(Math.max(v - 1, 0));
        }}
        className="outline-none rounded cursor-pointer"
        style={{
          background: 'var(--bg0)',
          border: '1px solid var(--brd)',
          color: 'var(--t1)',
          padding: '2px 6px',
          fontSize: '10.5px',
        }}
      >
        {dates.map((d, i) => (
          <option key={i} value={i}>
            {formatDate(d)}
          </option>
        ))}
      </select>

      {isNarrowed && (
        <button
          onClick={handleReset}
          className="rounded cursor-pointer"
          style={{
            background: 'var(--bg3)',
            border: '1px solid var(--brd)',
            color: 'var(--t2)',
            padding: '2px 8px',
            fontSize: '10px',
            fontWeight: 600,
          }}
        >
          Reset
        </button>
      )}

      <button
        onClick={() => setFullscreen((f) => !f)}
        className="ml-auto rounded cursor-pointer"
        style={{
          background: 'var(--bg3)',
          border: '1px solid var(--brd)',
          color: 'var(--t2)',
          padding: '2px 6px',
          lineHeight: 1,
        }}
        title={fullscreen ? 'Exit fullscreen' : 'Expand chart'}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {fullscreen ? (
            <>
              <polyline points="4 14 10 14 10 20" />
              <polyline points="20 10 14 10 14 4" />
              <line x1="14" y1="10" x2="21" y2="3" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </>
          ) : (
            <>
              <polyline points="15 3 21 3 21 9" />
              <polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </>
          )}
        </svg>
      </button>
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,.6)' }}>
        <div
          className="flex-1 m-4 rounded-xl p-4 flex flex-col overflow-hidden"
          style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
        >
          <div className="flex items-center justify-between mb-1">
            <div className="flex-1">{toolbar}</div>
            <button
              onClick={() => setFullscreen(false)}
              className="text-lg cursor-pointer ml-3"
              style={{ color: 'var(--t3)', lineHeight: 1 }}
            >
              &times;
            </button>
          </div>
          <div className="flex-1 min-h-0">
            {children({ startDi, endDi, chartHeight: 0 })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {toolbar}
      {children({ startDi, endDi, chartHeight: 320 })}
    </div>
  );
}
