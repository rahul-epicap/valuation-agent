'use client';

import { Action } from '../hooks/useDashboardState';

interface GrowthRateFilterProps {
  revGrMin: number | null;
  revGrMax: number | null;
  epsGrMin: number | null;
  epsGrMax: number | null;
  dispatch: React.Dispatch<Action>;
}

export default function GrowthRateFilter({
  revGrMin,
  revGrMax,
  epsGrMin,
  epsGrMax,
  dispatch,
}: GrowthRateFilterProps) {
  const hasValue = revGrMin != null || revGrMax != null || epsGrMin != null || epsGrMax != null;

  const inputStyle = {
    background: 'var(--bg2)',
    border: '1px solid var(--brd)',
    color: 'var(--t1)',
    padding: '5px 8px',
    borderRadius: '5px',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '11px',
  };

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="font-semibold" style={{ fontSize: '11px', color: 'var(--t2)' }}>
          Growth Rate Filters
        </div>
        {hasValue && (
          <button
            onClick={() => {
              dispatch({ type: 'SET_REV_GROWTH_MIN', payload: null });
              dispatch({ type: 'SET_REV_GROWTH_MAX', payload: null });
              dispatch({ type: 'SET_EPS_GROWTH_MIN', payload: null });
              dispatch({ type: 'SET_EPS_GROWTH_MAX', payload: null });
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
      <div style={{ fontSize: '9.5px', color: 'var(--t3)', marginBottom: '4px' }}>Revenue Growth</div>
      <div className="flex gap-1.5 mb-2">
        <input
          type="number"
          placeholder="Min %"
          value={revGrMin ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_REV_GROWTH_MIN',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={inputStyle}
        />
        <input
          type="number"
          placeholder="Max %"
          value={revGrMax ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_REV_GROWTH_MAX',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={inputStyle}
        />
      </div>
      <div style={{ fontSize: '9.5px', color: 'var(--t3)', marginBottom: '4px' }}>EPS Growth</div>
      <div className="flex gap-1.5">
        <input
          type="number"
          placeholder="Min %"
          value={epsGrMin ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_EPS_GROWTH_MIN',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={inputStyle}
        />
        <input
          type="number"
          placeholder="Max %"
          value={epsGrMax ?? ''}
          onChange={(e) =>
            dispatch({
              type: 'SET_EPS_GROWTH_MAX',
              payload: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="outline-none w-full"
          style={inputStyle}
        />
      </div>
    </div>
  );
}
