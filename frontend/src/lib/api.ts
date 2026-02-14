import { DashboardData, SnapshotMeta } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export async function fetchDashboardData(snapshotId?: number): Promise<DashboardData> {
  const url = snapshotId
    ? `${API_BASE}/api/dashboard-data/${snapshotId}`
    : `${API_BASE}/api/dashboard-data`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch dashboard data: ${res.status}`);
  return res.json();
}

export async function fetchSnapshots(): Promise<SnapshotMeta[]> {
  const res = await fetch(`${API_BASE}/api/snapshots`);
  if (!res.ok) throw new Error(`Failed to fetch snapshots: ${res.status}`);
  return res.json();
}

export async function uploadExcel(file: File, name?: string): Promise<SnapshotMeta> {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export function getTemplateUrl(): string {
  return `${API_BASE}/api/template`;
}

export interface BloombergUpdateResponse {
  id: number | null;
  skipped: boolean;
  message?: string;
  date_count: number;
  ticker_count?: number;
  industry_count?: number;
  previous_date_count?: number;
}

export async function triggerBloombergUpdate(
  lookbackDays: number = 5,
): Promise<BloombergUpdateResponse> {
  const res = await fetch(`${API_BASE}/api/bloomberg/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lookback_days: lookbackDays, periodicity: 'DAILY' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Bloomberg update failed' }));
    throw new Error(err.detail || 'Bloomberg update failed');
  }
  return res.json();
}
