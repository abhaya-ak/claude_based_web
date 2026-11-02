import React from 'react';
import { COPY } from '../lib/copy';
import { Button } from '../components/Button';
import { FileText } from 'lucide-react';

export const ReportPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.report.title}</h1>
        <p className="text-slate-600">{COPY.report.subtitle}</p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-900">
          <p className="font-semibold mb-1">Confidential & Protected Submission</p>
          <p className="text-xs text-blue-800">
            You may choose to submit anonymously or link to your verified account. Evidence files are encrypted and processed in isolated vaults.
          </p>
        </div>

        <div className="text-center py-10 space-y-4">
          <FileText className="w-12 h-12 text-slate-400 mx-auto" />
          <p className="text-sm font-medium text-slate-600">
            Multi-step incident submission wizard initializes in Slice F2.
          </p>
          <Button variant="secondary" onClick={() => window.history.back()}>
            {COPY.common.back}
          </Button>
        </div>
      </div>
    </div>
  );
};
