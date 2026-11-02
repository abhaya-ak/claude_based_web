import React from 'react';
import { COPY } from '../lib/copy';
import { Target } from 'lucide-react';
import { Button } from '../components/Button';

export const SimulatorPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.simulator.title}</h1>
        <p className="text-slate-600">{COPY.simulator.subtitle}</p>
      </div>

      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center py-16 space-y-5">
        <Target className="w-12 h-12 text-amber-600 mx-auto" />
        <h2 className="text-lg font-bold text-slate-800">5-Scenario Interactive Fraud Defense</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Test your detection reflexes against real-world SMS, banking, and social phishing threats.
        </p>
        <Button variant="primary">
          {COPY.simulator.startAttempt}
        </Button>
      </div>
    </div>
  );
};
