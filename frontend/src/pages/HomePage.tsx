import React from 'react';
import { Link } from 'react-router-dom';
import { COPY } from '../lib/copy';
import { ShieldCheck, Search, FileText, BookOpen, Target, ArrowRight } from 'lucide-react';
import { LookupWidget } from '../features/lookup/LookupWidget';

export const HomePage: React.FC = () => {
  return (
    <div className="space-y-12 pb-16">
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-blue-900 to-gov-navy text-white py-16 px-4 sm:px-6 lg:px-8 shadow-inner">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 bg-blue-800/60 border border-blue-400/30 px-3 py-1 rounded-full text-xs font-semibold text-blue-200">
            <ShieldCheck className="w-4 h-4 text-gov-yellow" />
            <span>National Anti-Scam Intelligence Network</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Stop Scams Before They Strike.
          </h1>

          <p className="text-base sm:text-lg text-blue-100 max-w-2xl mx-auto leading-relaxed">
            Verify suspicious phone numbers, links, and accounts against verified threat intelligence, report fraud incidents safely, and build resistance.
          </p>

          <div className="pt-2">
            <LookupWidget />
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
            <Link
              to="/lookup"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-gov-yellow text-slate-950 font-bold hover:bg-amber-400 shadow-md transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            >
              <Search className="w-4 h-4" />
              <span>{COPY.nav.lookup}</span>
            </Link>

            <Link
              to="/report"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-white text-gov-blue font-bold hover:bg-slate-100 shadow-md transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            >
              <FileText className="w-4 h-4" />
              <span>{COPY.nav.report}</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Feature Pillar Cards */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1: Indicator Lookup */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 text-gov-blue rounded-lg w-fit">
                <Search className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-slate-900">{COPY.lookup.title}</h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                {COPY.lookup.subtitle}
              </p>
            </div>
            <Link
              to="/lookup"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-gov-blue hover:text-gov-navy mt-4"
            >
              <span>Verify Now</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Card 2: Incident Reporting */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="space-y-3">
              <div className="p-3 bg-red-50 text-gov-red rounded-lg w-fit">
                <FileText className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-slate-900">{COPY.report.title}</h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                {COPY.report.subtitle}
              </p>
            </div>
            <Link
              to="/report"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-gov-red hover:text-red-800 mt-4"
            >
              <span>Submit Incident</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Card 3: Scam Simulator */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="space-y-3">
              <div className="p-3 bg-amber-50 text-amber-700 rounded-lg w-fit">
                <Target className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-slate-900">{COPY.simulator.title}</h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                {COPY.simulator.subtitle}
              </p>
            </div>
            <Link
              to="/simulator"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-amber-700 hover:text-amber-800 mt-4"
            >
              <span>Start Exercise</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Card 4: Literacy Hub */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="space-y-3">
              <div className="p-3 bg-emerald-50 text-emerald-700 rounded-lg w-fit">
                <BookOpen className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-slate-900">{COPY.literacy.title}</h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                {COPY.literacy.subtitle}
              </p>
            </div>
            <Link
              to="/literacy"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 hover:text-emerald-800 mt-4"
            >
              <span>Explore Guides</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};
