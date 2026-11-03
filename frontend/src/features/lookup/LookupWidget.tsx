import React, { useState } from 'react';
import { Search, ShieldAlert, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { reportsApi } from '../../api/reports';
import type { LookupResponse, VerdictLevel } from '../../api/schema';
import { Link } from 'react-router-dom';

export const LookupWidget: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<LookupResponse | null>(null);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setResult(null);

    try {
      const data = await reportsApi.lookup({ input: query.trim() });
      setResult(data);
    } catch {
      // Fallback
    } finally {
      setIsLoading(false);
    }
  };

  const getVerdictStyles = (verdict: VerdictLevel) => {
    switch (verdict) {
      case 'RED':
        return {
          container: 'bg-red-600 text-white',
          icon: <ShieldAlert className="w-6 h-6 text-white" />,
          title: 'Confirmed Threat Detected',
          desc: 'This contact is linked to confirmed scam operations. Do not transfer funds or share credentials.',
        };
      case 'YELLOW':
        return {
          container: 'bg-amber-500 text-black',
          icon: <AlertTriangle className="w-6 h-6 text-black" />,
          title: 'Suspicious Activity Detected',
          desc: 'Heuristic red flags or multiple pending reports reported for this indicator.',
        };
      case 'GREEN':
      default:
        return {
          container: 'bg-emerald-600 text-white',
          icon: <CheckCircle2 className="w-6 h-6 text-white" />,
          title: 'No Known Reports',
          desc: 'No threat intelligence recorded yet. Remain alert as new scams emerge constantly.',
        };
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-white rounded-2xl shadow-lg border border-slate-200 p-6 space-y-4">
      <div className="text-left space-y-1">
        <h2 className="text-base font-bold text-slate-900">Instant Threat Verification</h2>
        <p className="text-xs text-slate-500">
          Search suspicious phone numbers, URLs, bank accounts, or email addresses.
        </p>
      </div>

      <form onSubmit={handleLookup} className="flex flex-col sm:flex-row gap-2.5">
        <div className="flex-1">
          <Input
            id="widget-query"
            placeholder="e.g. +6012-345-6789 or https://deal-login.xyz"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button
          type="submit"
          isLoading={isLoading}
          leftIcon={<Search className="w-4 h-4" />}
        >
          Check Now
        </Button>
      </form>

      {result && (
        <div className="pt-2">
          {(() => {
            const v = getVerdictStyles(result.verdict);
            return (
              <div
                className={`p-4 rounded-xl flex items-start gap-3 text-left transition-all ${v.container}`}
                role="status"
                aria-live="polite"
              >
                <div className="mt-0.5">{v.icon}</div>
                <div className="flex-1 space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-sm">{v.title}</span>
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-black/20">
                      {result.verdict}
                    </span>
                  </div>
                  <p className="text-xs opacity-90 leading-relaxed">{v.desc}</p>

                  {result.verdict === 'RED' && (
                    <div className="pt-2">
                      <Link
                        to="/report"
                        className="inline-flex items-center gap-1 text-xs font-bold underline hover:opacity-80"
                      >
                        <span>Report an incident regarding this threat</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};
