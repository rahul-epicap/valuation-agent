'use client';

interface GrowthRateFilterProps {
  grMin: number | null;
  grMax: number | null;
  dispatch: React.Dispatch<any>;
}

export default function GrowthRateFilter({ grMin, grMax, dispatch }: GrowthRateFilterProps) {
  const hasValue = grMin != null || grMax != null;

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="font-semibold" style={{ fontSize: '11px', color: 'var(--t2)' }}>
          Growth Rate Filter
        </div>
        {hasValue && (
          <button
            onClick={() => {
              dispatch({ type: 'SET_GROWTH_MIN', payload: null });
              dispatch({ type: 'SET_GROWTH_MAX', payload: null });
            }}
            className="cursor-pointer"
            style={{
              fontSize: '9.5px',
              color: 'var(--blue)',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex gap-1.5">
        <input
          type="number"
          placeholder="Min %"
          value={grMin ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_GROWTH_MIN',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={{
            background: 'var(--bg2)',
            border: '1px solid var(--brd)',
            color: 'var(--t1)',
            padding: '5px 8px',
            borderRadius: '5px',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '11px',
          }}
        />
        <input
          type="number"
          placeholder="Max %"
          value={grMax ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_GROWTH_MAX',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={{
            background: 'var(--bg2)',
            border: '1px solid var(--brd)',
            color: 'var(--t1)',
            padding: '5px 8px',
            borderRadius: '5px',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '11px',
          }}
        />
      </div>
    </div>
  );
}
