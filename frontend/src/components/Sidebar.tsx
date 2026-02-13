'use client';

import { DashboardData } from '../lib/types';
import { DashboardState } from '../hooks/useDashboardState';
import IndustryFilter from './IndustryFilter';
import GrowthRateFilter from './GrowthRateFilter';
import TickerHighlight from './TickerHighlight';
import TickerExclusions from './TickerExclusions';

interface SidebarProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<any>;
  allIndustries: string[];
}

export default function Sidebar({ data, state, dispatch, allIndustries }: SidebarProps) {
  return (
    <aside
      className="overflow-y-auto p-3"
      style={{ borderRight: '1px solid var(--brd)', background: 'var(--bg1)' }}
    >
      <IndustryFilter
        allIndustries={allIndustries}
        activeIndustries={state.indOn}
        dispatch={dispatch}
      />
      <GrowthRateFilter
        grMin={state.grMin}
        grMax={state.grMax}
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
    </aside>
  );
}
