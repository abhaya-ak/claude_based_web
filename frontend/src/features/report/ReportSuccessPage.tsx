import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { CreateReportResponse } from '../../api/schema';
import { Button } from '../../components/Button';
import { ShieldCheck, Copy, Check, Download, AlertTriangle, PhoneCall } from 'lucide-react';

export interface ReportSuccessPageProps {
  reportData?: CreateReportResponse;
}

export const ReportSuccessPage: React.FC<ReportSuccessPageProps> = ({ reportData: propData }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const reportData = propData || (location.state as { report?: CreateReportResponse })?.report;

  const [hasAcknowledged, setHasAcknowledged] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  if (!reportData) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <h1 className="text-xl font-bold text-slate-900">No Report Submission Found</h1>
        <p className="text-sm text-slate-600">Please submit an incident report first.</p>
        <Button onClick={() => navigate('/report')}>Go to Report Wizard</Button>
      </div>
    );
  }

  const { reference_code, access_key, playbook } = reportData;

  const handleCopy = () => {
    if (!access_key) return;
    navigator.clipboard.writeText(access_key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const handleDownload = () => {
    if (!access_key) return;
    const content = `SCAMSHIELD INCIDENT RECEIPT\nReference Code: ${reference_code}\nAccess Key: ${access_key}\nDate: ${new Date().toISOString()}\n\nKeep this access key confidential to check your report status at /track.\n`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scamshield-${reference_code}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isContinueDisabled = !!access_key && !hasAcknowledged;

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-md space-y-6">
        {/* Success Header */}
        <div className="flex items-center gap-3 text-emerald-600 border-b border-slate-100 pb-4">
          <div className="p-2.5 bg-emerald-50 rounded-xl">
            <ShieldCheck className="w-8 h-8" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">Incident Report Submitted</h1>
            <p className="text-xs text-slate-500">Your report has been queued for analyst triage.</p>
          </div>
        </div>

        {/* Reference & Access Key Receipt Box */}
        <div className="p-5 bg-slate-50 border border-slate-200 rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Reference Code:
            </span>
            <strong className="font-mono text-lg text-slate-900 bg-white px-3.5 py-1.5 rounded-lg border border-slate-300 shadow-sm w-fit">
              {reference_code}
            </strong>
          </div>

          {/* Anonymous One-Time Access Key */}
          {access_key && (
            <div className="pt-4 border-t border-slate-200 space-y-3">
              <div className="flex items-start gap-2 text-xs font-semibold text-amber-800 bg-amber-50 p-3 rounded-lg border border-amber-200">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Single-View Access Key:</strong> This key is generated once and will NEVER be shown again. It is required to track investigation status anonymously.
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <code className="bg-slate-900 text-amber-300 px-3.5 py-2 rounded-lg font-mono text-sm tracking-wide select-all break-all">
                  {access_key}
                </code>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCopy}
                    leftIcon={copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  >
                    {copiedKey ? 'Copied' : 'Copy'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDownload}
                    leftIcon={<Download className="w-3.5 h-3.5" />}
                  >
                    Download .txt
                  </Button>
                </div>
              </div>

              {/* Mandatory Acknowledgment Checkbox */}
              <div className="flex items-start gap-2.5 pt-2">
                <input
                  id="ack-access-key"
                  type="checkbox"
                  checked={hasAcknowledged}
                  onChange={(e) => setHasAcknowledged(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900 mt-0.5"
                />
                <label
                  htmlFor="ack-access-key"
                  className="text-xs font-semibold text-slate-800 cursor-pointer select-none leading-relaxed"
                >
                  I have securely saved my Access Key. I understand that if I lose it, I will not be able to track this report.
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Personalized Recovery Playbook */}
        {playbook && (
          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h2 className="text-base font-bold text-slate-900">
              {playbook.title || 'Immediate Incident Recovery Actions'}
            </h2>

            <div className="space-y-2.5">
              {playbook.steps?.map((stepItem, idx) => (
                <div key={idx} className="p-4 rounded-xl bg-blue-50/60 border border-blue-100 text-sm">
                  <h3 className="font-bold text-slate-900 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] inline-flex items-center justify-center font-mono">
                      {idx + 1}
                    </span>
                    <span>{stepItem.title}</span>
                  </h3>
                  <p className="text-slate-700 mt-1.5 text-xs leading-relaxed pl-7">
                    {stepItem.detail}
                  </p>
                </div>
              ))}
            </div>

            {/* Emergency Hotline Info */}
            {playbook.hotlines && playbook.hotlines.length > 0 && (
              <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200/80 text-xs text-amber-950 space-y-2">
                <h4 className="font-bold flex items-center gap-1.5">
                  <PhoneCall className="w-4 h-4 text-amber-700" />
                  <span>Official Emergency Fraud Assistance Hotlines:</span>
                </h4>
                <div className="flex flex-wrap gap-4 pt-1">
                  {playbook.hotlines.map((hl, i) => (
                    <div key={i} className="font-medium">
                      <strong>{hl.name}: </strong>
                      <span className="font-bold text-red-700">{hl.number}</span>
                      {hl.hours && <span className="text-slate-500 text-[10px]"> ({hl.hours})</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation Actions */}
        <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row justify-between items-center gap-3">
          <Button
            variant="outline"
            onClick={() => navigate('/report')}
          >
            Submit Another Report
          </Button>

          <Button
            disabled={isContinueDisabled}
            onClick={() => navigate('/')}
          >
            Continue to Home
          </Button>
        </div>
      </div>
    </div>
  );
};
