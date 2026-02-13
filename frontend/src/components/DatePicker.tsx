'use client';

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

interface DatePickerProps {
  dates: string[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

const DAY_HEADERS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

export default function DatePicker({ dates, selectedIndex, onSelect }: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const dateIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    dates.forEach((d, i) => map.set(d, i));
    return map;
  }, [dates]);

  const selectedDate = dates[selectedIndex] ?? '';
  const selectedParts = useMemo(() => {
    const [y, m] = selectedDate.split('-').map(Number);
    return { year: y || 2020, month: m || 1 };
  }, [selectedDate]);

  const [viewYear, setViewYear] = useState(selectedParts.year);
  const [viewMonth, setViewMonth] = useState(selectedParts.month);

  const handleOpen = useCallback(() => {
    setViewYear(selectedParts.year);
    setViewMonth(selectedParts.month);
    setOpen(true);
  }, [selectedParts.year, selectedParts.month]);

  // Derive first/last month boundaries from dates array
  const bounds = useMemo(() => {
    const first = dates[0] ?? '2015-01-01';
    const last = dates[dates.length - 1] ?? '2026-01-01';
    const [fy, fm] = first.split('-').map(Number);
    const [ly, lm] = last.split('-').map(Number);
    return { fy, fm, ly, lm };
  }, [dates]);

  const canPrev = viewYear > bounds.fy || (viewYear === bounds.fy && viewMonth > bounds.fm);
  const canNext = viewYear < bounds.ly || (viewYear === bounds.ly && viewMonth < bounds.lm);

  const goPrev = () => {
    if (!canPrev) return;
    if (viewMonth === 1) { setViewYear(viewYear - 1); setViewMonth(12); }
    else setViewMonth(viewMonth - 1);
  };

  const goNext = () => {
    if (!canNext) return;
    if (viewMonth === 12) { setViewYear(viewYear + 1); setViewMonth(1); }
    else setViewMonth(viewMonth + 1);
  };

  const cells = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth - 1, 1).getDay();
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const result: { day: number; dateStr: string; available: boolean; index: number }[] = [];
    for (let i = 0; i < 42; i++) {
      const dayNum = i - firstDay + 1;
      if (dayNum < 1 || dayNum > daysInMonth) {
        result.push({ day: 0, dateStr: '', available: false, index: -1 });
      } else {
        const mm = String(viewMonth).padStart(2, '0');
        const dd = String(dayNum).padStart(2, '0');
        const dateStr = `${viewYear}-${mm}-${dd}`;
        const idx = dateIndexMap.get(dateStr);
        result.push({ day: dayNum, dateStr, available: idx !== undefined, index: idx ?? -1 });
      }
    }
    return result;
  }, [viewYear, viewMonth, dateIndexMap]);

  const monthLabel = useMemo(() => {
    const d = new Date(viewYear, viewMonth - 1, 1);
    return d.toLocaleString('en-US', { month: 'long', year: 'numeric' });
  }, [viewYear, viewMonth]);

  // Close on click-outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') setOpen(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => (open ? setOpen(false) : handleOpen())}
        className="outline-none cursor-pointer flex items-center gap-1.5"
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
        <span>{selectedDate}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ opacity: 0.5 }}>
          <path d="M2 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1"
          style={{
            background: 'var(--bg2)',
            border: '1px solid var(--brd)',
            borderRadius: '10px',
            boxShadow: '0 8px 24px rgba(0,0,0,.35)',
            zIndex: 50,
            width: 280,
            padding: '12px',
          }}
        >
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-2">
            <button
              onClick={goPrev}
              disabled={!canPrev}
              className="cursor-pointer p-1 rounded"
              style={{
                opacity: canPrev ? 1 : 0.3,
                color: 'var(--t1)',
                background: 'transparent',
                border: 'none',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9 3L5 7l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--t1)' }}>
              {monthLabel}
            </span>
            <button
              onClick={goNext}
              disabled={!canNext}
              className="cursor-pointer p-1 rounded"
              style={{
                opacity: canNext ? 1 : 0.3,
                color: 'var(--t1)',
                background: 'transparent',
                border: 'none',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {DAY_HEADERS.map((h, i) => (
              <div
                key={i}
                className="text-center"
                style={{ fontSize: '9px', color: 'var(--t3)', fontWeight: 600, padding: '2px 0' }}
              >
                {h}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7">
            {cells.map((cell, i) => {
              if (cell.day === 0) {
                return <div key={i} style={{ height: 30 }} />;
              }
              const isSelected = cell.dateStr === selectedDate;
              return (
                <button
                  key={i}
                  disabled={!cell.available}
                  onClick={() => {
                    if (cell.available) {
                      onSelect(cell.index);
                      setOpen(false);
                    }
                  }}
                  className="flex items-center justify-center rounded cursor-pointer"
                  style={{
                    height: 30,
                    fontSize: '11px',
                    fontFamily: "'JetBrains Mono', monospace",
                    color: isSelected
                      ? '#fff'
                      : cell.available
                        ? 'var(--t1)'
                        : 'var(--t3)',
                    background: isSelected ? 'var(--blue)' : 'transparent',
                    opacity: cell.available ? 1 : 0.3,
                    pointerEvents: cell.available ? 'auto' : 'none',
                    border: 'none',
                    fontWeight: isSelected ? 700 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (cell.available && !isSelected) {
                      (e.target as HTMLElement).style.background = 'var(--bg3)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      (e.target as HTMLElement).style.background = 'transparent';
                    }
                  }}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
