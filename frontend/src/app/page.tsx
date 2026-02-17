'use client';

import { useState, useEffect, useCallback } from 'react';
import { DashboardData, SnapshotMeta } from '../lib/types';
import { fetchDashboardData, fetchSnapshots, triggerBloombergUpdate } from '../lib/api';
import { useDashboardState } from '../hooks/useDashboardState';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import RegressionChart from '../components/RegressionChart';
import MultiplesChart from '../components/MultiplesChart';
import SlopeChart from '../components/SlopeChart';
import InterceptChart from '../components/InterceptChart';
import ChartContainer from '../components/ChartContainer';
import UploadModal from '../components/UploadModal';
import ValueScoreView from '../components/ValueScoreView';
import DcfView from '../components/DcfView';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [activeSnapshotId, setActiveSnapshotId] = useState<number | undefined>();
  const [updating, setUpdating] = useState(false);

  const loadData = useCallback(async (snapshotId?: number) => {
    try {
      setLoading(true);
      setError(null);
      const [dashData, snaps] = await Promise.all([
        fetchDashboardData(snapshotId),
        fetchSnapshots(),
      ]);
      setData(dashData);
      setSnapshots(snaps);
      setActiveSnapshotId(snapshotId || snaps[0]?.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSnapshotChange = (id: number) => {
    setActiveSnapshotId(id);
    loadData(id);
  };

  const handleUploadSuccess = () => {
    setShowUpload(false);
    loadData();
  };

  const handleUpdate = async () => {
    try {
      setUpdating(true);
      const resp = await triggerBloombergUpdate();
      if (resp.skipped) {
        alert(resp.message || 'No new trading days since last snapshot');
      }
      await loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Bloomberg update failed');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center" style={{ background: 'var(--bg0)' }}>
        <p className="text-sm animate-pulse" style={{ color: 'var(--t2)' }}>
          Loading Epicenter Valuation Dashboard…
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center gap-4" style={{ background: 'var(--bg0)' }}>
        <p className="text-sm" style={{ color: 'var(--t2)' }}>
          {error || 'No data available'}
        </p>
        <button
          onClick={() => setShowUpload(true)}
          className="px-4 py-2 rounded text-sm font-semibold cursor-pointer"
          style={{ background: 'var(--blue)', color: '#fff' }}
        >
          Upload Excel Data
        </button>
        {showUpload && (
          <UploadModal
            onClose={() => setShowUpload(false)}
            onSuccess={handleUploadSuccess}
          />
        )}
      </div>
    );
  }

  return (
    <DashboardContent
      data={data}
      snapshots={snapshots}
      activeSnapshotId={activeSnapshotId}
      onSnapshotChange={handleSnapshotChange}
      onUploadClick={() => setShowUpload(true)}
      onUpdateClick={handleUpdate}
      updating={updating}
      showUpload={showUpload}
      onUploadClose={() => setShowUpload(false)}
      onUploadSuccess={handleUploadSuccess}
    />
  );
}

function DashboardContent({
  data,
  snapshots,
  activeSnapshotId,
  onSnapshotChange,
  onUploadClick,
  onUpdateClick,
  updating,
  showUpload,
  onUploadClose,
  onUploadSuccess,
}: {
  data: DashboardData;
  snapshots: SnapshotMeta[];
  activeSnapshotId?: number;
  onSnapshotChange: (id: number) => void;
  onUploadClick: () => void;
  onUpdateClick: () => void;
  updating: boolean;
  showUpload: boolean;
  onUploadClose: () => void;
  onUploadSuccess: () => void;
}) {
  const { state, dispatch, allIndustries } = useDashboardState(data);

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg0)' }}>
      <Header
        data={data}
        state={state}
        dispatch={dispatch}
        snapshots={snapshots}
        activeSnapshotId={activeSnapshotId}
        onSnapshotChange={onSnapshotChange}
        onUploadClick={onUploadClick}
        onUpdateClick={onUpdateClick}
        updating={updating}
      />
      <div className="grid" style={{ gridTemplateColumns: '260px 1fr', height: 'calc(100vh - 53px)' }}>
        <Sidebar
          data={data}
          state={state}
          dispatch={dispatch}
          allIndustries={allIndustries}
        />
        <main className="overflow-y-auto" style={{ padding: '16px 20px' }}>
          {state.view === 'regression' ? (
            <ValueScoreView data={data} state={state} dispatch={dispatch} />
          ) : state.view === 'dcf' ? (
            <DcfView data={data} state={state} dispatch={dispatch} />
          ) : (
            <>
              <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
                <RegressionChart data={data} state={state} dispatch={dispatch} />
              </div>
              <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
                  <ChartContainer dates={data.dates}>
                    {({ startDi, endDi, chartHeight }) => (
                      <MultiplesChart data={data} state={state} dispatch={dispatch}
                        startDi={startDi} endDi={endDi} chartHeight={chartHeight} />
                    )}
                  </ChartContainer>
                </div>
                <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
                  <ChartContainer dates={data.dates}>
                    {({ startDi, endDi, chartHeight }) => (
                      <SlopeChart data={data} state={state} dispatch={dispatch}
                        startDi={startDi} endDi={endDi} chartHeight={chartHeight} />
                    )}
                  </ChartContainer>
                </div>
                <div className="rounded-xl p-4" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
                  <ChartContainer dates={data.dates}>
                    {({ startDi, endDi, chartHeight }) => (
                      <InterceptChart data={data} state={state} dispatch={dispatch}
                        startDi={startDi} endDi={endDi} chartHeight={chartHeight} />
                    )}
                  </ChartContainer>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
      {showUpload && (
        <UploadModal onClose={onUploadClose} onSuccess={onUploadSuccess} />
      )}
    </div>
  );
}
