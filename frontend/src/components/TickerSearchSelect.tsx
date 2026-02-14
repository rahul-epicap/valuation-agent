'use client';

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';

interface TickerSearchSelectProps {
  tickers: string[];
  industries: Record<string, string>;
  selected: string | null;
  onSelect: (ticker: string | null) => void;
}

export default function TickerSearchSelect({
  tickers,
  industries,
  selected,
  onSelect,
}: TickerSearchSelectProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    if (!query) return tickers;
    const q = query.toLowerCase();
    return tickers.filter(
      (t) =>
        t.toLowerCase().includes(q) ||
        (industries[t] || '').toLowerCase().includes(q)
    );
  }, [tickers, industries, query]);

  // Clamp activeIdx to valid range (handles filtered list shrinking)
  const clampedIdx = Math.min(activeIdx, Math.max(filtered.length - 1, 0));

  // Scroll active item into view
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.children[clampedIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [clampedIdx, open]);

  const selectTicker = useCallback(
    (t: string) => {
      onSelect(t);
      setQuery('');
      setOpen(false);
      inputRef.current?.blur();
    },
    [onSelect]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        e.preventDefault();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered[clampedIdx]) selectTicker(filtered[clampedIdx]);
        break;
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        inputRef.current?.blur();
        break;
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const root = inputRef.current?.parentElement;
      if (root && !root.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" style={{ minWidth: 220 }}>
      <div className="flex items-center" style={{
        background: 'var(--bg2)',
        border: '1px solid var(--brd)',
        borderRadius: '7px',
      }}>
        <input
          ref={inputRef}
          value={selected && !open ? selected : query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIdx(0);
            if (!open) setOpen(true);
          }}
          onFocus={() => {
            if (selected) setQuery('');
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search ticker..."
          className="flex-1 outline-none bg-transparent"
          style={{
            color: 'var(--t1)',
            padding: '6px 9px',
            fontSize: '11.5px',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        />
        {selected && (
          <button
            onClick={() => {
              onSelect(null);
              setQuery('');
              inputRef.current?.focus();
            }}
            className="px-2 cursor-pointer"
            style={{ color: 'var(--t3)', fontSize: '14px', lineHeight: 1 }}
            aria-label="Clear selection"
          >
            &times;
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <div
          ref={listRef}
          className="absolute z-50 w-full overflow-y-auto rounded-lg mt-1"
          style={{
            maxHeight: 240,
            background: 'var(--bg0)',
            border: '1px solid var(--brd)',
            boxShadow: '0 8px 24px rgba(0,0,0,.4)',
          }}
        >
          {filtered.map((t, i) => (
            <div
              key={t}
              onMouseDown={(e) => {
                e.preventDefault();
                selectTicker(t);
              }}
              onMouseEnter={() => setActiveIdx(i)}
              className="flex items-baseline gap-2 px-3 py-1.5 cursor-pointer"
              style={{
                background: i === clampedIdx ? 'var(--bg2)' : 'transparent',
                fontSize: '11.5px',
              }}
            >
              <span
                className="font-bold"
                style={{
                  color: 'var(--t1)',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {t}
              </span>
              <span style={{ color: 'var(--t3)', fontSize: '10px' }}>
                {industries[t] || ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {open && filtered.length === 0 && query && (
        <div
          className="absolute z-50 w-full rounded-lg mt-1 px-3 py-2"
          style={{
            background: 'var(--bg0)',
            border: '1px solid var(--brd)',
            fontSize: '11px',
            color: 'var(--t3)',
          }}
        >
          No tickers found
        </div>
      )}
    </div>
  );
}
