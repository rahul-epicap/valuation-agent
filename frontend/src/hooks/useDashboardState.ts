'use client';

import { useReducer, useMemo } from 'react';
import { DashboardData, MetricType } from '../lib/types';

export type ViewMode = 'charts' | 'regression' | 'dcf';

export interface DashboardState {
  view: ViewMode;
  reg: MetricType;
  mul: MetricType;
  slp: MetricType;
  int: MetricType;
  di: number;
  indOn: Set<string>;
  exTk: Set<string>;
  hlTk: Set<string>;
  vsTicker: string | null;
  hlSrch: string;
  exSrch: string;
  revGrMin: number | null;
  revGrMax: number | null;
  epsGrMin: number | null;
  epsGrMax: number | null;
  dcfDiscountRate: number;
  dcfTerminalGrowth: number;
  dcfProjectionYears: number;
  dcfFadePeriod: number;
}

type Action =
  | { type: 'SET_VIEW'; payload: ViewMode }
  | { type: 'SET_REG'; payload: MetricType }
  | { type: 'SET_MUL'; payload: MetricType }
  | { type: 'SET_SLP'; payload: MetricType }
  | { type: 'SET_INT'; payload: MetricType }
  | { type: 'SET_DATE'; payload: number }
  | { type: 'TOGGLE_INDUSTRY'; payload: string }
  | { type: 'SELECT_ALL_INDUSTRIES'; payload: string[] }
  | { type: 'CLEAR_ALL_INDUSTRIES' }
  | { type: 'TOGGLE_HIGHLIGHT'; payload: string }
  | { type: 'CLEAR_HIGHLIGHTS' }
  | { type: 'TOGGLE_EXCLUSION'; payload: string }
  | { type: 'CLEAR_EXCLUSIONS' }
  | { type: 'EXCLUDE_VISIBLE'; payload: string[] }
  | { type: 'SET_VS_TICKER'; payload: string | null }
  | { type: 'SET_HL_SEARCH'; payload: string }
  | { type: 'SET_EX_SEARCH'; payload: string }
  | { type: 'SET_REV_GROWTH_MIN'; payload: number | null }
  | { type: 'SET_REV_GROWTH_MAX'; payload: number | null }
  | { type: 'SET_EPS_GROWTH_MIN'; payload: number | null }
  | { type: 'SET_EPS_GROWTH_MAX'; payload: number | null }
  | { type: 'SET_DCF_DISCOUNT_RATE'; payload: number }
  | { type: 'SET_DCF_TERMINAL_GROWTH'; payload: number }
  | { type: 'SET_DCF_PROJECTION_YEARS'; payload: number }
  | { type: 'SET_DCF_FADE_PERIOD'; payload: number };

function reducer(state: DashboardState, action: Action): DashboardState {
  switch (action.type) {
    case 'SET_VIEW':
      return { ...state, view: action.payload };
    case 'SET_REG':
      return { ...state, reg: action.payload };
    case 'SET_MUL':
      return { ...state, mul: action.payload };
    case 'SET_SLP':
      return { ...state, slp: action.payload };
    case 'SET_INT':
      return { ...state, int: action.payload };
    case 'SET_DATE':
      return { ...state, di: action.payload };
    case 'TOGGLE_INDUSTRY': {
      const next = new Set(state.indOn);
      if (next.has(action.payload)) next.delete(action.payload);
      else next.add(action.payload);
      return { ...state, indOn: next };
    }
    case 'SELECT_ALL_INDUSTRIES':
      return { ...state, indOn: new Set(action.payload) };
    case 'CLEAR_ALL_INDUSTRIES':
      return { ...state, indOn: new Set() };
    case 'TOGGLE_HIGHLIGHT': {
      const next = new Set(state.hlTk);
      if (next.has(action.payload)) next.delete(action.payload);
      else next.add(action.payload);
      return { ...state, hlTk: next };
    }
    case 'CLEAR_HIGHLIGHTS':
      return { ...state, hlTk: new Set() };
    case 'TOGGLE_EXCLUSION': {
      const nextEx = new Set(state.exTk);
      const nextHl = new Set(state.hlTk);
      if (nextEx.has(action.payload)) {
        nextEx.delete(action.payload);
      } else {
        nextEx.add(action.payload);
        nextHl.delete(action.payload);
      }
      return { ...state, exTk: nextEx, hlTk: nextHl };
    }
    case 'CLEAR_EXCLUSIONS':
      return { ...state, exTk: new Set() };
    case 'EXCLUDE_VISIBLE': {
      const nextEx = new Set(state.exTk);
      const nextHl = new Set(state.hlTk);
      for (const t of action.payload) {
        nextEx.add(t);
        nextHl.delete(t);
      }
      return { ...state, exTk: nextEx, hlTk: nextHl };
    }
    case 'SET_VS_TICKER':
      return { ...state, vsTicker: action.payload };
    case 'SET_HL_SEARCH':
      return { ...state, hlSrch: action.payload };
    case 'SET_EX_SEARCH':
      return { ...state, exSrch: action.payload };
    case 'SET_REV_GROWTH_MIN':
      return { ...state, revGrMin: action.payload };
    case 'SET_REV_GROWTH_MAX':
      return { ...state, revGrMax: action.payload };
    case 'SET_EPS_GROWTH_MIN':
      return { ...state, epsGrMin: action.payload };
    case 'SET_EPS_GROWTH_MAX':
      return { ...state, epsGrMax: action.payload };
    case 'SET_DCF_DISCOUNT_RATE':
      return { ...state, dcfDiscountRate: action.payload };
    case 'SET_DCF_TERMINAL_GROWTH':
      return { ...state, dcfTerminalGrowth: action.payload };
    case 'SET_DCF_PROJECTION_YEARS':
      return { ...state, dcfProjectionYears: action.payload };
    case 'SET_DCF_FADE_PERIOD':
      return { ...state, dcfFadePeriod: action.payload };
    default:
      return state;
  }
}

export function createInitialState(data: DashboardData): DashboardState {
  const allIndustries = [...new Set(Object.values(data.industries))].sort();
  return {
    view: 'charts',
    reg: 'evRev',
    mul: 'evRev',
    slp: 'evRev',
    int: 'evRev',
    di: data.dates.length - 1,
    indOn: new Set(allIndustries),
    exTk: new Set(),
    hlTk: new Set(),
    vsTicker: null,
    hlSrch: '',
    exSrch: '',
    revGrMin: null,
    revGrMax: null,
    epsGrMin: null,
    epsGrMax: null,
    dcfDiscountRate: 0.10,
    dcfTerminalGrowth: 0.03,
    dcfProjectionYears: 10,
    dcfFadePeriod: 5,
  };
}

export function useDashboardState(data: DashboardData) {
  const initialState = useMemo(() => createInitialState(data), [data]);
  const [state, dispatch] = useReducer(reducer, initialState);

  const allIndustries = useMemo(
    () => [...new Set(Object.values(data.industries))].sort(),
    [data]
  );

  return { state, dispatch, allIndustries };
}
