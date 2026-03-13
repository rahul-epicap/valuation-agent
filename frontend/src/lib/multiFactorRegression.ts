/**
 * Multi-factor OLS regression solver using normal equations.
 *
 * Solves β = (X'X)⁻¹X'y where X columns are:
 *   [0] = intercept (1s), [1] = growth%, [2+] = factor dummies.
 *
 * Uses Gauss-Jordan elimination with partial pivoting for inversion.
 */
import { MultiFactorRegressionResult, MultiFactorScatterPoint, RegressionFactor } from './types';
import { CONTINUOUS_FACTORS } from './filters';

// ---------------------------------------------------------------------------
// Matrix utilities (dense, small matrices — at most ~100×100)
// ---------------------------------------------------------------------------

export function matTranspose(A: number[][]): number[][] {
  const rows = A.length;
  const cols = A[0].length;
  const T: number[][] = Array.from({ length: cols }, () => new Array(rows));
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      T[j][i] = A[i][j];
    }
  }
  return T;
}

export function matMultiply(A: number[][], B: number[][]): number[][] {
  const m = A.length;
  const n = B[0].length;
  const k = B.length;
  const C: number[][] = Array.from({ length: m }, () => new Array(n).fill(0));
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < n; j++) {
      let sum = 0;
      for (let p = 0; p < k; p++) {
        sum += A[i][p] * B[p][j];
      }
      C[i][j] = sum;
    }
  }
  return C;
}

/**
 * Gauss-Jordan inversion with partial pivoting.
 * Returns null if the matrix is singular.
 */
export function matInvert(M: number[][]): number[][] | null {
  const n = M.length;
  // Augmented matrix [M | I]
  const aug: number[][] = M.map((row, i) => {
    const r = [...row];
    for (let j = 0; j < n; j++) r.push(i === j ? 1 : 0);
    return r;
  });

  for (let col = 0; col < n; col++) {
    // Partial pivoting: find row with largest absolute value in column
    let maxVal = Math.abs(aug[col][col]);
    let maxRow = col;
    for (let row = col + 1; row < n; row++) {
      const val = Math.abs(aug[row][col]);
      if (val > maxVal) {
        maxVal = val;
        maxRow = row;
      }
    }
    if (maxVal < 1e-12) return null; // Singular

    // Swap rows
    if (maxRow !== col) {
      [aug[col], aug[maxRow]] = [aug[maxRow], aug[col]];
    }

    // Scale pivot row
    const pivot = aug[col][col];
    for (let j = 0; j < 2 * n; j++) {
      aug[col][j] /= pivot;
    }

    // Eliminate column in all other rows
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = aug[row][col];
      for (let j = 0; j < 2 * n; j++) {
        aug[row][j] -= factor * aug[col][j];
      }
    }
  }

  // Extract inverse from right half
  return aug.map((row) => row.slice(n));
}

/**
 * Multiply matrix by column vector: Ax = b.
 */
function matVecMultiply(A: number[][], v: number[]): number[] {
  return A.map((row) => row.reduce((sum, val, j) => sum + val * v[j], 0));
}

// ---------------------------------------------------------------------------
// Collinearity guard: drop factors with zero variance or < 3 members
// ---------------------------------------------------------------------------

interface FilteredFactors {
  /** Indices into original factorNames that survived */
  keptIndices: number[];
  /** Names of surviving factors */
  keptNames: string[];
  /** Filtered design matrix (still includes intercept col 0 and growth col 1) */
  X: number[][];
}

function filterFactors(
  X: number[][],
  factorNames: string[],
  minMembers: number = 3,
): FilteredFactors {
  const n = X.length;
  const keptIndices: number[] = [];
  const keptNames: string[] = [];

  for (let f = 0; f < factorNames.length; f++) {
    const colIdx = f + 2; // columns 0=intercept, 1=growth, 2+=factors
    // Count non-zero entries (members)
    let count = 0;
    let sum = 0;
    for (let i = 0; i < n; i++) {
      sum += X[i][colIdx];
      if (X[i][colIdx] !== 0) count++;
    }
    if (count < minMembers) continue;

    // Check variance
    const mean = sum / n;
    let variance = 0;
    for (let i = 0; i < n; i++) {
      variance += (X[i][colIdx] - mean) ** 2;
    }
    variance /= n;
    if (variance < 1e-12) continue;

    keptIndices.push(f);
    keptNames.push(factorNames[f]);
  }

  // Rebuild X with only kept factor columns
  const filteredX: number[][] = X.map((row) => {
    const newRow = [row[0], row[1]]; // intercept + growth
    for (const fi of keptIndices) {
      newRow.push(row[fi + 2]);
    }
    return newRow;
  });

  return { keptIndices, keptNames, X: filteredX };
}

// ---------------------------------------------------------------------------
// Core OLS solver
// ---------------------------------------------------------------------------

/**
 * Multi-factor OLS regression via normal equations β = (X'X)⁻¹X'y.
 *
 * @param y - Response vector (valuation multiples)
 * @param X - Design matrix: col 0 = 1 (intercept), col 1 = growth%, cols 2+ = factors
 * @param factorNames - Names for columns 2+ (must match X column count - 2)
 * @returns Regression result or null if matrix is singular / insufficient data
 */
export function multiFactorOLS(
  y: number[],
  X: number[][],
  factorNames: string[],
): MultiFactorRegressionResult | null {
  const n = y.length;
  if (n < 3) return null;

  // Filter out collinear / sparse factors
  const { keptNames, X: Xf } = filterFactors(X, factorNames);
  const p = Xf[0].length; // total parameter count (intercept + growth + factors)

  if (n <= p) return null; // Need more observations than parameters

  // Normal equations: β = (X'X)⁻¹ X'y
  const Xt = matTranspose(Xf);
  const XtX = matMultiply(Xt, Xf);
  const XtXinv = matInvert(XtX);
  if (!XtXinv) return null;

  // X'y as column vector
  const yCol = y.map((v) => [v]);
  const Xty = matMultiply(Xt, yCol).map((r) => r[0]);
  const beta = matVecMultiply(XtXinv, Xty);

  // Compute R² and adjusted R²
  const yMean = y.reduce((s, v) => s + v, 0) / n;
  let sst = 0;
  let sse = 0;
  for (let i = 0; i < n; i++) {
    sst += (y[i] - yMean) ** 2;
    const predicted = Xf[i].reduce((sum, xij, j) => sum + xij * beta[j], 0);
    sse += (y[i] - predicted) ** 2;
  }

  const r2 = sst > 0 ? 1 - sse / sst : 0;
  const adjustedR2 = sst > 0 ? 1 - ((1 - r2) * (n - 1)) / (n - p) : 0;

  // Build factor results
  const factors: RegressionFactor[] = keptNames.map((name, i) => ({
    name,
    type: name in CONTINUOUS_FACTORS ? 'continuous' : 'binary',
    coefficient: beta[i + 2], // skip intercept and growth
  }));

  return {
    intercept: beta[0],
    growthCoefficient: beta[1],
    factors,
    r2,
    adjustedR2,
    n,
    p,
  };
}

// ---------------------------------------------------------------------------
// Partial regression: compute adjusted Y for scatter plot
// ---------------------------------------------------------------------------

/**
 * Compute adjustedY = y - Σ(βₖ · factor_k) for each point.
 * The scatter plot then shows (x, adjustedY) with line y = β₁x + β₀.
 */
export function computeAdjustedPoints(
  points: MultiFactorScatterPoint[],
  result: MultiFactorRegressionResult,
): MultiFactorScatterPoint[] {
  const factorCoeffs = new Map(result.factors.map((f) => [f.name, f.coefficient]));

  return points.map((pt) => {
    let factorEffect = 0;
    if (pt.factorValues) {
      for (const [name, value] of Object.entries(pt.factorValues)) {
        const coeff = factorCoeffs.get(name);
        if (coeff !== undefined) {
          factorEffect += coeff * value;
        }
      }
    }
    return {
      ...pt,
      adjustedY: pt.y - factorEffect,
    };
  });
}
