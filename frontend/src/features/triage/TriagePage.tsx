import React, { useState, useEffect } from 'react';
import { triageApi } from '../../api/triage';
import type { ScamReport } from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { Modal } from '../../components/Modal';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import {
  ClipboardList,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Download,
  ExternalLink,
  Filter,
} from 'lucide-react';
import { formatCurrency, formatDate } from '../../lib/format';

export const TriagePage: React.FC = () => {
  const [reports, setReports] = useState<ScamReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<ScamReport | null>(null);
  const [evidenceUrls, setEvidenceUrls] = useState<Array<{ id: string; download_url: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState('');
  const [highPriorityOnly, setHighPriorityOnly] = useState(false);

  // Action Modals State
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [verifyThreatLevel, setVerifyThreatLevel] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('HIGH');
  const [verifyPublicNote, setVerifyPublicNote] = useState('');

  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('Insufficient or frivolous narrative provided.');

  const loadQueue = async () => {
    setIsLoading(true);
    try {
      const data = await triageApi.getQueue({
        category: categoryFilter || undefined,
        is_high_priority: highPriorityOnly ? true : undefined,
      });
      setReports(data.results || []);
      if (data.results?.length > 0) {
        setSelectedReport(data.results[0]);
        loadEvidence(data.results[0].id);
      } else {
        setSelectedReport(null);
        setEvidenceUrls([]);
      }
    } catch {
      setErrorMsg('Failed to fetch triage queue reports.');
    } finally {
      setIsLoading(false);
    }
  };

  const loadEvidence = async (reportId: string) => {
    try {
      const evidence = await triageApi.getEvidenceUrls(reportId);
      setEvidenceUrls(evidence.evidence_urls || []);
    } catch {
      setEvidenceUrls([]);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [categoryFilter, highPriorityOnly]);

  const handleSelectReport = (report: ScamReport) => {
    setSelectedReport(report);
    setActionSuccess(null);
    loadEvidence(report.id);
  };

  const handleConfirmVerify = async () => {
    if (!selectedReport) return;
    try {
      await triageApi.verifyReport(selectedReport.id, {
        threat_level: verifyThreatLevel,
        public_note: verifyPublicNote.trim() || undefined,
      });
      setActionSuccess(`Indicators verified at ${verifyThreatLevel} threat level.`);
      setIsVerifyModalOpen(false);
      setVerifyPublicNote('');
      loadQueue();
    } catch {
      setErrorMsg('Indicator verification failed.');
    }
  };

  const handleConfirmReject = async () => {
    if (!selectedReport) return;
    try {
      await triageApi.rejectReport(selectedReport.id, {
        rejection_reason: rejectReason,
      });
      setActionSuccess('Report rejected.');
      setIsRejectModalOpen(false);
      loadQueue();
    } catch {
      setErrorMsg('Rejection failed.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-slate-900" />
            <span>Analyst Triage Workbench</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Review incoming incident clusters, inspect evidence attachments, and publish verified intelligence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={loadQueue} isLoading={isLoading}>
            Refresh Queue
          </Button>
        </div>
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

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm text-xs">
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-600 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded border border-slate-300 p-1.5 text-xs text-slate-800"
          >
            <option value="">All Categories</option>
            <option value="PHISHING">Phishing</option>
            <option value="INVESTMENT">Investment</option>
            <option value="E_COMMERCE">E-Commerce</option>
            <option value="JOB">Job Scam</option>
            <option value="IMPERSONATION">Impersonation</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="priority-filter"
            type="checkbox"
            checked={highPriorityOnly}
            onChange={(e) => setHighPriorityOnly(e.target.checked)}
            className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
          />
          <label htmlFor="priority-filter" className="font-semibold text-slate-700 cursor-pointer">
            High Priority Only
          </label>
        </div>
      </div>

      {/* Investigation Split Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[550px]">
        {/* Left Panel: Queue List */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="p-3.5 bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-600 flex justify-between items-center">
            <span>Pending Incidents</span>
            <span className="bg-slate-200 text-slate-800 px-2 py-0.5 rounded-full text-[10px]">
              {reports.length}
            </span>
          </div>

          <div className="flex-1 divide-y divide-slate-100 overflow-y-auto max-h-[600px]">
            {reports.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No incident reports currently awaiting triage.
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
                  <ShieldAlert className="w-4 h-4 text-slate-700" />
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
                  onClick={() => setIsVerifyModalOpen(true)}
                >
                  Verify Threat (High)
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={<CheckCircle2 className="w-4 h-4 text-amber-500" />}
                  onClick={() => {
                    setVerifyThreatLevel('MEDIUM');
                    setIsVerifyModalOpen(true);
                  }}
                >
                  Verify Threat (Medium)
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  leftIcon={<XCircle className="w-4 h-4" />}
                  onClick={() => setIsRejectModalOpen(true)}
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

      {/* Verify Confirmation Modal */}
      <Modal
        isOpen={isVerifyModalOpen}
        onClose={() => setIsVerifyModalOpen(false)}
        title="Verify Cluster Indicators"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Confirming this threat will convert active indicators to <strong>{verifyThreatLevel}</strong> threat status and flag them on citizen lookup queries.
          </p>

          <Select
            id="modal-threat-level"
            label="Assigned Threat Level"
            value={verifyThreatLevel}
            onChange={(e) => setVerifyThreatLevel(e.target.value as 'HIGH' | 'MEDIUM' | 'LOW')}
            options={[
              { value: 'HIGH', label: 'HIGH — Confirmed malicious scam' },
              { value: 'MEDIUM', label: 'MEDIUM — Suspicious / High risk' },
              { value: 'LOW', label: 'LOW — Mild suspicion / Watchlist' },
            ]}
          />

          <Input
            id="modal-public-note"
            label="Public Investigation Note (Optional)"
            placeholder="e.g. Offender impersonated telecom customer care"
            value={verifyPublicNote}
            onChange={(e) => setVerifyPublicNote(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setIsVerifyModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmVerify}>
              Confirm Verification
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reject Modal */}
      <Modal
        isOpen={isRejectModalOpen}
        onClose={() => setIsRejectModalOpen(false)}
        title="Reject Incident Report"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Please select the justification rationale for rejecting this submission:
          </p>

          <Select
            id="modal-reject-reason"
            label="Rejection Rationale"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            options={[
              { value: 'Insufficient or frivolous narrative provided.', label: 'Insufficient Details' },
              { value: 'Duplicate report already submitted.', label: 'Duplicate Submission' },
              { value: 'Legitimate business transaction / Not fraud.', label: 'Not a Scam / Civil Dispute' },
              { value: 'Unverifiable contact indicators.', label: 'Invalid Indicators' },
            ]}
          />

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setIsRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleConfirmReject}>
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
