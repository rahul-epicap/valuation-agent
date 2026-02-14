'use client';

import { ValueScoreEntry } from '../lib/valueScore';
import { HIGHLIGHT_COLORS } from '../lib/types';

interface ValueScoreCardProps {
  entry: ValueScoreEntry;
  highlightIndex: number | null;
}

export default function ValueScoreCard({ entry, highlightIndex }: ValueScoreCardProps) {
  const isUndervalued = entry.pctDiff < 0;
  const badgeColor = isUndervalued ? 'var(--green)' : 'var(--red)';
  const borderColor = highlightIndex != null ? HIGHLIGHT_COLORS[highlightIndex % HIGHLIGHT_COLORS.length] : 'var(--brd)';

  return (
    <div
      className="rounded-lg p-3 flex items-center gap-3"
      style={{
        background: 'var(--bg0)',
        border: '1px solid var(--brd)',
        borderLeft: highlightIndex != null ? `3px solid ${borderColor}` : '1px solid var(--brd)',
      }}
    >
      {/* Ticker + Industry */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-1.5">
          <span className="font-bold text-sm" style={{ color: 'var(--t1)' }}>
            {entry.ticker}
          </span>
          <span
            className="text-xs truncate"
            style={{ color: 'var(--t3)' }}
          >
            {entry.industry}
          </span>
        </div>
        <div
          className="mt-1 flex gap-3 text-xs"
          style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--t2)' }}
        >
          <span>Growth: {entry.growth.toFixed(1)}%</span>
          <span>Actual: {entry.actual.toFixed(1)}x</span>
          <span>Pred: {entry.predicted.toFixed(1)}x</span>
        </div>
      </div>

      {/* Pct Diff Badge */}
      <div
        className="rounded-md px-2.5 py-1 text-sm font-bold whitespace-nowrap"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          background: `${badgeColor}20`,
          color: badgeColor,
        }}
      >
        {entry.pctDiff > 0 ? '+' : ''}{entry.pctDiff.toFixed(1)}%
      </div>
    </div>
  );
}
