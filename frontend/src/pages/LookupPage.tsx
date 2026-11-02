import React from 'react';
import { COPY } from '../lib/copy';
import { Search } from 'lucide-react';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

export const LookupPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
      <div className="text-center space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.lookup.title}</h1>
        <p className="text-slate-600 max-w-xl mx-auto">{COPY.lookup.subtitle}</p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
        <form onSubmit={(e) => e.preventDefault()} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <Input
              id="lookup-input"
              aria-label={COPY.lookup.searchPlaceholder}
              placeholder={COPY.lookup.searchPlaceholder}
            />
          </div>
          <Button type="submit" leftIcon={<Search className="w-4 h-4" />}>
            {COPY.lookup.searchButton}
          </Button>
        </form>

        <div className="border-t border-slate-100 pt-6">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
            Supported Verification Formats
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
