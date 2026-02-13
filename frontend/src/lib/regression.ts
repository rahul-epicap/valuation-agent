import { RegressionResult } from './types';

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
