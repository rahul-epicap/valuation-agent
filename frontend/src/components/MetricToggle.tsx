'use client';

import { MetricType, METRIC_LABELS } from '../lib/types';

interface MetricToggleProps {
  active: MetricType;
  onChange: (type: MetricType) => void;
}

const TYPES: MetricType[] = ['evRev', 'evGP', 'pEPS'];

const ACTIVE_CLASSES: Record<MetricType, string> = {
  evRev: 'bg-blue-500 text-white',
  evGP: 'bg-amber-500 text-black',
  pEPS: 'bg-emerald-500 text-black',
};

export default function MetricToggle({ active, onChange }: MetricToggleProps) {
  return (
    <div className="flex gap-0.5 rounded p-0.5" style={{ background: 'var(--bg0)' }}>
      {TYPES.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`px-2.5 py-1 rounded text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
            active === t ? ACTIVE_CLASSES[t] : ''
          }`}
          style={active !== t ? { color: 'var(--t3)', background: 'transparent' } : {}}
        >
          {METRIC_LABELS[t]}
        </button>
      ))}
    </div>
  );
}
