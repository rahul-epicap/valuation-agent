'use client';

import { useState, useRef } from 'react';
import { uploadExcel, getTemplateUrl } from '../lib/api';

interface UploadModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export default function UploadModal({ onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadExcel(file, name || undefined);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,.6)' }}>
      <div className="rounded-xl p-6 w-full max-w-md" style={{ background: 'var(--bg2)', border: '1px solid var(--brd)' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Upload Excel Data</h2>
          <button onClick={onClose} className="text-lg cursor-pointer" style={{ color: 'var(--t3)' }}>&times;</button>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--t2)' }}>
            Snapshot Name (optional)
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Q1 2026 Update"
            className="w-full outline-none"
            style={{
              background: 'var(--bg0)',
              border: '1px solid var(--brd)',
              color: 'var(--t1)',
              padding: '8px 10px',
              borderRadius: '7px',
              fontSize: '13px',
            }}
          />
        </div>

        <div
          className="mb-4 rounded-lg p-6 text-center cursor-pointer"
          style={{ border: '2px dashed var(--brd)', background: 'var(--bg0)' }}
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file ? (
            <p className="text-sm" style={{ color: 'var(--t1)' }}>{file.name}</p>
          ) : (
            <p className="text-sm" style={{ color: 'var(--t3)' }}>
              Click to select Excel file (.xlsx)
            </p>
          )}
        </div>

        {error && (
          <p className="text-xs mb-3" style={{ color: 'var(--red)' }}>{error}</p>
        )}

        <div className="flex items-center justify-between">
          <a
            href={getTemplateUrl()}
            className="text-xs underline"
            style={{ color: 'var(--t3)' }}
          >
            Download template
          </a>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs font-semibold cursor-pointer"
              style={{ background: 'var(--bg3)', color: 'var(--t2)', border: '1px solid var(--brd)' }}
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="px-3 py-1.5 rounded text-xs font-semibold"
              style={{
                background: file && !uploading ? 'var(--blue)' : 'var(--bg3)',
                color: file && !uploading ? '#fff' : 'var(--t3)',
                cursor: file && !uploading ? 'pointer' : 'not-allowed',
              }}
            >
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
