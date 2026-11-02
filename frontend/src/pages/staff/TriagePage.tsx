import React from 'react';
import { ClipboardList } from 'lucide-react';

export const TriagePage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <ClipboardList className="w-6 h-6 text-gov-blue" />
          <span>Triage Workbench & Queue</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Analyst portal for reviewing pending incident clusters and verifying malicious indicators.
        </p>
      </div>

      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center py-16 space-y-3">
        <p className="text-sm font-medium text-slate-600">
          The Triage Queue interface connects to `/api/v1/triage/queue/` in Slice F3.
        </p>
      </div>
    </div>
  );
};
