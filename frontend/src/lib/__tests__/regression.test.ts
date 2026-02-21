import { describe, it, expect } from 'vitest';
import {
  linearRegression,
  linearRegressionTrimmed,
  linearRegressionRobust,
  logLinearRegression,
  compareRegressionMethods,
} from '../regression';

// Helper: generate y = m*x + b with optional noise
function makeLine(
  m: number,
  b: number,
  xs: number[],
  noise: number[] = [],
): [number, number][] {
  return xs.map((x, i) => [x, m * x + b + (noise[i] ?? 0)]);
}

describe('linearRegression', () => {
  it('returns null for fewer than 3 points', () => {
    expect(linearRegression([[1, 2]])).toBeNull();
    expect(linearRegression([[1, 2], [3, 4]])).toBeNull();
  });

  it('fits a perfect line (y = 2x + 1)', () => {
    const pts = makeLine(2, 1, [0, 1, 2, 3, 4]);
    const result = linearRegression(pts)!;
    expect(result).not.toBeNull();
    expect(result.slope).toBeCloseTo(2, 10);
    expect(result.intercept).toBeCloseTo(1, 10);
    expect(result.r2).toBeCloseTo(1.0, 10);
    expect(result.n).toBe(5);
  });

  it('handles negative slope (y = -3x + 10)', () => {
    const pts = makeLine(-3, 10, [0, 1, 2, 3, 4]);
    const result = linearRegression(pts)!;
    expect(result.slope).toBeCloseTo(-3, 10);
    expect(result.intercept).toBeCloseTo(10, 10);
    expect(result.r2).toBeCloseTo(1.0, 10);
  });

  it('handles constant y (zero slope)', () => {
    const pts: [number, number][] = [[1, 5], [2, 5], [3, 5]];
    const result = linearRegression(pts)!;
    expect(result.slope).toBeCloseTo(0, 10);
    expect(result.intercept).toBeCloseTo(5, 10);
    // R² should be 0 when SST = 0
    expect(result.r2).toBe(0);
  });

  it('returns null for collinear x values', () => {
    const pts: [number, number][] = [[1, 2], [1, 4], [1, 6]];
    expect(linearRegression(pts)).toBeNull();
  });

  it('computes reasonable R² for noisy data', () => {
    const pts = makeLine(2, 1, [0, 1, 2, 3, 4], [0.1, -0.2, 0.15, -0.1, 0.05]);
    const result = linearRegression(pts)!;
    expect(result.r2).toBeGreaterThan(0.95);
    expect(result.r2).toBeLessThanOrEqual(1.0);
    expect(result.slope).toBeCloseTo(2, 0);
    expect(result.n).toBe(5);
  });
});

describe('linearRegressionTrimmed', () => {
  it('returns null for fewer than 3 points', () => {
    expect(linearRegressionTrimmed([[1, 2]])).toBeNull();
  });

  it('matches OLS on clean data', () => {
    const pts = makeLine(2, 1, [0, 1, 2, 3, 4]);
    const trimmed = linearRegressionTrimmed(pts)!;
    const ols = linearRegression(pts)!;
    expect(trimmed.slope).toBeCloseTo(ols.slope, 10);
    expect(trimmed.intercept).toBeCloseTo(ols.intercept, 10);
    expect(trimmed.nOriginal).toBe(5);
  });

  it('removes outliers and improves fit', () => {
    // Clean line with one extreme outlier
    const pts: [number, number][] = [
      [0, 1], [1, 3], [2, 5], [3, 7], [4, 9], // y = 2x + 1
      [2.5, 50], // massive outlier
    ];
    const ols = linearRegression(pts)!;
    const trimmed = linearRegressionTrimmed(pts)!;

    // Trimmed should have higher R² than OLS
    expect(trimmed.r2).toBeGreaterThan(ols.r2);
    // Trimmed slope should be closer to true slope (2.0)
    expect(Math.abs(trimmed.slope - 2)).toBeLessThan(Math.abs(ols.slope - 2));
    expect(trimmed.nOriginal).toBe(6);
    expect(trimmed.n).toBeLessThan(6); // At least one point removed
  });

  it('preserves all points when no outliers', () => {
    const pts = makeLine(1, 0, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    const trimmed = linearRegressionTrimmed(pts)!;
    expect(trimmed.n).toBe(10);
    expect(trimmed.nOriginal).toBe(10);
  });
});

describe('linearRegressionRobust', () => {
  it('returns null for fewer than 3 points', () => {
    expect(linearRegressionRobust([[1, 2]])).toBeNull();
  });

  it('matches OLS on clean data', () => {
    const pts = makeLine(2, 1, [0, 1, 2, 3, 4]);
    const robust = linearRegressionRobust(pts)!;
    expect(robust.slope).toBeCloseTo(2, 4);
    expect(robust.intercept).toBeCloseTo(1, 4);
    expect(robust.n).toBe(5);
  });

  it('is more robust to outliers than OLS', () => {
    const pts: [number, number][] = [
      [0, 1], [1, 3], [2, 5], [3, 7], [4, 9], // y = 2x + 1
      [2.5, 50], // massive outlier
    ];
    const ols = linearRegression(pts)!;
    const robust = linearRegressionRobust(pts)!;

    // Robust slope should be closer to true slope (2.0) than OLS
    expect(Math.abs(robust.slope - 2)).toBeLessThan(Math.abs(ols.slope - 2));
  });

  it('uses all n points (never removes)', () => {
    const pts: [number, number][] = [
      [0, 1], [1, 3], [2, 5], [3, 7], [4, 9],
      [2.5, 50],
    ];
    const robust = linearRegressionRobust(pts)!;
    expect(robust.n).toBe(6);
  });
});

describe('logLinearRegression', () => {
  it('returns null for fewer than 3 positive-y points', () => {
    expect(logLinearRegression([[1, -1], [2, -2], [3, -3]])).toBeNull();
    expect(logLinearRegression([[1, 1]])).toBeNull();
  });

  it('fits exponential data well', () => {
    // y = e^(0.5x + 1) => log(y) = 0.5x + 1
    const pts: [number, number][] = [0, 1, 2, 3, 4].map((x) => [
      x,
      Math.exp(0.5 * x + 1),
    ]);
    const result = logLinearRegression(pts)!;
    expect(result).not.toBeNull();
    expect(result.logSlope).toBeCloseTo(0.5, 8);
    expect(result.logIntercept).toBeCloseTo(1, 8);
    expect(result.r2).toBeCloseTo(1.0, 8);
  });

  it('filters out non-positive y values', () => {
    const pts: [number, number][] = [
      [0, -5], // should be filtered
      [1, 2],
      [2, 4],
      [3, 8],
      [4, 16],
    ];
    const result = logLinearRegression(pts)!;
    expect(result.n).toBe(4); // Only 4 valid points
  });

  it('returns logSlope and logIntercept fields', () => {
    const pts: [number, number][] = [[0, 1], [1, 2], [2, 4], [3, 8]];
    const result = logLinearRegression(pts)!;
    expect(result).toHaveProperty('logSlope');
    expect(result).toHaveProperty('logIntercept');
    expect(result.logSlope).toBe(result.slope);
    expect(result.logIntercept).toBe(result.intercept);
  });
});

describe('compareRegressionMethods', () => {
  it('returns empty array for insufficient data', () => {
    expect(compareRegressionMethods([[1, 2]])).toEqual([]);
  });

  it('returns all 4 methods for valid data', () => {
    const pts: [number, number][] = [
      [0, 2], [1, 4], [2, 6], [3, 8], [4, 10],
    ];
    const results = compareRegressionMethods(pts);
    expect(results).toHaveLength(4);

    const methods = results.map((r) => r.method);
    expect(methods).toContain('ols');
    expect(methods).toContain('trimmed');
    expect(methods).toContain('robust');
    expect(methods).toContain('logLinear');
  });

  it('includes predict functions that work', () => {
    const pts = makeLine(2, 1, [0, 1, 2, 3, 4]);
    const results = compareRegressionMethods(pts);

    for (const r of results) {
      expect(typeof r.predict).toBe('function');
      // All methods should predict something reasonable at x=1
      const pred = r.predict(1);
      expect(Number.isFinite(pred)).toBe(true);
    }

    // OLS predict should be exact for clean linear data
    const ols = results.find((r) => r.method === 'ols')!;
    expect(ols.predict(5)).toBeCloseTo(11, 8); // 2*5 + 1
  });

  it('tracks nOriginal correctly', () => {
    const pts: [number, number][] = [
      [0, 1], [1, 3], [2, 5], [3, 7], [4, 9], [2.5, 50],
    ];
    const results = compareRegressionMethods(pts);
    for (const r of results) {
      expect(r.nOriginal).toBe(6);
    }
  });

  it('skips logLinear when all y values are non-positive', () => {
    const pts: [number, number][] = [
      [0, -5], [1, -3], [2, -1],
    ];
    const results = compareRegressionMethods(pts);
    const methods = results.map((r) => r.method);
    expect(methods).not.toContain('logLinear');
  });
});
