'use client';

import { useReducer, useMemo } from 'react';
import { DashboardData, MetricType } from '../lib/types';

export interface DashboardState {
  reg: MetricType;
  mul: MetricType;
  slp: MetricType;
  di: number;
  indOn: Set<string>;
  exTk: Set<string>;
  hlTk: Set<string>;
  hlSrch: string;
  exSrch: string;
  epsCap: boolean;
}

type Action =
  | { type: 'SET_REG'; payload: MetricType }
  | { type: 'SET_MUL'; payload: MetricType }
  | { type: 'SET_SLP'; payload: MetricType }
  | { type: 'SET_DATE'; payload: number }
  | { type: 'TOGGLE_INDUSTRY'; payload: string }
  | { type: 'SELECT_ALL_INDUSTRIES'; payload: string[] }
  | { type: 'CLEAR_ALL_INDUSTRIES' }
  | { type: 'TOGGLE_HIGHLIGHT'; payload: string }
  | { type: 'CLEAR_HIGHLIGHTS' }
  | { type: 'TOGGLE_EXCLUSION'; payload: string }
  | { type: 'CLEAR_EXCLUSIONS' }
  | { type: 'EXCLUDE_VISIBLE'; payload: string[] }
  | { type: 'SET_HL_SEARCH'; payload: string }
  | { type: 'SET_EX_SEARCH'; payload: string }
  | { type: 'SET_EPS_CAP'; payload: boolean };

function reducer(state: DashboardState, action: Action): DashboardState {
  switch (action.type) {
    case 'SET_REG':
      return { ...state, reg: action.payload };
    case 'SET_MUL':
      return { ...state, mul: action.payload };
    case 'SET_SLP':
      return { ...state, slp: action.payload };
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
    case 'SET_HL_SEARCH':
      return { ...state, hlSrch: action.payload };
    case 'SET_EX_SEARCH':
      return { ...state, exSrch: action.payload };
    case 'SET_EPS_CAP':
      return { ...state, epsCap: action.payload };
    default:
      return state;
  }
}

export function createInitialState(data: DashboardData): DashboardState {
  const allIndustries = [...new Set(Object.values(data.industries))].sort();
  return {
    reg: 'evRev',
    mul: 'evRev',
    slp: 'evRev',
    di: data.dates.length - 1,
    indOn: new Set(allIndustries),
    exTk: new Set(),
    hlTk: new Set(),
    hlSrch: '',
    exSrch: '',
    epsCap: true,
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
