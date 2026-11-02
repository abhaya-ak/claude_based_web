import React from 'react';
import { COPY } from '../lib/copy';
import { BookOpen } from 'lucide-react';

export const LiteracyPage: React.FC = () => {
  return (
    <div className="max-w-5xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.literacy.title}</h1>
        <p className="text-slate-600">{COPY.literacy.subtitle}</p>
      </div>

      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center py-16 space-y-4">
        <BookOpen className="w-12 h-12 text-slate-400 mx-auto" />
        <h2 className="text-lg font-bold text-slate-800">Educational Guides & Curated Content</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Tactical playbooks, elder fraud prevention, and teen digital safety modules connect here in Slice F4.
        </p>
      </div>
    </div>
  );
};
