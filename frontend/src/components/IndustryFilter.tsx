'use client';

interface IndustryFilterProps {
  allIndustries: string[];
  activeIndustries: Set<string>;
  dispatch: React.Dispatch<any>;
}

export default function IndustryFilter({ allIndustries, activeIndustries, dispatch }: IndustryFilterProps) {
  return (
    <div className="mb-4">
      <div
        className="font-bold uppercase mb-1.5 pl-0.5"
        style={{ color: 'var(--t3)', fontSize: '9.5px', letterSpacing: '1px' }}
      >
        Industry Filter
      </div>
      <div className="flex gap-1 mb-1.5 flex-wrap">
        <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'var(--blue-d)', color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>
          {activeIndustries.size} selected
        </span>
        <span className="px-1.5 py-0.5 rounded font-semibold" style={{ fontSize: '9.5px', background: 'rgba(255,255,255,.04)', color: 'var(--t3)', fontFamily: "'JetBrains Mono', monospace" }}>
          {allIndustries.length} total
        </span>
      </div>
      <div className="flex gap-1 mb-1.5">
        <button
          onClick={() => dispatch({ type: 'SELECT_ALL_INDUSTRIES', payload: allIndustries })}
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{ fontSize: '9.5px', border: '1px solid var(--brd)', background: 'var(--bg2)', color: 'var(--t2)' }}
        >
          Select All
        </button>
        <button
          onClick={() => dispatch({ type: 'CLEAR_ALL_INDUSTRIES' })}
          className="px-2 py-1 rounded font-semibold cursor-pointer"
          style={{ fontSize: '9.5px', border: '1px solid var(--brd)', background: 'var(--bg2)', color: 'var(--t2)' }}
        >
          Clear All
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-64 overflow-y-auto">
        {allIndustries.map((ind) => {
          const active = activeIndustries.has(ind);
          return (
            <div
              key={ind}
              onClick={() => dispatch({ type: 'TOGGLE_INDUSTRY', payload: ind })}
              className="cursor-pointer select-none transition-all"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 6px',
                borderRadius: '3px',
                fontSize: '10px',
                fontWeight: active ? 600 : 500,
                border: `1px solid ${active ? '#2563eb' : 'var(--brd)'}`,
                background: active ? '#2563eb' : 'var(--bg2)',
                color: active ? '#fff' : 'var(--t2)',
              }}
            >
              {ind}
            </div>
          );
        })}
      </div>
    </div>
  );
}
