import React, { useState } from 'react';
import { COPY } from '../../lib/copy';
import { Search, ShieldAlert, CheckCircle2, AlertTriangle, ShieldQuestion } from 'lucide-react';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { reportsApi } from '../../api/reports';
import type { LookupResponse, VerdictLevel } from '../../api/schema';
import { parseApiError } from '../../api/errors';

export const LookupPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<LookupResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const data = await reportsApi.lookup({ input: query.trim() });
      setResult(data);
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Lookup verification query failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const getVerdictCard = (verdict: VerdictLevel) => {
    switch (verdict) {
      case 'RED':
        return {
          container: 'bg-red-600 text-white',
          badge: 'bg-white text-red-700 font-bold',
          icon: <ShieldAlert className="w-8 h-8 text-white" />,
          title: COPY.lookup.verdictRedTitle,
          description: COPY.lookup.verdictRedDesc,
        };
      case 'YELLOW':
        return {
          container: 'bg-amber-500 text-black',
          badge: 'bg-black text-amber-300 font-bold',
          icon: <AlertTriangle className="w-8 h-8 text-black" />,
          title: COPY.lookup.verdictYellowTitle,
          description: COPY.lookup.verdictYellowDesc,
        };
      case 'GREEN':
      default:
        return {
          container: 'bg-emerald-600 text-white',
          badge: 'bg-white text-emerald-700 font-bold',
          icon: <CheckCircle2 className="w-8 h-8 text-white" />,
          title: COPY.lookup.verdictGreenTitle,
          description: COPY.lookup.verdictGreenDesc,
        };
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
      <div className="text-center space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.lookup.title}</h1>
        <p className="text-slate-600 max-w-xl mx-auto">{COPY.lookup.subtitle}</p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
        <form onSubmit={handleLookup} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <Input
              id="lookup-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={COPY.lookup.searchPlaceholder}
              placeholder={COPY.lookup.searchPlaceholder}
            />
          </div>
          <Button
            type="submit"
            isLoading={isLoading}
            leftIcon={<Search className="w-4 h-4" />}
          >
            {COPY.lookup.searchButton}
          </Button>
        </form>

        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            {errorMsg}
          </div>
        )}

        {/* Verdict Results Display */}
        {result && (
          <div className="space-y-4 pt-2">
            {(() => {
              const card = getVerdictCard(result.verdict);
              return (
                <div
                  className={`p-6 rounded-xl shadow-md space-y-3 ${card.container}`}
                  role="region"
                  aria-live="polite"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {card.icon}
                      <div>
                        <span className={`px-2 py-0.5 text-xs rounded uppercase tracking-wider ${card.badge}`}>
                          Verdict: {result.verdict}
                        </span>
                        <h2 className="text-xl font-bold mt-1">{card.title}</h2>
                      </div>
                    </div>
                  </div>
                  <p className="text-sm opacity-90 leading-relaxed">{card.description}</p>
                </div>
              );
            })()}
          </div>
        )}

        <div className="border-t border-slate-100 pt-6">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
            <ShieldQuestion className="w-4 h-4" />
            <span>Supported Verification Formats</span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-slate-600">
            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <strong className="block text-slate-800">Phone Numbers</strong>
              +60 12-345-6789 (E.164)
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <strong className="block text-slate-800">Web Links & URLs</strong>
              https://scam-bank.top
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <strong className="block text-slate-800">Bank Accounts</strong>
              Masked digits check
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <strong className="block text-slate-800">Email Addresses</strong>
              officer@fake-police.com
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
