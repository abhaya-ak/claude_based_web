import React, { useState, useEffect } from 'react';
import { triageApi } from '../../api/triage';
import type { VerifiedIndicator } from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { Modal } from '../../components/Modal';
import { Input } from '../../components/Input';
import { ShieldCheck, ShieldOff, Search, AlertCircle, RefreshCw } from 'lucide-react';
import { formatDate } from '../../lib/format';

export const IndicatorManagementPage: React.FC = () => {
  const [indicators, setIndicators] = useState<VerifiedIndicator[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Revocation state
  const [revokingItem, setRevokingItem] = useState<VerifiedIndicator | null>(null);
  const [revocationReason, setRevocationReason] = useState('');
  const [isSubmittingRevoke, setIsSubmittingRevoke] = useState(false);

  const fetchIndicators = async () => {
    setIsLoading(true);
    try {
      const data = await triageApi.getIndicators();
      setIndicators(data.results || []);
    } catch {
      setErrorMsg('Failed to load verified indicators.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchIndicators();
  }, []);

  const handleRevokeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!revokingItem || !revocationReason.trim()) return;

    setIsSubmittingRevoke(true);
    try {
      await triageApi.revokeIndicator(revokingItem.id, revocationReason.trim());
      setSuccessMsg(`Indicator "${revokingItem.display_value}" revoked successfully.`);
      setRevokingItem(null);
      setRevocationReason('');
      fetchIndicators();
    } catch {
      setErrorMsg('Failed to revoke indicator. Please verify your permissions.');
    } finally {
      setIsSubmittingRevoke(false);
    }
  };

  const filteredIndicators = indicators.filter((ind) =>
    ind.display_value.toLowerCase().includes(searchQuery.toLowerCase()) ||
    ind.indicator_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (ind.public_note && ind.public_note.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-emerald-600" />
            <span>Threat Intelligence Vault</span>
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Active indicators currently powering the real-time citizen lookup engine.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchIndicators}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {successMsg && (
        <Alert variant="success" onDismiss={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {errorMsg && (
        <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {/* Filter / Search Bar */}
      <div className="flex items-center gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
        <Search className="w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="Filter by indicator value, type, or note..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full text-sm outline-none placeholder:text-slate-400 bg-transparent"
        />
      </div>

      {/* Indicators Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Indicator</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Threat Level</th>
                <th className="py-3 px-4 text-center">Confidence</th>
                <th className="py-3 px-4 text-center">Reports</th>
                <th className="py-3 px-4">Confirmed Date</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredIndicators.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <AlertCircle className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="font-medium">No verified indicators found</p>
                    <p className="text-xs text-slate-400">Indicators verified by analysts will populate here automatically.</p>
                  </td>
                </tr>
              ) : (
                filteredIndicators.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      <div>{item.display_value}</div>
                      {item.public_note && (
                        <div className="text-xs font-sans text-slate-500 mt-0.5 line-clamp-1">
                          {item.public_note}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-700 border border-slate-200">
                        {item.indicator_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 text-xs font-black uppercase rounded ${
                          item.threat_level === 'HIGH'
                            ? 'bg-red-100 text-red-800 border border-red-200'
                            : item.threat_level === 'MEDIUM'
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        }`}
                      >
                        {item.threat_level}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center font-semibold text-slate-700">
                      {Math.round(item.confidence_score * 100)}%
                    </td>
                    <td className="py-3 px-4 text-center font-bold text-slate-900">
                      {item.report_count}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500 whitespace-nowrap">
                      {formatDate(item.first_confirmed_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {item.is_active ? (
                        <button
                          type="button"
                          onClick={() => setRevokingItem(item)}
                          className="inline-flex items-center gap-1 text-xs font-bold text-red-600 hover:text-red-800 hover:bg-red-50 px-2.5 py-1 rounded transition-colors"
                        >
                          <ShieldOff className="w-3.5 h-3.5" />
                          <span>Revoke</span>
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400 font-medium italic">Revoked</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Revoke Indicator Modal */}
      {revokingItem && (
        <Modal
          isOpen={true}
          onClose={() => setRevokingItem(null)}
          title="Revoke Verified Indicator"
        >
          <form onSubmit={handleRevokeSubmit} className="space-y-4">
            <p className="text-sm text-slate-600">
              Revoking this indicator removes it from the public high-risk threat lookup engine.
              This action requires an explicit audit justification reason.
            </p>

            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs space-y-1">
              <div><strong className="text-red-900">Indicator:</strong> <span className="font-mono">{revokingItem.display_value}</span></div>
              <div><strong className="text-red-900">Type:</strong> {revokingItem.indicator_type}</div>
            </div>

            <div>
              <label htmlFor="revokeReason" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Audit Revocation Reason *
              </label>
              <Input
                id="revokeReason"
                type="text"
                required
                placeholder="e.g., False positive confirmed by bank security team."
                value={revocationReason}
                onChange={(e) => setRevocationReason(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setRevokingItem(null)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="danger"
                isLoading={isSubmittingRevoke}
                disabled={!revocationReason.trim()}
              >
                Confirm Revocation
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
