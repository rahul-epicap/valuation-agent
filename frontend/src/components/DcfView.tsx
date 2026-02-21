'use client';

import { useMemo } from 'react';
import { DashboardData } from '../lib/types';
import { Action, DashboardState } from '../hooks/useDashboardState';
import {
  extractDcfInputs,
  computeDcf,
  computeSensitivityTable,
  DcfResult,
  SensitivityCell,
} from '../lib/dcf';
import TickerSearchSelect from './TickerSearchSelect';
import CompanyHeader from './CompanyHeader';

interface DcfViewProps {
  data: DashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}

export default function DcfView({ data, state, dispatch }: DcfViewProps) {
  const ticker = state.vsTicker;

  const inputs = useMemo(
    () =>
      ticker
        ? extractDcfInputs(
            data,
            ticker,
            state.di,
            state.dcfDiscountRate,
            state.dcfTerminalGrowth,
            state.dcfProjectionYears,
            state.dcfFadePeriod
          )
        : null,
    [data, ticker, state.di, state.dcfDiscountRate, state.dcfTerminalGrowth, state.dcfProjectionYears, state.dcfFadePeriod]
  );

  const result = useMemo(() => (inputs ? computeDcf(inputs) : null), [inputs]);

  const sensitivityTable = useMemo(() => {
    if (!inputs) return null;
    const dr = inputs.discountRate;
    const tg = inputs.terminalGrowth;
    const discountRates = [dr - 0.02, dr - 0.01, dr, dr + 0.01, dr + 0.02];
    const terminalGrowths = [tg - 0.02, tg - 0.01, tg, tg + 0.01, tg + 0.02];
    return {
      rows: discountRates,
      cols: terminalGrowths,
      cells: computeSensitivityTable(inputs, discountRates, terminalGrowths),
    };
  }, [inputs]);

  return (
    <div>
      {/* Header row: ticker search */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <TickerSearchSelect
          tickers={data.tickers}
          industries={data.industries}
          selected={ticker}
          onSelect={(t) => dispatch({ type: 'SET_VS_TICKER', payload: t })}
        />
      </div>

      {/* Empty state */}
      {!ticker && (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
        >
          <div className="text-lg font-bold mb-2" style={{ color: 'var(--t2)' }}>
            Select a Ticker
          </div>
          <p className="text-xs" style={{ color: 'var(--t3)', maxWidth: 360, margin: '0 auto' }}>
            Search for a company above to see its DCF-implied P/E valuation.
            The model projects EPS forward using consensus growth, fading to a terminal rate,
            and discounts back to derive a fair-value P/E multiple.
          </p>
        </div>
      )}

      {/* Analysis content */}
      {ticker && (
        <>
          <CompanyHeader data={data} ticker={ticker} dateIndex={state.di} />

          <DcfInputControls state={state} dispatch={dispatch} />

          {!inputs && (
            <div
              className="rounded-xl p-8 text-center mb-4"
              style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
            >
              <p className="text-sm font-semibold mb-1" style={{ color: 'var(--t2)' }}>
                Data Unavailable
              </p>
              <p className="text-xs" style={{ color: 'var(--t3)' }}>
                DCF requires positive forward EPS, EPS growth data, and P/E ratio.
                This ticker may have negative earnings or missing data at the selected date.
              </p>
            </div>
          )}

          {inputs && result && (
            <>
              <DcfResultSummary result={result} />
              <EpsProjectionTable result={result} forwardEps={inputs.forwardEps} />
              {sensitivityTable && (
                <SensitivityTable
                  rows={sensitivityTable.rows}
                  cols={sensitivityTable.cols}
                  cells={sensitivityTable.cells}
                  currentPe={result.currentPe}
                  centerDr={inputs.discountRate}
                  centerTg={inputs.terminalGrowth}
                />
              )}
            </>
          )}

          <DcfMethodology />
        </>
      )}
    </div>
  );
}

/* ---------- DcfInputControls ---------- */

function DcfInputControls({
  state,
  dispatch,
}: {
  state: DashboardState;
  dispatch: React.Dispatch<Action>;
}) {
  const inputStyle = {
    background: 'var(--bg0)',
    border: '1px solid var(--brd)',
    color: 'var(--t1)',
    padding: '6px 8px',
    borderRadius: '6px',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '12px',
    width: '100%',
  } as const;

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3 className="text-xs font-bold mb-3" style={{ color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        DCF Parameters
      </h3>
      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <InputField
          label="Discount Rate"
          value={state.dcfDiscountRate}
          onChange={(v) => dispatch({ type: 'SET_DCF_DISCOUNT_RATE', payload: v })}
          format="pct"
          min={0.01}
          max={0.30}
          step={0.005}
          style={inputStyle}
        />
        <InputField
          label="Terminal Growth"
          value={state.dcfTerminalGrowth}
          onChange={(v) => dispatch({ type: 'SET_DCF_TERMINAL_GROWTH', payload: v })}
          format="pct"
          min={0.00}
          max={0.10}
          step={0.005}
          style={inputStyle}
        />
        <InputField
          label="Projection Years"
          value={state.dcfProjectionYears}
          onChange={(v) => dispatch({ type: 'SET_DCF_PROJECTION_YEARS', payload: Math.round(v) })}
          format="int"
          min={3}
          max={20}
          step={1}
          style={inputStyle}
        />
        <InputField
          label="Fade Period (yrs)"
          value={state.dcfFadePeriod}
          onChange={(v) => dispatch({ type: 'SET_DCF_FADE_PERIOD', payload: Math.round(v) })}
          format="int"
          min={1}
          max={15}
          step={1}
          style={inputStyle}
        />
      </div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  format,
  min,
  max,
  step,
  style,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  format: 'pct' | 'int';
  min: number;
  max: number;
  step: number;
  style: React.CSSProperties;
}) {
  const displayValue = format === 'pct' ? (value * 100).toFixed(1) : String(value);

  return (
    <div>
      <label
        className="block mb-1"
        style={{ fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--t3)' }}
      >
        {label}
      </label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={displayValue}
          onChange={(e) => {
            const raw = parseFloat(e.target.value);
            if (isNaN(raw)) return;
            const actual = format === 'pct' ? raw / 100 : raw;
            if (actual >= min && actual <= max) onChange(actual);
          }}
          step={format === 'pct' ? step * 100 : step}
          style={style}
        />
        {format === 'pct' && (
          <span style={{ color: 'var(--t3)', fontSize: '11px' }}>%</span>
        )}
      </div>
    </div>
  );
}

/* ---------- DcfResultSummary ---------- */

function DcfResultSummary({ result }: { result: DcfResult }) {
  const isUndervalued = result.deviationPct > 0;
  const devColor = isUndervalued ? 'var(--green)' : 'var(--red)';
  const devBg = isUndervalued ? 'var(--green-d)' : 'var(--red-d)';
  const devLabel = isUndervalued ? 'Undervalued' : 'Overvalued';

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--t1)' }}>
        DCF Valuation Summary
      </h3>

      {/* Primary cards */}
      <div className="grid gap-3 mb-3" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <StatCard label="Current P/E" value={`${result.currentPe.toFixed(1)}x`} color="var(--t1)" />
        <StatCard label="Implied DCF P/E" value={`${result.impliedPe.toFixed(1)}x`} color="var(--blue)" />
        <div className="rounded-lg p-3 text-center" style={{ background: devBg }}>
          <label className="block mb-0.5" style={{ fontSize: '8.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.7px', color: 'var(--t3)' }}>
            {devLabel}
          </label>
          <span className="font-bold" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '18px', color: devColor }}>
            {result.deviationPct > 0 ? '+' : ''}{result.deviationPct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Secondary stats */}
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <StatCard label="Sum of PVs / Share" value={`$${result.sumPvEps.toFixed(2)}`} color="var(--t2)" />
        <StatCard label="PV Terminal Value / Share" value={`$${result.pvTerminalValue.toFixed(2)}`} color="var(--t2)" />
        <StatCard label="Terminal Value %" value={`${result.terminalValuePct.toFixed(1)}%`} color="var(--t2)" />
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-lg p-3 text-center" style={{ background: 'var(--bg0)', border: '1px solid var(--brd)' }}>
      <label className="block mb-0.5" style={{ fontSize: '8.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.7px', color: 'var(--t3)' }}>
        {label}
      </label>
      <span className="font-bold" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '16px', color }}>
        {value}
      </span>
    </div>
  );
}

/* ---------- EpsProjectionTable ---------- */

function EpsProjectionTable({ result, forwardEps }: { result: DcfResult; forwardEps: number }) {
  const headerStyle = {
    fontSize: '8.5px',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    color: 'var(--t3)',
    padding: '8px 10px',
    textAlign: 'right' as const,
  };

  const cellStyle = {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '11.5px',
    color: 'var(--t1)',
    padding: '6px 10px',
    textAlign: 'right' as const,
  };

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--t1)' }}>
        EPS Projection
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--brd)' }}>
              <th style={{ ...headerStyle, textAlign: 'left' }}>Year</th>
              <th style={headerStyle}>Growth %</th>
              <th style={headerStyle}>EPS</th>
              <th style={headerStyle}>Discount Factor</th>
              <th style={headerStyle}>Present Value</th>
            </tr>
          </thead>
          <tbody>
            {/* Year 0 — current forward EPS */}
            <tr style={{ borderBottom: '1px solid var(--brd)' }}>
              <td style={{ ...cellStyle, textAlign: 'left', color: 'var(--t3)' }}>0 (Current)</td>
              <td style={{ ...cellStyle, color: 'var(--t3)' }}>&mdash;</td>
              <td style={cellStyle}>${forwardEps.toFixed(2)}</td>
              <td style={{ ...cellStyle, color: 'var(--t3)' }}>&mdash;</td>
              <td style={{ ...cellStyle, color: 'var(--t3)' }}>&mdash;</td>
            </tr>
            {result.projections.map((p) => (
              <tr key={p.year} style={{ borderBottom: '1px solid var(--brd)' }}>
                <td style={{ ...cellStyle, textAlign: 'left' }}>{p.year}</td>
                <td style={cellStyle}>{(p.growthRate * 100).toFixed(1)}%</td>
                <td style={cellStyle}>${p.eps.toFixed(2)}</td>
                <td style={cellStyle}>{p.discountFactor.toFixed(4)}</td>
                <td style={cellStyle}>${p.presentValue.toFixed(2)}</td>
              </tr>
            ))}
            {/* Terminal value row */}
            <tr style={{ borderBottom: '1px solid var(--brd)', background: 'var(--bg0)' }}>
              <td colSpan={4} style={{ ...cellStyle, textAlign: 'left', fontWeight: 700 }}>
                PV of Terminal Value
              </td>
              <td style={{ ...cellStyle, fontWeight: 700 }}>${result.pvTerminalValue.toFixed(2)}</td>
            </tr>
            {/* Total row */}
            <tr style={{ background: 'var(--bg0)' }}>
              <td colSpan={4} style={{ ...cellStyle, textAlign: 'left', fontWeight: 700, color: 'var(--blue)' }}>
                Total DCF Value / Share
              </td>
              <td style={{ ...cellStyle, fontWeight: 700, color: 'var(--blue)' }}>
                ${result.totalPvPerShare.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------- SensitivityTable ---------- */

function SensitivityTable({
  rows,
  cols,
  cells,
  currentPe,
  centerDr,
  centerTg,
}: {
  rows: number[];
  cols: number[];
  cells: SensitivityCell[][];
  currentPe: number;
  centerDr: number;
  centerTg: number;
}) {
  const headerStyle = {
    fontSize: '9px',
    fontWeight: 700,
    color: 'var(--t3)',
    padding: '6px 8px',
    textAlign: 'center' as const,
  };

  return (
    <div
      className="rounded-xl p-4 mb-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--t1)' }}>
        Sensitivity Analysis
      </h3>
      <p className="text-xs mb-3" style={{ color: 'var(--t3)' }}>
        Implied P/E by discount rate (rows) vs. terminal growth (columns)
      </p>
      <div className="overflow-x-auto">
        <table className="w-full" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...headerStyle, textAlign: 'left' }}>DR \ TG</th>
              {cols.map((tg) => (
                <th
                  key={tg}
                  style={{
                    ...headerStyle,
                    fontWeight: Math.abs(tg - centerTg) < 0.001 ? 800 : 700,
                    color: Math.abs(tg - centerTg) < 0.001 ? 'var(--t1)' : 'var(--t3)',
                  }}
                >
                  {(tg * 100).toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((dr, ri) => {
              const isCenter = Math.abs(dr - centerDr) < 0.001;
              return (
                <tr key={dr} style={{ borderTop: '1px solid var(--brd)' }}>
                  <td
                    style={{
                      ...headerStyle,
                      textAlign: 'left',
                      fontWeight: isCenter ? 800 : 700,
                      color: isCenter ? 'var(--t1)' : 'var(--t3)',
                    }}
                  >
                    {(dr * 100).toFixed(1)}%
                  </td>
                  {cells[ri].map((cell, ci) => {
                    const isCenterCell = isCenter && Math.abs(cols[ci] - centerTg) < 0.001;
                    let bgColor = 'transparent';
                    let textColor = 'var(--t2)';

                    if (cell.impliedPe != null) {
                      if (isCenterCell) {
                        bgColor = 'rgba(59,130,246,.15)';
                        textColor = 'var(--blue)';
                      } else if (cell.impliedPe > currentPe) {
                        textColor = 'var(--green)';
                      } else {
                        textColor = 'var(--red)';
                      }
                    }

                    return (
                      <td
                        key={ci}
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: '11px',
                          padding: '6px 8px',
                          textAlign: 'center',
                          color: textColor,
                          background: bgColor,
                          fontWeight: isCenterCell ? 700 : 400,
                        }}
                      >
                        {cell.impliedPe != null ? `${cell.impliedPe.toFixed(1)}x` : '\u2014'}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------- DcfMethodology ---------- */

function DcfMethodology() {
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}
    >
      <h3
        className="text-xs font-bold mb-2"
        style={{ color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}
      >
        How to Read
      </h3>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--t3)' }}>
        This DCF model uses consensus forward EPS as the cash flow proxy, projecting it forward
        using current EPS growth that linearly fades to the terminal growth rate over the fade period.
        Terminal value is calculated via the Gordon Growth Model. The total present value is divided by
        current forward EPS to produce an <strong>Implied DCF P/E</strong>.{' '}
        <strong style={{ color: 'var(--green)' }}>Positive deviation</strong> = the DCF implies a higher
        P/E than the market (potentially undervalued).{' '}
        <strong style={{ color: 'var(--red)' }}>Negative deviation</strong> = the market P/E exceeds
        the DCF-implied P/E (potentially overvalued).{' '}
        The <strong>sensitivity table</strong> shows how the implied P/E changes across different
        discount rate and terminal growth assumptions. Green cells have an implied P/E above the
        current market P/E; red cells are below.
      </p>
    </div>
  );
}
