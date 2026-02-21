'use client';

import { DashboardData } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import IndexFilter from './IndexFilter';
import IndustryFilter from './IndustryFilter';
import GrowthRateFilter from './GrowthRateFilter';
import TickerHighlight from './TickerHighlight';
import TickerExclusions from './TickerExclusions';
import PeerSearchPanel from './PeerSearchPanel';

interface SidebarProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
  allIndustries: string[];
  allIndices: string[];
}

export default function Sidebar({ data, state, dispatch, allIndustries, allIndices }: SidebarProps) {
  return (
    <aside
      className="overflow-y-auto p-3"
      style={{ borderRight: '1px solid var(--brd)', background: 'var(--bg1)' }}
    >
      <IndexFilter
        data={data}
        state={state}
        allIndices={allIndices}
        dispatch={dispatch}
      />
      <IndustryFilter
        allIndustries={allIndustries}
        activeIndustries={state.indOn}
        dispatch={dispatch}
      />
      <GrowthRateFilter
        revGrMin={state.revGrMin}
        revGrMax={state.revGrMax}
        epsGrMin={state.epsGrMin}
        epsGrMax={state.epsGrMax}
        dispatch={dispatch}
      />
      <TickerHighlight
        data={data}
        state={state}
        dispatch={dispatch}
      />
      <TickerExclusions
        data={data}
        state={state}
        dispatch={dispatch}
      />
      {state.view === 'peers' && (
        <PeerSearchPanel
          data={data}
          state={state}
          dispatch={dispatch}
        />
      )}
    </aside>
  );
}
