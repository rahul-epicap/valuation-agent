import { RegressionResult, CooksRegressionResult, ComparisonResult } from './types';

export function linearRegression(pts: [number, number][]): RegressionResult | null {
  const n = pts.length;
  if (n < 3) return null;

  let sx = 0, sy = 0, sxy = 0, sx2 = 0, sy2 = 0;
  for (const [x, y] of pts) {
    sx += x;
    sy += y;
    sxy += x * y;
    sx2 += x * x;
    sy2 += y * y;
  }

  const d = n * sx2 - sx * sx;
  if (Math.abs(d) < 1e-12) return null;

  const slope = (n * sxy - sx * sy) / d;
  const intercept = (sy - slope * sx) / n;
  const sst = sy2 - sy * sy / n;

  let sse = 0;
  for (const [x, y] of pts) {
    const p = slope * x + intercept;
    sse += (y - p) * (y - p);
  }

  return {
    slope,
    intercept,
    r2: sst > 0 ? 1 - sse / sst : 0,
    n,
  };
}

/**
 * Approach 1: Iterative Residual Outlier Trimming.
 * Runs OLS, removes points with |standardized residual| > threshold, re-fits.
 */
export function linearRegressionTrimmed(
  pts: [number, number][],
  threshold = 2.0,
  maxIter = 2
): (RegressionResult & { nOriginal: number }) | null {
  if (pts.length < 3) return null;
  const nOriginal = pts.length;
  let current = [...pts];

  for (let iter = 0; iter < maxIter; iter++) {
    const reg = linearRegression(current);
    if (!reg) return null;

    const residuals = current.map(([x, y]) => y - (reg.slope * x + reg.intercept));
    const mean = residuals.reduce((s, r) => s + r, 0) / residuals.length;
    const variance =
      residuals.reduce((s, r) => s + (r - mean) * (r - mean), 0) / residuals.length;
    const sigma = Math.sqrt(variance);
    if (sigma < 1e-12) break;

    const kept = current.filter(
      (_, i) => Math.abs(residuals[i] - mean) / sigma <= threshold
    );
    if (kept.length < 3 || kept.length === current.length) break;
    current = kept;
  }

  const final = linearRegression(current);
  if (!final) return null;
  return { ...final, nOriginal };
}

/**
 * Approach 2: Cook's Distance-based outlier removal.
 * Combines residual magnitude AND leverage (extreme X values) into a single
 * influence metric. Removes points where D_i > thresholdMultiplier * (4/n),
 * then re-fits. This catches high-leverage points (extreme growth stocks)
 * that residual-only trimming misses.
 */
export function linearRegressionCooks(
  pts: [number, number][],
  thresholdMultiplier = 1.0,
  maxIter = 2
): CooksRegressionResult | null {
  if (pts.length < 3) return null;
  const nOriginal = pts.length;
  // Track original indices so we can report which points were removed
  let currentIdx = pts.map((_, i) => i);
  let current = [...pts];
  const p = 2; // number of parameters (slope + intercept)

  for (let iter = 0; iter < maxIter; iter++) {
    const n = current.length;
    const reg = linearRegression(current);
    if (!reg) return null;

    const { slope, intercept } = reg;

    // Residuals and MSE
    const residuals = current.map(([x, y]) => y - (slope * x + intercept));
    const mse = residuals.reduce((s, r) => s + r * r, 0) / (n - p);
    if (mse < 1e-12) break;

    // Hat matrix diagonal: h_ii = 1/n + (x_i - x_mean)² / Σ(x_j - x_mean)²
    const xMean = current.reduce((s, [x]) => s + x, 0) / n;
    const ssX = current.reduce((s, [x]) => s + (x - xMean) * (x - xMean), 0);
    if (ssX < 1e-12) break;

    const threshold = thresholdMultiplier * (4.0 / n);
    const kept: [number, number][] = [];
    const keptIdx: number[] = [];
    for (let i = 0; i < n; i++) {
      const h = 1.0 / n + (current[i][0] - xMean) ** 2 / ssX;
      const denom = 1 - h;
      if (Math.abs(denom) < 1e-12) continue; // near-singular leverage
      const cookD = (residuals[i] ** 2 / (p * mse)) * (h / (denom * denom));
      if (cookD <= threshold) {
        kept.push(current[i]);
        keptIdx.push(currentIdx[i]);
      }
    }

    if (kept.length < 3 || kept.length === current.length) break;
    current = kept;
    currentIdx = keptIdx;
  }

  const final = linearRegression(current);
  if (!final) return null;

  const keptSet = new Set(currentIdx);
  const removedIndices = pts.map((_, i) => i).filter((i) => !keptSet.has(i));

  return { ...final, nOriginal, removedIndices };
}

/**
 * Approach 3: Huber Robust Regression (Iteratively Reweighted Least Squares).
 * Downweights outliers rather than removing them.
 */
export function linearRegressionRobust(
  pts: [number, number][],
  k = 1.345,
  maxIter = 50,
  tol = 1e-6
): RegressionResult | null {
  const n = pts.length;
  if (n < 3) return null;

  // Start with OLS estimates
  const init = linearRegression(pts);
  if (!init) return null;

  let slope = init.slope;
  let intercept = init.intercept;
  const weights = new Float64Array(n).fill(1);

  for (let iter = 0; iter < maxIter; iter++) {
    // Compute residuals
    const residuals = pts.map(([x, y]) => y - (slope * x + intercept));

    // MAD scale estimate (median absolute deviation)
    const absRes = residuals.map(Math.abs);
    const sortedAbs = [...absRes].sort((a, b) => a - b);
    const medianAbsRes =
      sortedAbs.length % 2 === 0
        ? (sortedAbs[sortedAbs.length / 2 - 1] + sortedAbs[sortedAbs.length / 2]) / 2
        : sortedAbs[Math.floor(sortedAbs.length / 2)];
    const scale = medianAbsRes / 0.6745; // MAD-based σ estimate
    if (scale < 1e-12) break;

    // Huber weights
    for (let i = 0; i < n; i++) {
      const u = Math.abs(residuals[i]) / scale;
      weights[i] = u <= k ? 1 : k / u;
    }

    // Weighted least squares
    let wsx = 0, wsy = 0, wsxy = 0, wsx2 = 0, wsum = 0;
    for (let i = 0; i < n; i++) {
      const w = weights[i];
      const [x, y] = pts[i];
      wsum += w;
      wsx += w * x;
      wsy += w * y;
      wsxy += w * x * y;
      wsx2 += w * x * x;
    }

    const wd = wsum * wsx2 - wsx * wsx;
    if (Math.abs(wd) < 1e-12) return null;

    const newSlope = (wsum * wsxy - wsx * wsy) / wd;
    const newIntercept = (wsy - newSlope * wsx) / wsum;

    const change = Math.abs(newSlope - slope) + Math.abs(newIntercept - intercept);
    slope = newSlope;
    intercept = newIntercept;
    if (change < tol) break;
  }

  // Compute R² on original scale (unweighted)
  const meanY = pts.reduce((s, [, y]) => s + y, 0) / n;
  let sst = 0, sse = 0;
  for (const [x, y] of pts) {
    sst += (y - meanY) * (y - meanY);
    const p = slope * x + intercept;
    sse += (y - p) * (y - p);
  }

  return {
    slope,
    intercept,
    r2: sst > 0 ? 1 - sse / sst : 0,
    n,
  };
}

/**
 * Approach 3: Log-Linear Regression.
 * Regresses log(multiple) against growth to handle concavity and compress extremes.
 * Returns log-space slope/intercept; R² is computed on original scale.
 */
export function logLinearRegression(
  pts: [number, number][]
): (RegressionResult & { logSlope: number; logIntercept: number }) | null {
  // Filter to positive y values (required for log transform)
  const valid = pts.filter(([, y]) => y > 0);
  if (valid.length < 3) return null;

  const logPts: [number, number][] = valid.map(([x, y]) => [x, Math.log(y)]);
  const logReg = linearRegression(logPts);
  if (!logReg) return null;

  const logSlope = logReg.slope;
  const logIntercept = logReg.intercept;

  // Compute R² on original (non-log) scale for fair comparison
  const meanY = valid.reduce((s, [, y]) => s + y, 0) / valid.length;
  let sst = 0, sse = 0;
  for (const [x, y] of valid) {
    sst += (y - meanY) * (y - meanY);
    const predicted = Math.exp(logIntercept + logSlope * x);
    sse += (y - predicted) * (y - predicted);
  }

  return {
    slope: logSlope,
    intercept: logIntercept,
    logSlope,
    logIntercept,
    r2: sst > 0 ? 1 - sse / sst : 0,
    n: valid.length,
  };
}

// ---------------------------------------------------------------------------
// Enhanced Ridge regression with winsorized features (autoresearch discovery)
// ---------------------------------------------------------------------------

function winsorize(arr: number[], lower = 5, upper = 95): number[] {
  if (arr.length === 0) return arr;
  const sorted = [...arr].sort((a, b) => a - b);
  const lo = sorted[Math.floor(arr.length * lower / 100)];
  const hi = sorted[Math.ceil(arr.length * upper / 100) - 1];
  return arr.map(v => Math.min(Math.max(v, lo), hi));
}

export interface EnhancedRegressionResult {
  intercept: number;
  coefficients: number[];
  means: number[];
  stds: number[];
  featureNames: string[];
  r2: number;
  adjustedR2: number;
  n: number;
  predict: (growthPct: number, grossMargin?: number) => number;
}

/**
 * Metric-specific Ridge regression with winsorized features.
 * Discovered by autoresearch:
 *   - P/EPS: growth%, positive_growth, |growth| (OOS R²=0.20)
 *   - EV/Rev: growth%, gross_margin, growth×margin (OOS R²=0.14)
 *   - EV/GP: growth%, positive_growth, log|growth|
 *
 * All use Ridge (lambda=10), feature standardization, and winsorization.
 */
export function ridgeEnhancedRegression(
  pts: [number, number][],
  metricType: string = 'evRev',
  grossMargins?: number[],
  lambda = 10.0,
): EnhancedRegressionResult | null {
  const n = pts.length;
  if (n < 10) return null;

  const isEps = metricType === 'pEPS' || metricType === 'pEPS_GAAP';

  // Filter valid observations
  const validIdx: number[] = [];
  for (let i = 0; i < n; i++) {
    const [x, y] = pts[i];
    if (!isFinite(x) || !isFinite(y) || y <= 0) continue;
    if (isEps && y >= 150) continue;
    validIdx.push(i);
  }
  if (validIdx.length < 10) return null;

  let growth = validIdx.map(i => pts[i][0]);
  let mult = validIdx.map(i => pts[i][1]);
  const nv = validIdx.length;

  // Winsorize — tighter for PE
  if (isEps) {
    mult = winsorize(mult, 3, 97);
    growth = winsorize(growth, 3, 97);
  } else {
    mult = winsorize(mult, 2, 98);
    growth = winsorize(growth, 3, 97);
  }

  // Build metric-specific features
  let featureNames: string[];
  const X: number[][] = [];

  if (isEps) {
    // P/EPS: growth, positive indicator, absolute magnitude
    featureNames = ['growth_pct_w', 'positive_growth', 'growth_abs'];
    for (let i = 0; i < nv; i++) {
      const g = growth[i];
      X.push([g, g > 0 ? 1 : 0, Math.abs(g)]);
    }
  } else if (metricType === 'evRev') {
    // EV/Rev: growth, gross margin, growth×margin
    featureNames = ['growth_pct_w', 'gross_margin', 'growth_x_margin'];
    const hasGM = grossMargins != null && grossMargins.length === pts.length;
    let gmW: number[];
    if (hasGM) {
      const rawGM = validIdx.map(i => grossMargins![i]);
      const finiteGM = rawGM.filter(v => isFinite(v));
      const meanGM = finiteGM.length > 0
        ? finiteGM.reduce((s, v) => s + v, 0) / finiteGM.length : 0;
      gmW = winsorize(
        rawGM.map(v => isFinite(v) ? v : meanGM), 3, 97
      );
    } else {
      gmW = new Array(nv).fill(0);
    }
    for (let i = 0; i < nv; i++) {
      const g = growth[i];
      X.push([g, gmW[i], g * gmW[i]]);
    }
  } else {
    // EV/GP: growth, positive indicator, log|growth|
    featureNames = ['growth_pct_w', 'positive_growth', 'log_growth_abs'];
    for (let i = 0; i < nv; i++) {
      const g = growth[i];
      X.push([g, g > 0 ? 1 : 0, Math.sign(g) * Math.log1p(Math.abs(g))]);
    }
  }

  // Standardize features
  const p = featureNames.length;
  const means = new Array(p).fill(0);
  const stds = new Array(p).fill(0);

  for (let j = 0; j < p; j++) {
    let sum = 0;
    for (let i = 0; i < nv; i++) sum += X[i][j];
    means[j] = sum / nv;
  }
  for (let j = 0; j < p; j++) {
    let sumSq = 0;
    for (let i = 0; i < nv; i++) sumSq += (X[i][j] - means[j]) ** 2;
    stds[j] = Math.sqrt(sumSq / nv);
    if (stds[j] < 1e-10) stds[j] = 1;
  }
  for (let i = 0; i < nv; i++) {
    for (let j = 0; j < p; j++) {
      X[i][j] = (X[i][j] - means[j]) / stds[j];
    }
  }

  // Ridge: beta = (X'X + λI)⁻¹ X'y
  const totalP = p + 1;
  const XtX: number[][] = Array.from(
    { length: totalP }, () => new Array(totalP).fill(0)
  );
  const Xty = new Array(totalP).fill(0);

  for (let i = 0; i < nv; i++) {
    const row = [1, ...X[i]];
    const y = mult[i];
    for (let a = 0; a < totalP; a++) {
      Xty[a] += row[a] * y;
      for (let b = 0; b < totalP; b++) {
        XtX[a][b] += row[a] * row[b];
      }
    }
  }
  for (let j = 1; j < totalP; j++) {
    XtX[j][j] += lambda;
  }

  const inv = invertMatrix(XtX);
  if (!inv) return null;

  const beta = new Array(totalP).fill(0);
  for (let i = 0; i < totalP; i++) {
    for (let j = 0; j < totalP; j++) {
      beta[i] += inv[i][j] * Xty[j];
    }
  }

  let sst = 0, sse = 0;
  const yMean = mult.reduce((s, v) => s + v, 0) / nv;
  for (let i = 0; i < nv; i++) {
    sst += (mult[i] - yMean) ** 2;
    let pred = beta[0];
    for (let j = 0; j < p; j++) pred += X[i][j] * beta[j + 1];
    sse += (mult[i] - pred) ** 2;
  }
  const r2 = sst > 0 ? 1 - sse / sst : 0;
  const adjustedR2 = sst > 0 ? 1 - ((1 - r2) * (nv - 1)) / (nv - totalP) : 0;

  const intercept = beta[0];
  const coefficients = beta.slice(1);

  return {
    intercept,
    coefficients,
    means,
    stds,
    featureNames,
    r2,
    adjustedR2,
    n: nv,
    predict: (growthPct: number, grossMargin = 0) => {
      const g = growthPct;
      let raw: number[];
      if (isEps) {
        raw = [g, g > 0 ? 1 : 0, Math.abs(g)];
      } else if (metricType === 'evRev') {
        raw = [g, grossMargin, g * grossMargin];
      } else {
        raw = [g, g > 0 ? 1 : 0, Math.sign(g) * Math.log1p(Math.abs(g))];
      }
      let y = intercept;
      for (let j = 0; j < p; j++) {
        y += ((raw[j] - means[j]) / stds[j]) * coefficients[j];
      }
      return y;
    },
  };
}

/** Simple Gauss-Jordan matrix inversion (for Ridge normal equations). */
function invertMatrix(M: number[][]): number[][] | null {
  const n = M.length;
  const aug: number[][] = M.map((row, i) => {
    const r = [...row];
    for (let j = 0; j < n; j++) r.push(i === j ? 1 : 0);
    return r;
  });
  for (let col = 0; col < n; col++) {
    let maxVal = Math.abs(aug[col][col]);
    let maxRow = col;
    for (let row = col + 1; row < n; row++) {
      const val = Math.abs(aug[row][col]);
      if (val > maxVal) { maxVal = val; maxRow = row; }
    }
    if (maxVal < 1e-12) return null;
    if (maxRow !== col) [aug[col], aug[maxRow]] = [aug[maxRow], aug[col]];
    const pivot = aug[col][col];
    for (let j = 0; j < 2 * n; j++) aug[col][j] /= pivot;
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const f = aug[row][col];
      for (let j = 0; j < 2 * n; j++) aug[row][j] -= f * aug[col][j];
    }
  }
  return aug.map(row => row.slice(n));
}

/**
 * Runs all four regression methods on the same data and returns comparable results.
 */
export function compareRegressionMethods(
  pts: [number, number][]
): ComparisonResult[] {
  const results: ComparisonResult[] = [];
  const nOriginal = pts.length;

  // 1. Standard OLS
  const ols = linearRegression(pts);
  if (ols) {
    results.push({
      method: 'ols',
      label: 'OLS (Current)',
      r2: ols.r2,
      n: ols.n,
      nOriginal,
      slope: ols.slope,
      intercept: ols.intercept,
      predict: (x: number) => ols.slope * x + ols.intercept,
    });
  }

  // 2. Iterative Residual Trimming
  const trimmed = linearRegressionTrimmed(pts);
  if (trimmed) {
    results.push({
      method: 'trimmed',
      label: 'Residual Trimming',
      r2: trimmed.r2,
      n: trimmed.n,
      nOriginal: trimmed.nOriginal,
      slope: trimmed.slope,
      intercept: trimmed.intercept,
      predict: (x: number) => trimmed.slope * x + trimmed.intercept,
    });
  }

  // 3. Cook's Distance
  const cooks = linearRegressionCooks(pts);
  if (cooks) {
    results.push({
      method: 'cooks',
      label: "Cook's Distance",
      r2: cooks.r2,
      n: cooks.n,
      nOriginal: cooks.nOriginal,
      slope: cooks.slope,
      intercept: cooks.intercept,
      predict: (x: number) => cooks.slope * x + cooks.intercept,
    });
  }

  // 5. Huber Robust Regression
  const robust = linearRegressionRobust(pts);
  if (robust) {
    results.push({
      method: 'robust',
      label: 'Robust (Huber)',
      r2: robust.r2,
      n: robust.n,
      nOriginal,
      slope: robust.slope,
      intercept: robust.intercept,
      predict: (x: number) => robust.slope * x + robust.intercept,
    });
  }

  // 6. Log-Linear
  const logLin = logLinearRegression(pts);
  if (logLin) {
    results.push({
      method: 'logLinear',
      label: 'Log-Linear',
      r2: logLin.r2,
      n: logLin.n,
      nOriginal,
      slope: logLin.logSlope,
      intercept: logLin.logIntercept,
      predict: (x: number) => Math.exp(logLin.logIntercept + logLin.logSlope * x),
    });
  }

  // 7. Ridge Enhanced (autoresearch — winsorized + growth features)
  const ridge = ridgeEnhancedRegression(pts);
  if (ridge) {
    results.push({
      method: 'ridgeEnhanced',
      label: 'Ridge Enhanced',
      r2: ridge.r2,
      n: ridge.n,
      nOriginal,
      slope: ridge.coefficients[0],   // growth coefficient (standardized)
      intercept: ridge.intercept,
      predict: (x: number) => ridge.predict(x),
    });
  }

  return results;
}
