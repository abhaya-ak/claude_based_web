import React from 'react';
import { Sliders } from 'lucide-react';

export const AdminPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Sliders className="w-6 h-6 text-purple-600" />
          <span>System Administration Console</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Review staff registration applications, adjust heuristic scanner rules, and audit telemetry.
        </p>
      </div>

      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center py-16 space-y-3">
        <p className="text-sm font-medium text-slate-600">
          The Admin Console connects to `/api/v1/admin-portal/` in Slice F5.
        </p>
      </div>
    </div>
  );
};
