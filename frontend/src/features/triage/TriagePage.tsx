import React, { useState, useEffect } from 'react';
import { triageApi } from '../../api/triage';
import type { ScamReport } from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { ClipboardList, ShieldAlert, CheckCircle2, XCircle, Download, ExternalLink } from 'lucide-react';
import { formatCurrency, formatDate } from '../../lib/format';

export const TriagePage: React.FC = () => {
  const [reports, setReports] = useState<ScamReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<ScamReport | null>(null);
  const [evidenceUrls, setEvidenceUrls] = useState<Array<{ id: string; download_url: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadQueue = async () => {
    setIsLoading(true);
    try {
      const data = await triageApi.getQueue();
      setReports(data.results || []);
      if (data.results?.length > 0 && !selectedReport) {
        setSelectedReport(data.results[0]);
      }
    } catch {
      setErrorMsg('Failed to fetch triage queue reports.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleSelectReport = async (report: ScamReport) => {
    setSelectedReport(report);
    setActionSuccess(null);
    setEvidenceUrls([]);

    try {
      const evidence = await triageApi.getEvidenceUrls(report.id);
      setEvidenceUrls(evidence.evidence_urls || []);
    } catch {
      // Evidence not available or no permissions
    }
  };

  const handleVerify = async (threatLevel: 'HIGH' | 'MEDIUM' | 'LOW') => {
    if (!selectedReport) return;
    try {
      await triageApi.verifyReport(selectedReport.id, { threat_level: threatLevel });
      setActionSuccess(`Indicators verified at ${threatLevel} threat level.`);
      loadQueue();
    } catch {
      setErrorMsg('Verification failed.');
    }
  };

  const handleReject = async () => {
    if (!selectedReport) return;
    try {
      await triageApi.rejectReport(selectedReport.id, {
        rejection_reason: 'Frivolous or insufficient evidence provided.',
      });
      setActionSuccess('Report rejected.');
      loadQueue();
    } catch {
      setErrorMsg('Rejection failed.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-slate-900" />
            <span>Analyst Triage Workbench</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Review incoming incident clusters, inspect evidence attachments, and publish verified intelligence.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={loadQueue} isLoading={isLoading}>
          Refresh Queue
        </Button>
      </div>

      {actionSuccess && (
        <Alert variant="success" onDismiss={() => setActionSuccess(null)}>
          {actionSuccess}
        </Alert>
      )}

      {errorMsg && (
        <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {/* Investigation Split Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[550px]">
        {/* Left Panel: Queue List */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="p-3.5 bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-600">
            Pending Queue ({reports.length})
          </div>

          <div className="flex-1 divide-y divide-slate-100 overflow-y-auto max-h-[600px]">
            {reports.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No pending incident reports in queue.
              </div>
            ) : (
              reports.map((rep) => {
                const isSelected = selectedReport?.id === rep.id;
                return (
                  <div
                    key={rep.id}
                    onClick={() => handleSelectReport(rep)}
                    className={`p-4 cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-blue-50/70 border-l-4 border-slate-900'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex justify-between items-start text-xs mb-1">
                      <span className="font-mono font-bold text-slate-900">{rep.reference_code}</span>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-semibold">
                        {rep.category}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 line-clamp-2">{rep.message_text}</p>
                    <div className="flex justify-between items-center text-[11px] text-slate-400 mt-2">
                      <span>Loss: {formatCurrency(rep.financial_loss, rep.currency)}</span>
                      <span>{formatDate(rep.created_at)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Panel: Report Investigation & Evidence Vault */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between space-y-6">
          {selectedReport ? (
            <div className="space-y-6">
              <div className="flex justify-between items-start border-b border-slate-100 pb-4">
                <div>
                  <span className="text-xs uppercase font-bold text-slate-400">Selected Incident</span>
                  <h2 className="text-xl font-bold font-mono text-slate-900">
                    {selectedReport.reference_code}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 text-xs font-bold rounded bg-amber-100 text-amber-800">
                    {selectedReport.status}
                  </span>
                </div>
              </div>

              {/* Narrative & Loss */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Victim Narrative
                </h3>
                <p className="text-sm text-slate-800 bg-slate-50 p-4 rounded-lg leading-relaxed whitespace-pre-wrap">
                  {selectedReport.message_text}
                </p>
                <div className="text-xs text-slate-600">
                  <strong>Reported Loss: </strong>
                  <span>{formatCurrency(selectedReport.financial_loss, selectedReport.currency)}</span>
                  <span className="mx-2">|</span>
                  <strong>Platform: </strong>
                  <span>{selectedReport.platform}</span>
                </div>
              </div>

              {/* Evidence Vault */}
              <div className="space-y-2 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4" />
                  <span>Presigned Evidence Attachments (15-Min TTL)</span>
                </h3>
                {evidenceUrls.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No evidence files attached to this incident.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {evidenceUrls.map((ev, idx) => (
                      <a
                        key={ev.id}
                        href={ev.download_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Evidence #{idx + 1}</span>
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </a>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="border-t border-slate-100 pt-4 flex flex-wrap gap-3">
                <Button
                  size="sm"
                  variant="primary"
                  leftIcon={<CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  onClick={() => handleVerify('HIGH')}
                >
                  Verify Threat (High)
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={<CheckCircle2 className="w-4 h-4 text-amber-500" />}
                  onClick={() => handleVerify('MEDIUM')}
                >
                  Verify Threat (Medium)
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  leftIcon={<XCircle className="w-4 h-4" />}
                  onClick={handleReject}
                >
                  Reject Report
                </Button>
              </div>
            </div>
          ) : (
            <div className="m-auto text-center text-slate-400 text-sm">
              Select an incident from the queue to inspect details and verify indicators.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
