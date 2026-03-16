# Valuation R² Optimization — Research Program

## Objective
Maximize the **composite evaluation score** for cross-sectional valuation regressions.

We regress valuation multiples (EV/Revenue, EV/Gross Profit, Price/EPS) against growth rates and additional factors for ~3900 tickers across ~860 monthly dates (2010–2026).

The current best uses Ridge regression with growth-derived features only. We want to explore whether adding fundamental, quality, momentum, and leverage factors from FMP data can further improve R².

## Composite Score
`score = 0.40 × OOS_R² + 0.25 × stability + 0.20 × adjusted_R² + 0.15 × interpretability`

| Metric | Weight | Description |
|--------|--------|-------------|
| OOS R² | 40% | Mean R² across rolling temporal splits (train 12 months, test 1 month) |
| Stability | 25% | `1 - CV(R²)` across splits — consistent performance beats spiky |
| Adjusted R² | 20% | Penalizes adding features that don't improve fit |
| Interpretability | 15% | Economic rationale for included features (scored 0–1) |

## Available Data

### From Dashboard Snapshot (time-varying: per ticker per date)
- **Valuation multiples**: EV/Revenue (er), EV/Gross Profit (eg), Price/EPS (pe) — arrays per ticker per date
- **Growth rates**: Revenue growth (rg), EPS growth (xg) — decimal values per ticker per date
- **Forward EPS**: (fe) — absolute dollar value
- **Industries**: ~42 unique industry classifications
- **Index memberships**: Binary dummy variables for index membership

### Derived Factors (time-varying)
- **Gross margin**: `er / eg = (EV/Rev) / (EV/GP) = GP/Rev`

### FMP Factors (cross-sectional: one value per ticker, z-score standardized)

**IMPORTANT**: These factors are available on `dataset.fmp_factors` — a dict mapping factor name to a numpy array of shape `(n_tickers,)`. Values are z-score standardized cross-sectionally. NaN means the factor is unavailable for that ticker. You SHOULD try incorporating these factors into your models.

To access FMP factors for valid points at a given date, use the valid mask to index into them. Example:
```python
mask = dataset.valid_masks[metric_type][date_idx]
# Get log_market_cap for valid tickers at this date
if "log_market_cap" in dataset.fmp_factors:
    lmc = dataset.fmp_factors["log_market_cap"][mask]
```

Available FMP factors (~48 factors, ~65% coverage across tickers):

**Size** (strong economic prior — larger firms trade at lower multiples):
- `log_market_cap` — log of market capitalization (64% coverage)

**Volatility / Risk** (higher risk → higher discount rate → lower multiples):
- `beta` — stock beta vs market (70%)
- `historical_vol_30d` — 30-day annualized volatility (55%)
- `historical_vol_90d` — 90-day annualized volatility (54%)

**Momentum** (momentum drives valuation expansion/compression):
- `momentum_1m` — 1-month price return (55%)
- `momentum_3m` — 3-month price return (54%)
- `momentum_6m` — 6-month price return (53%)
- `momentum_12m` — 12-month price return (52%)

**Quality / Profitability** (higher quality → higher multiples):
- `roe` — return on equity (67%)
- `roic` — return on invested capital (67%)
- `return_on_assets` — return on assets (67%)
- `return_on_capital` — return on capital employed (67%)
- `gross_profit_margin` — gross profit margin (67%)
- `operating_profit_margin` — operating profit margin (67%)
- `net_profit_margin` — net profit margin (67%)
- `income_quality` — earnings quality (accruals vs cash) (67%)
- `fcf_yield` — free cash flow yield (67%)
- `earnings_yield` — earnings yield (67%)
- `fcf_to_operating_cf` — FCF / operating cash flow (67%)
- `asset_turnover` — asset turnover ratio (67%)

**Leverage** (higher leverage → higher risk → lower multiples, all else equal):
- `debt_to_equity` — total debt / equity (67%)
- `debt_to_assets` — total debt / assets (67%)
- `net_debt_to_ebitda` — net debt / EBITDA (67%)
- `interest_coverage` — interest coverage ratio (67%)
- `current_ratio` — current ratio (67%)

**Growth (historical from financials)** (complements forward growth from snapshot):
- `revenue_growth_hist` — historical revenue growth (67%)
- `gross_profit_growth` — gross profit growth (67%)
- `eps_growth_hist` — historical EPS growth (67%)
- `fcf_growth` — free cash flow growth (67%)
- `operating_income_growth` — operating income growth (67%)
- `three_yr_rev_growth` — 3-year revenue growth per share (67%)
- `five_yr_rev_growth` — 5-year revenue growth per share (67%)

**R&D / SBC Intensity** (high R&D → future growth option → higher multiples):
- `rd_to_revenue` — R&D expense / revenue (67%)
- `rd_expense_growth` — R&D expense growth rate (67%)
- `sbc_to_revenue` — stock-based compensation / revenue (67%)
- `capex_to_revenue` — capex / revenue (67%)

**Analyst Sentiment** (consensus view on quality/prospects):
- `n_analysts_eps` — number of analysts covering EPS (56%)
- `n_analysts_rev` — number of analysts covering revenue (56%)
- `eps_estimate_dispersion` — (high - low) / avg EPS estimate (53%)
- `earnings_surprise_pct` — latest earnings surprise % (62%)
- `avg_earnings_surprise_4q` — average surprise over last 4 quarters (62%)

**Rating** (composite quality score):
- `rating_score` — FMP composite rating (64%)

**Valuation Context** (cross-sectional valuation from FMP's perspective):
- `pe_ratio` — P/E ratio from FMP (67%)
- `pb_ratio` — P/B ratio (67%)
- `price_to_sales` — P/S ratio (67%)
- `ev_to_sales` — EV/Sales (67%)
- `ev_to_ebitda` — EV/EBITDA (67%)

## Constraints
1. Maximum **20 features** (including intercept)
2. Every feature must have **economic rationale** — no data-mined artifacts
3. Experiment must complete in **< 60 seconds**
4. Minimum **10 observations** per cross-section
5. Model must be **reproducible** — no random seeds that change between runs
6. Prefer models expressible as linear combinations for production deployment
7. FMP factors have NaN for some tickers — you must handle missing values (mean-impute or drop)

## Function Signatures (DO NOT CHANGE)
```python
def build_features(dataset, date_idx, metric_type) -> (X, y, feature_names)
def fit_model(X_train, y_train) -> model
def predict(model, X_test) -> y_pred
def get_model_description() -> str
```

## Research Directions to Explore

### HIGH PRIORITY — Try FMP factors
1. **Size effect**: Add `log_market_cap` — small caps trade at different multiples than large caps
2. **Quality premium**: Add `roic`, `roe`, or `gross_profit_margin` — high quality companies deserve higher multiples
3. **Momentum**: Add `momentum_6m` or `momentum_12m` — price momentum correlates with multiple expansion
4. **Leverage discount**: Add `debt_to_equity` or `net_debt_to_ebitda` — levered companies trade at discounts
5. **R&D intensity**: Add `rd_to_revenue` — R&D-heavy companies often trade at higher revenue multiples
6. **Analyst coverage**: Add `n_analysts_eps` — more covered stocks may price more efficiently
7. **Earnings surprise**: Add `earnings_surprise_pct` — recent beats/misses drive re-rating
8. **Multi-factor models**: Combine 3-5 FMP factors with growth in a Ridge regression
9. **Factor interactions**: growth × quality, growth × size, growth × momentum

### Also worth exploring
10. **Non-linear transforms**: log(growth), growth², interaction terms
11. **Robust regression**: Huber loss, trimmed regression
12. **Regularization**: Ridge, Lasso, Elastic Net with many factors
13. **Winsorization**: Cap extreme values instead of removing them
14. **Cross-sectional standardization**: Z-score features per date before pooling

## Tips
- FMP factors are **already z-scored** — you can use them directly as regression features
- FMP factors have **NaN for ~35% of tickers** — use `np.nanmean()` to impute or filter to non-NaN
- The relationship between growth and multiples is approximately **linear but noisy**
- **High-growth outliers** (>100% growth) often break simple OLS — consider transforms
- **Sector effects** are significant — software companies trade at different multiples than hardware
- **Market regime** matters — the slope changes dramatically over time
- The baseline OLS uses **growth percentages** (not decimals) as the X variable
- FMP factors are **cross-sectional** (constant across dates) — they add explanatory power for *why* some stocks trade at higher multiples than others at the same growth rate
- To access: `dataset.fmp_factors["log_market_cap"]` returns array of shape `(n_tickers,)`
- To get factor names: `dataset.fmp_factor_names` returns list of available factor names
