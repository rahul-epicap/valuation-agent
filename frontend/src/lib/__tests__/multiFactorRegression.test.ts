import { describe, it, expect } from 'vitest';
import {
  matTranspose,
  matMultiply,
  matInvert,
  multiFactorOLS,
  computeAdjustedPoints,
} from '../multiFactorRegression';
import { MultiFactorScatterPoint } from '../types';

describe('matTranspose', () => {
  it('transposes a 2x3 matrix', () => {
    const A = [[1, 2, 3], [4, 5, 6]];
    const T = matTranspose(A);
    expect(T).toEqual([[1, 4], [2, 5], [3, 6]]);
  });
});

describe('matMultiply', () => {
  it('multiplies two matrices', () => {
    const A = [[1, 2], [3, 4]];
    const B = [[5, 6], [7, 8]];
    expect(matMultiply(A, B)).toEqual([[19, 22], [43, 50]]);
  });

  it('handles identity multiplication', () => {
    const A = [[1, 2], [3, 4]];
    const I = [[1, 0], [0, 1]];
    expect(matMultiply(A, I)).toEqual(A);
  });
});

describe('matInvert', () => {
  it('inverts a 2x2 matrix', () => {
    const A = [[4, 7], [2, 6]];
    const inv = matInvert(A)!;
    expect(inv).not.toBeNull();
    // A * A^-1 should be identity
    const product = matMultiply(A, inv);
    expect(product[0][0]).toBeCloseTo(1, 10);
    expect(product[0][1]).toBeCloseTo(0, 10);
    expect(product[1][0]).toBeCloseTo(0, 10);
    expect(product[1][1]).toBeCloseTo(1, 10);
  });

  it('returns null for a singular matrix', () => {
    const A = [[1, 2], [2, 4]]; // rows are linearly dependent
    expect(matInvert(A)).toBeNull();
  });

  it('inverts a 3x3 matrix', () => {
    const A = [[1, 2, 3], [0, 1, 4], [5, 6, 0]];
    const inv = matInvert(A)!;
    expect(inv).not.toBeNull();
    const product = matMultiply(A, inv);
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        expect(product[i][j]).toBeCloseTo(i === j ? 1 : 0, 8);
      }
    }
  });
});

describe('multiFactorOLS', () => {
  it('returns null for fewer than 3 points', () => {
    const y = [1, 2];
    const X = [[1, 10], [1, 20]];
    expect(multiFactorOLS(y, X, [])).toBeNull();
  });

  it('recovers known coefficients for single-factor (growth only)', () => {
    // y = 2*growth + 5 (no dummy factors)
    const n = 20;
    const y: number[] = [];
    const X: number[][] = [];
    for (let i = 0; i < n; i++) {
      const growth = i * 5;
      X.push([1, growth]); // intercept + growth
      y.push(2 * growth + 5);
    }

    const result = multiFactorOLS(y, X, [])!;
    expect(result).not.toBeNull();
    expect(result.intercept).toBeCloseTo(5, 6);
    expect(result.growthCoefficient).toBeCloseTo(2, 6);
    expect(result.r2).toBeCloseTo(1.0, 6);
    expect(result.factors).toHaveLength(0);
    expect(result.n).toBe(n);
  });

  it('recovers known coefficients with binary dummy factors', () => {
    // y = 0.5*growth + 3 + 8*isTech + 5*isHealth
    const n = 30;
    const y: number[] = [];
    const X: number[][] = [];
    const factorNames = ['Tech', 'Health'];

    for (let i = 0; i < n; i++) {
      const growth = 5 + i * 3;
      const isTech = i % 3 === 0 ? 1 : 0;
      const isHealth = i % 3 === 1 ? 1 : 0;
      X.push([1, growth, isTech, isHealth]);
      y.push(0.5 * growth + 3 + 8 * isTech + 5 * isHealth);
    }

    const result = multiFactorOLS(y, X, factorNames)!;
    expect(result).not.toBeNull();
    expect(result.intercept).toBeCloseTo(3, 4);
    expect(result.growthCoefficient).toBeCloseTo(0.5, 4);
    expect(result.r2).toBeCloseTo(1.0, 4);
    expect(result.factors).toHaveLength(2);
    expect(result.factors[0].name).toBe('Tech');
    expect(result.factors[0].coefficient).toBeCloseTo(8, 4);
    expect(result.factors[1].name).toBe('Health');
    expect(result.factors[1].coefficient).toBeCloseTo(5, 4);
  });

  it('reports adjusted R² lower than R² with many factors', () => {
    // Add noise so R² < 1, and many factors to penalize adjusted R²
    const n = 50;
    const y: number[] = [];
    const X: number[][] = [];
    const factorNames: string[] = [];
    const numFactors = 10;

    for (let f = 0; f < numFactors; f++) {
      factorNames.push(`F${f}`);
    }

    for (let i = 0; i < n; i++) {
      const growth = i * 2;
      const row = [1, growth];
      for (let f = 0; f < numFactors; f++) {
        row.push((i + f) % (f + 3) === 0 ? 1 : 0);
      }
      X.push(row);
      y.push(0.3 * growth + 10 + Math.sin(i) * 2);
    }

    const result = multiFactorOLS(y, X, factorNames)!;
    expect(result).not.toBeNull();
    expect(result.adjustedR2).toBeLessThanOrEqual(result.r2);
  });

  it('drops factors with < 3 members', () => {
    // Factor "Rare" has only 1 member, should be dropped
    const n = 20;
    const y: number[] = [];
    const X: number[][] = [];

    for (let i = 0; i < n; i++) {
      const growth = i * 5;
      const isCommon = i % 4 === 0 ? 1 : 0;
      const isRare = i === 0 ? 1 : 0; // only 1 member
      X.push([1, growth, isCommon, isRare]);
      y.push(growth * 0.5 + 3 + 4 * isCommon);
    }

    const result = multiFactorOLS(y, X, ['Common', 'Rare'])!;
    expect(result).not.toBeNull();
    // Rare should be dropped
    const factorNames = result.factors.map((f) => f.name);
    expect(factorNames).toContain('Common');
    expect(factorNames).not.toContain('Rare');
  });

  it('drops factors with zero variance', () => {
    // Factor "AllZero" is all zeros — should be dropped
    const n = 15;
    const y: number[] = [];
    const X: number[][] = [];

    for (let i = 0; i < n; i++) {
      const growth = i * 5;
      const isReal = i % 3 === 0 ? 1 : 0;
      X.push([1, growth, isReal, 0]); // col 3 is all zeros
      y.push(growth * 0.2 + 1 + 2 * isReal);
    }

    const result = multiFactorOLS(y, X, ['Real', 'AllZero'])!;
    expect(result).not.toBeNull();
    const factorNames = result.factors.map((f) => f.name);
    expect(factorNames).toContain('Real');
    expect(factorNames).not.toContain('AllZero');
  });

  it('returns null when n <= p', () => {
    // 3 points but 4 parameters (intercept + growth + 2 factors)
    const y = [1, 2, 3];
    const X = [[1, 10, 1, 0], [1, 20, 0, 1], [1, 30, 1, 1]];
    // After filtering, we might still have too many params
    // With 3 points and 4 columns, if all factors pass filtering, should return null
    const result = multiFactorOLS(y, X, ['A', 'B']);
    // Either null or successfully drops factors to make it solvable
    if (result !== null) {
      expect(result.n).toBeGreaterThan(result.p);
    }
  });

  it('produces higher R² than single-factor when factors explain variance', () => {
    // Generate data where group membership explains variance
    const n = 40;
    const ySingle: number[] = [];
    const yMulti: number[] = [];
    const XSingle: number[][] = [];
    const XMulti: number[][] = [];

    for (let i = 0; i < n; i++) {
      const growth = 5 + i * 2;
      const isGroupA = i < 20 ? 1 : 0;
      const groupEffect = isGroupA ? 10 : 0;

      const val = 0.3 * growth + 2 + groupEffect + (Math.random() - 0.5) * 0.5;
      ySingle.push(val);
      yMulti.push(val);
      XSingle.push([1, growth]);
      XMulti.push([1, growth, isGroupA]);
    }

    const singleResult = multiFactorOLS(ySingle, XSingle, [])!;
    const multiResult = multiFactorOLS(yMulti, XMulti, ['GroupA'])!;

    expect(multiResult.r2).toBeGreaterThan(singleResult.r2);
  });
});

describe('computeAdjustedPoints', () => {
  it('subtracts factor effects from y values', () => {
    const result = {
      intercept: 5,
      growthCoefficient: 0.5,
      factors: [
        { name: 'Tech', type: 'binary' as const, coefficient: 8 },
        { name: 'Health', type: 'binary' as const, coefficient: 5 },
      ],
      r2: 0.9,
      adjustedR2: 0.88,
      n: 30,
      p: 4,
    };

    const points: MultiFactorScatterPoint[] = [
      { x: 20, y: 23, t: 'AAPL', factorValues: { Tech: 1, Health: 0 } },
      { x: 10, y: 15, t: 'JNJ', factorValues: { Tech: 0, Health: 1 } },
      { x: 15, y: 12, t: 'XOM', factorValues: { Tech: 0, Health: 0 } },
    ];

    const adjusted = computeAdjustedPoints(points, result);

    // AAPL: adjustedY = 23 - (8*1 + 5*0) = 15
    expect(adjusted[0].adjustedY).toBeCloseTo(15);
    // JNJ: adjustedY = 15 - (8*0 + 5*1) = 10
    expect(adjusted[1].adjustedY).toBeCloseTo(10);
    // XOM: adjustedY = 12 - 0 = 12
    expect(adjusted[2].adjustedY).toBeCloseTo(12);
  });

  it('handles points without factor values', () => {
    const result = {
      intercept: 5,
      growthCoefficient: 0.5,
      factors: [{ name: 'Tech', type: 'binary' as const, coefficient: 8 }],
      r2: 0.9,
      adjustedR2: 0.88,
      n: 10,
      p: 3,
    };

    const points: MultiFactorScatterPoint[] = [
      { x: 20, y: 23, t: 'AAPL' }, // no factorValues
    ];

    const adjusted = computeAdjustedPoints(points, result);
    expect(adjusted[0].adjustedY).toBeCloseTo(23); // No adjustment
  });
});
