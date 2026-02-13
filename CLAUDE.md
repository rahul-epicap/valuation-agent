# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Valuation Agent is a Jupyter notebook-based algorithmic valuation tool that estimates appropriate P/E and P/FCF multiples for a target company at 2-year and 5-year horizons using regression-based comparable analysis. It runs on Bloomberg's BQuant platform using BQL (Bloomberg Query Language) for all market data.

## Architecture

The project is a single Jupyter notebook (`valuation_agent.ipynb`) organized into 7 sequential sections (30 cells total):

1. **Configuration & Inputs** (Cells 1.1–1.3) — User-configurable parameters (GICS level, market cap ranges, tolerances, peer thresholds) and target company/projections input
2. **Data Retrieval** (Cells 2.1–2.3) — Fetches target company fundamentals and builds/queries the peer universe via BQL
3. **Peer Selection Logic** (Cells 3.1–3.4) — Four peer dimensions: sector peers, growth cohort (cross-sector), profitability peers (cross-sector), mature comparables (for 5-year terminal)
4. **Regression Analysis** (Cells 4.1–4.3) — OLS regressions of growth/profitability metrics vs. valuation multiples with outlier removal and confidence intervals
5. **Interactive Visualizations** (Cells 5.1–5.4) — Plotly scatter plots for each regression and summary comparison charts
6. **Results Output** (Cells 6.1–6.3) — Summary tables, peer detail tables, and implied valuation calculations
7. **Validation & Warnings** (Cells 7.1–7.2) — R² quality checks, data coverage warnings, and interactive peer exclusion/re-run

## Key Dependencies

- **bql** — Bloomberg Query Language Python SDK (only available within Bloomberg Terminal / BQuant environment)
- **pandas**, **numpy** — Data manipulation
- **scipy.stats** — OLS regression (linregress)
- **plotly** — Interactive visualizations
- **IPython.display** — Notebook rendering

## BQL Usage Notes

- This notebook must run inside Bloomberg's BQuant Jupyter environment where `bql.Service()` is available
- For NTM (next-twelve-months) forward estimates, use `fa_period_offset=1` with `fa_act_est_data='E'` — do NOT use `best_*` fields (fixed in commit 5763932)
- Universe construction uses `bq.univ.equitiesuniv(['ACTIVE', 'PRIMARY'])` with chained `.filter()` calls
- GICS classification fields: `gics_sector_name()`, `gics_industry_group_name()`, `gics_industry_name()`, `gics_sub_industry_name()`

## Running the Notebook

Execute cells sequentially (Kernel → Run All) inside BQuant. Before running:
1. Set `TARGET_TICKER` in Cell 1.3 (Bloomberg format, e.g., `"AAPL US Equity"`)
2. Paste 5-year projections into `PROJECTIONS_TSV` (tab-separated: Year, Revenue, EPS, FCF)
3. Adjust configuration in Cell 1.2 if needed (GICS level, market cap range, tolerances)

## Peer Selection Methodology

- **Sector peers**: Same GICS classification, filtered by market cap range, positive earnings, US exchanges
- **Growth cohort**: Cross-sector companies with similar NTM EPS growth (±GROWTH_TOLERANCE pp)
- **Profitability peers**: Cross-sector companies with similar gross/EBITDA margins
- **Mature comps**: Large-cap ($5B+ revenue), low-growth (<15%), long-history (10+ years) companies for terminal multiple estimation
- Outliers removed at ±2 standard deviations from regression line
