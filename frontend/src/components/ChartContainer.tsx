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

interface MonthEntry {
  key: string;       // "YYYY-MM"
  label: string;     // "MMM YYYY"
  firstDi: number;   // first date index in this month
  lastDi: number;    // last date index in this month
}

export default function ChartContainer({ dates, children }: ChartContainerProps) {
  const [fullscreen, setFullscreen] = useState(false);

  // Build unique month list from dates
  const months = useMemo(() => {
    const result: MonthEntry[] = [];
    for (let i = 0; i < dates.length; i++) {
      const key = dates[i].slice(0, 7); // "YYYY-MM"
      if (result.length === 0 || result[result.length - 1].key !== key) {
        result.push({ key, label: formatDate(dates[i]), firstDi: i, lastDi: i });
      } else {
        result[result.length - 1].lastDi = i;
      }
    }
    return result;
  }, [dates]);

  const [rawStartMi, setStartMi] = useState(0);
  const [rawEndMi, setEndMi] = useState(months.length - 1);

  // Clamp to valid range without setState in effect
  const maxMi = months.length - 1;
  const startMi = useMemo(() => Math.min(rawStartMi, maxMi - 1), [rawStartMi, maxMi]);
  const endMi = useMemo(() => Math.max(Math.min(rawEndMi, maxMi), startMi), [rawEndMi, maxMi, startMi]);

  // Derive date indices from selected months
  const startDi = months[startMi]?.firstDi ?? 0;
  const endDi = months[endMi]?.lastDi ?? dates.length - 1;

  const isNarrowed = startMi !== 0 || endMi !== maxMi;

  const handleReset = () => {
    setStartMi(0);
    setEndMi(maxMi);
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
        value={startMi}
        onChange={(e) => {
          const v = Number(e.target.value);
          setStartMi(v);
          if (v >= endMi) setEndMi(Math.min(v + 1, maxMi));
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
        {months.map((m, i) => (
          <option key={m.key} value={i}>
            {m.label}
          </option>
        ))}
      </select>

      <label style={{ color: 'var(--t3)' }}>To</label>
      <select
        value={endMi}
        onChange={(e) => {
          const v = Number(e.target.value);
          setEndMi(v);
          if (v <= startMi) setStartMi(Math.max(v - 1, 0));
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
        {months.map((m, i) => (
          <option key={m.key} value={i}>
            {m.label}
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
          <div className="flex-1 min-h-0 flex flex-col [&>div]:flex-1 [&>div]:flex [&>div]:flex-col [&>div]:min-h-0">
            {children({ startDi, endDi, chartHeight: 0 })}
          </div>
        </div>
      </div>
    );
  }

  // Use smaller chart height on mobile
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const defaultHeight = isMobile ? 240 : 320;

  return (
    <div>
      {toolbar}
      {children({ startDi, endDi, chartHeight: defaultHeight })}
    </div>
  );
}
