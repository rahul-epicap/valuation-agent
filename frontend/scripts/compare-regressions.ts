/**
 * Compare all 4 regression methods across the full dataset.
 * Usage: npx tsx scripts/compare-regressions.ts [API_URL]
 */

import { DashboardData, MetricType } from '../src/lib/types';
import { computeAggregateComparison, computeHistoricalBaseline, computeHistoricalBaselineWeighted } from '../src/lib/valueScore';

const API_URL = process.argv[2] || 'http://localhost:8000';

async function fetchData(): Promise<DashboardData> {
  const res = await fetch(`${API_URL}/api/dashboard-data`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json() as Promise<DashboardData>;
}

function pad(s: string, len: number): string {
  return s.length >= len ? s : s + ' '.repeat(len - s.length);
}
function rpad(s: string, len: number): string {
  return s.length >= len ? s : ' '.repeat(len - s.length) + s;
}

function printTable(
  title: string,
  headers: string[],
  rows: string[][],
  widths: number[]
) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`  ${title}`);
  console.log('='.repeat(70));
  const hdr = headers.map((h, i) => i === 0 ? pad(h, widths[i]) : rpad(h, widths[i])).join('  ');
  console.log(hdr);
  console.log('-'.repeat(hdr.length));
  for (const row of rows) {
    console.log(row.map((c, i) => i === 0 ? pad(c, widths[i]) : rpad(c, widths[i])).join('  '));
  }
}

async function main() {
  console.log(`Fetching data from ${API_URL}/api/dashboard-data ...`);
  const data = await fetchData();
  console.log(`Loaded: ${data.tickers.length} tickers, ${data.dates.length} dates`);

  const allTickers = data.tickers;
  const metrics: MetricType[] = ['evRev', 'evGP', 'pEPS'];
  const metricLabels: Record<MetricType, string> = {
    evRev: 'EV / Revenue',
    evGP: 'EV / Gross Profit',
    pEPS: 'Price / EPS',
  };

  for (const metric of metrics) {
    // Run aggregate comparison (no growth filters for broad test)
    const results = computeAggregateComparison(
      data, metric, allTickers, null, null, null, null
    );

    const headers = ['Method', 'Avg R²', 'Med R²', 'Avg N', 'Periods', 'Wins', 'Win%', 'Avg Slope', 'Avg Intcpt'];
    const widths =  [22,        8,        8,        7,       8,         5,      6,      10,          10];
    const totalPeriods = results[0]?.periodCount || 1;

    const rows = results.map((r) => [
      r.label,
      r.avgR2.toFixed(4),
      r.medianR2.toFixed(4),
      r.avgN.toFixed(0),
      String(r.periodCount),
      String(r.winCount),
      ((r.winCount / totalPeriods) * 100).toFixed(1) + '%',
      r.avgSlope.toFixed(4),
      r.avgIntercept.toFixed(2),
    ]);

    // Sort by avg R² descending for display
    rows.sort((a, b) => parseFloat(b[1]) - parseFloat(a[1]));

    printTable(`${metricLabels[metric]} — Spot Regression (${data.dates.length} periods)`, headers, rows, widths);

    // Also show avg N trimmed vs original for trimming method
    const trimmed = results.find((r) => r.method === 'trimmed');
    if (trimmed && trimmed.avgN < trimmed.avgNOriginal) {
      const pctKept = (trimmed.avgN / trimmed.avgNOriginal * 100).toFixed(1);
      console.log(`  Trimming keeps avg ${trimmed.avgN.toFixed(0)} of ${trimmed.avgNOriginal.toFixed(0)} pts (${pctKept}%)`);
    }
  }

  // Historical baseline comparison: equal-weight vs R²-weighted
  console.log(`\n${'='.repeat(70)}`);
  console.log('  Historical Baseline: Equal-Weight vs R²-Weighted');
  console.log('='.repeat(70));

  const blHeaders = ['Metric', 'Method', 'Avg Slope', 'Avg Intcpt', 'Avg R²', 'Periods'];
  const blWidths = [18, 18, 10, 10, 8, 8];

  const blRows: string[][] = [];
  for (const metric of metrics) {
    const eq = computeHistoricalBaseline(data, metric, allTickers, null, null, null, null);
    const wt = computeHistoricalBaselineWeighted(data, metric, allTickers, null, null, null, null);

    if (eq) {
      blRows.push([
        metricLabels[metric], 'Equal-Weight',
        eq.avgSlope.toFixed(4), eq.avgIntercept.toFixed(2),
        eq.avgR2.toFixed(4), String(eq.periodCount),
      ]);
    }
    if (wt) {
      blRows.push([
        metricLabels[metric], 'R²-Weighted',
        wt.avgSlope.toFixed(4), wt.avgIntercept.toFixed(2),
        wt.avgR2.toFixed(4), String(wt.periodCount),
      ]);
    }
  }

  const hdr = blHeaders.map((h, i) => i === 0 ? pad(h, blWidths[i]) : rpad(h, blWidths[i])).join('  ');
  console.log(hdr);
  console.log('-'.repeat(hdr.length));
  for (const row of blRows) {
    console.log(row.map((c, i) => i === 0 ? pad(c, blWidths[i]) : rpad(c, blWidths[i])).join('  '));
  }

  console.log('\nDone.');
}

main().catch((e) => {
  console.error('Error:', e.message);
  process.exit(1);
});
