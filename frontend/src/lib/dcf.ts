import { DashboardData } from './types';

export interface DcfInputs {
  forwardEps: number;
  currentPe: number;
  epsGrowth: number;
  discountRate: number;
  terminalGrowth: number;
  projectionYears: number;
  fadePeriod: number;
}

export interface DcfYearProjection {
  year: number;
  growthRate: number;
  eps: number;
  discountFactor: number;
  presentValue: number;
}

export interface DcfResult {
  projections: DcfYearProjection[];
  sumPvEps: number;
  terminalEps: number;
  terminalValue: number;
  pvTerminalValue: number;
  totalPvPerShare: number;
  impliedPe: number;
  currentPe: number;
  deviationPct: number;
  terminalValuePct: number;
}

export interface SensitivityCell {
  discountRate: number;
  terminalGrowth: number;
  impliedPe: number | null;
}

/** Linearly interpolate growth from initial to terminal over the fade period */
export function fadeGrowthRate(
  year: number,
  initialGrowth: number,
  terminalGrowth: number,
  fadePeriod: number
): number {
  if (fadePeriod <= 0) return terminalGrowth;
  if (year <= 0) return initialGrowth;
  if (year >= fadePeriod) return terminalGrowth;
  const t = year / fadePeriod;
  return initialGrowth * (1 - t) + terminalGrowth * t;
}

/** Core DCF computation. Returns null if inputs are invalid. */
export function computeDcf(inputs: DcfInputs): DcfResult | null {
  const { forwardEps, currentPe, epsGrowth, discountRate, terminalGrowth, projectionYears, fadePeriod } = inputs;

  // Validation guards
  if (forwardEps <= 0) return null;
  if (currentPe <= 0) return null;
  if (discountRate <= terminalGrowth) return null;

  const projections: DcfYearProjection[] = [];
  let eps = forwardEps;
  let sumPvEps = 0;

  for (let y = 1; y <= projectionYears; y++) {
    const growthRate = fadeGrowthRate(y, epsGrowth, terminalGrowth, fadePeriod);
    eps = eps * (1 + growthRate);
    const discountFactor = 1 / Math.pow(1 + discountRate, y);
    const presentValue = eps * discountFactor;
    sumPvEps += presentValue;

    projections.push({
      year: y,
      growthRate,
      eps,
      discountFactor,
      presentValue,
    });
  }

  // Terminal value via Gordon Growth Model
  const terminalEps = eps * (1 + terminalGrowth);
  const terminalValue = terminalEps / (discountRate - terminalGrowth);
  const pvTerminalValue = terminalValue / Math.pow(1 + discountRate, projectionYears);

  const totalPvPerShare = sumPvEps + pvTerminalValue;
  const impliedPe = totalPvPerShare / forwardEps;
  const deviationPct = ((impliedPe - currentPe) / currentPe) * 100;
  const terminalValuePct = (pvTerminalValue / totalPvPerShare) * 100;

  return {
    projections,
    sumPvEps,
    terminalEps,
    terminalValue,
    pvTerminalValue,
    totalPvPerShare,
    impliedPe,
    currentPe,
    deviationPct,
    terminalValuePct,
  };
}

/** Extract DCF inputs from dashboard data for a given ticker and date */
export function extractDcfInputs(
  data: DashboardData,
  ticker: string,
  dateIndex: number,
  discountRate: number,
  terminalGrowth: number,
  projectionYears: number,
  fadePeriod: number
): DcfInputs | null {
  const metrics = data.fm[ticker];
  if (!metrics) return null;

  const fe = metrics.fe[dateIndex];
  const xg = metrics.xg[dateIndex];
  const pe = metrics.pe[dateIndex];

  if (fe == null || fe <= 0) return null;
  if (xg == null) return null;
  if (pe == null || pe <= 0) return null;

  return {
    forwardEps: fe,
    currentPe: pe,
    epsGrowth: xg,
    discountRate,
    terminalGrowth,
    projectionYears,
    fadePeriod,
  };
}

/** Build a sensitivity table varying discount rate and terminal growth */
export function computeSensitivityTable(
  inputs: DcfInputs,
  discountRates: number[],
  terminalGrowths: number[]
): SensitivityCell[][] {
  return discountRates.map((dr) =>
    terminalGrowths.map((tg) => {
      const result = computeDcf({ ...inputs, discountRate: dr, terminalGrowth: tg });
      return {
        discountRate: dr,
        terminalGrowth: tg,
        impliedPe: result?.impliedPe ?? null,
      };
    })
  );
}
