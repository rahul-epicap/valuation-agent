'use client';

import { useEffect } from 'react';

interface MobileSidebarProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export default function MobileSidebar({ open, onClose, children }: MobileSidebarProps) {
  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = ''; };
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="md:hidden fixed inset-0 z-40">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        className="absolute top-0 left-0 bottom-0 w-72 overflow-y-auto"
        style={{ background: 'var(--bg1)' }}
      >
        <div className="flex items-center justify-between p-3" style={{ borderBottom: '1px solid var(--brd)' }}>
          <span className="text-sm font-bold" style={{ color: 'var(--t1)' }}>Filters</span>
          <button
            onClick={onClose}
            className="p-1 rounded cursor-pointer"
            style={{ color: 'var(--t3)' }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
