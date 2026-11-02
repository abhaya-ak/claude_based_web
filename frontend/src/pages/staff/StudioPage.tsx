import React from 'react';
import { BookOpen } from 'lucide-react';

export const StudioPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-emerald-600" />
          <span>Literacy Studio</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Educator authoring workstation for educational guides, tactics, and simulator scenarios.
        </p>
      </div>

      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center py-16 space-y-3">
        <p className="text-sm font-medium text-slate-600">
          The Literacy Studio CMS connects to `/api/v1/studio/` in Slice F4.
        </p>
      </div>
    </div>
  );
};
