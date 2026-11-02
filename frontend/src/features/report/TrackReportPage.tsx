import React, { useState } from 'react';
import { COPY } from '../../lib/copy';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { reportsApi } from '../../api/reports';
import type { TrackReportResponse } from '../../api/schema';
import { parseApiError } from '../../api/errors';
import { Search } from 'lucide-react';
import { formatDate } from '../../lib/format';

export const TrackReportPage: React.FC = () => {
  const [referenceCode, setReferenceCode] = useState('');
  const [accessKey, setAccessKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<TrackReportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!referenceCode.trim() || !accessKey.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const data = await reportsApi.trackReport({
        reference_code: referenceCode.trim().toUpperCase(),
        access_key: accessKey.trim(),
      });
      setResult(data);
    } catch (err) {
      const parsed = parseApiError(err);
      if (parsed.status === 404) {
        setErrorMsg('Invalid reference code or access key. Please double check your records.');
      } else {
        setErrorMsg(parsed.message || 'Unable to retrieve incident status.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.report.trackReportTitle}</h1>
        <p className="text-slate-600 text-sm">
          Check the review progress and active advisories for your submitted report.
        </p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
        {errorMsg && (
          <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        <form onSubmit={handleTrack} className="space-y-4">
          <Input
            id="track-ref"
            label={COPY.report.referenceLabel}
            placeholder="e.g. SCM-2026-X7K9P2M4"
            required
            value={referenceCode}
            onChange={(e) => setReferenceCode(e.target.value)}
          />

          <Input
            id="track-key"
            label={COPY.report.accessKeyLabel}
            placeholder="Enter the 128-bit key provided upon submission"
            required
            value={accessKey}
            onChange={(e) => setAccessKey(e.target.value)}
          />

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isLoading}
            leftIcon={<Search className="w-4 h-4" />}
          >
            {COPY.report.trackButton}
          </Button>
        </form>

        {result && (
          <div className="pt-6 border-t border-slate-200 space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="text-xs uppercase font-bold text-slate-500">Status</span>
                <p className="text-lg font-bold text-slate-900">{result.status}</p>
              </div>
              <div>
                <span className="text-xs uppercase font-bold text-slate-500">Submitted</span>
                <p className="text-sm font-medium text-slate-700">{formatDate(result.created_at)}</p>
              </div>
            </div>

            {result.playbook && (
              <div className="space-y-3 pt-2">
                <h3 className="font-bold text-slate-900 text-sm">{result.playbook.title}</h3>
                <div className="space-y-2">
                  {result.playbook.steps.map((st, i) => (
                    <div key={i} className="p-3 rounded bg-blue-50 text-xs text-slate-800">
                      <strong>{st.title}: </strong>
                      <span>{st.detail}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
