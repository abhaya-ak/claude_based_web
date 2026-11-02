import React, { useState, useEffect } from 'react';
import { analyticsApi, type LossesByCurrency, type TacticBreakdown, type SpikeAlert, type VolumeDataPoint } from '../../api/analytics';
import { Button } from '../../components/Button';
import { TrendingUp, AlertTriangle, DollarSign, Activity, Flame } from 'lucide-react';
import { formatCurrency } from '../../lib/format';

export const TrendAnalyticsPage: React.FC = () => {
  const [losses, setLosses] = useState<LossesByCurrency[]>([]);
  const [tactics, setTactics] = useState<TacticBreakdown[]>([]);
  const [spikes, setSpikes] = useState<SpikeAlert[]>([]);
  const [volume, setVolume] = useState<VolumeDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchTrends = async () => {
    setIsLoading(true);
    try {
      const [lossRes, tacticRes, spikeRes, volRes] = await Promise.all([
        analyticsApi.getLosses(),
        analyticsApi.getTactics(),
        analyticsApi.getSpikes(),
        analyticsApi.getVolumeTrends(30),
      ]);
      setLosses(lossRes.losses || []);
      setTactics(tacticRes.tactics || []);
      setSpikes(spikeRes.spikes || []);
      setVolume(volRes.points || []);
    } catch {
      // Offline fallback defaults
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTrends();
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-slate-900" />
            <span>Fraud Trend Analytics & Spike Detection</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time pattern intelligence and +300% surge alerts across categories and financial vectors.
          </p>
        </div>

        <Button size="sm" variant="outline" onClick={fetchTrends} isLoading={isLoading}>
          Refresh Analytics
        </Button>
      </div>

      {/* Critical Spike Alerts Banner */}
      {spikes.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-red-600 flex items-center gap-1.5">
            <Flame className="w-4 h-4 text-red-600" />
            <span>Critical Surge Alerts (+300% Volume Spike)</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {spikes.map((spike, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3 text-red-950"
              >
                <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <strong className="text-sm font-bold uppercase">{spike.category}</strong>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-600 text-white">
                      +{spike.percentage_increase}% Surge
                    </span>
                  </div>
                  <p className="text-xs text-slate-700">
                    Volume accelerated from {spike.baseline_count} baseline reports to {spike.current_count} active reports.
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analytics KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Losses Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Cumulative Loss</span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>

          <div className="space-y-2">
            {losses.length === 0 ? (
              <p className="text-xs text-slate-400">No losses recorded in active window.</p>
            ) : (
              losses.map((l, i) => (
                <div key={i} className="flex justify-between items-baseline border-b border-slate-50 pb-2">
                  <span className="text-xs font-semibold text-slate-600">{l.currency}</span>
                  <strong className="text-lg font-bold text-slate-900">
                    {formatCurrency(l.total_loss, l.currency)}
                  </strong>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Tactic Distribution Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Top Deception Tactics</span>
            <Activity className="w-4 h-4 text-blue-600" />
          </div>

          <div className="space-y-2">
            {tactics.length === 0 ? (
              <p className="text-xs text-slate-400">Tactic telemetry calibrating...</p>
            ) : (
              tactics.slice(0, 4).map((t, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-slate-700">{t.tactic}</span>
                    <span className="font-bold text-slate-900">{t.percentage}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-slate-900 h-1.5 rounded-full"
                      style={{ width: `${t.percentage}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Volume Trend summary */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Incident Velocity</span>
            <TrendingUp className="w-4 h-4 text-purple-600" />
          </div>

          <div className="space-y-2">
            <div className="text-3xl font-extrabold text-slate-900">
              {volume.reduce((acc, curr) => acc + curr.count, 0)}
            </div>
            <p className="text-xs text-slate-500">Total reports submitted in past 30 days.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
