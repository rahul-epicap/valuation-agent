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

  return results;
}
