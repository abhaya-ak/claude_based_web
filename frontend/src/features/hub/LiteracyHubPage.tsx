import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { COPY } from '../../lib/copy';
import { literacyApi } from '../../api/literacy';
import type { LiteracyGuide } from '../../api/schema';
import { BookOpen, Clock, Tag } from 'lucide-react';
import { Input } from '../../components/Input';
import { formatDate } from '../../lib/format';

export const LiteracyHubPage: React.FC = () => {
  const [guides, setGuides] = useState<LiteracyGuide[]>([]);
  const [search, setSearch] = useState('');
  const [selectedGroup, setSelectedGroup] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const loadGuides = async () => {
      setIsLoading(true);
      try {
        const res = await literacyApi.getGuides({
          group: selectedGroup || undefined,
        });
        setGuides(res.results || []);
      } catch {
        // Fallback for offline demo
      } finally {
        setIsLoading(false);
      }
    };
    loadGuides();
  }, [selectedGroup]);

  const audienceGroups = [
    { value: '', label: 'All Audiences' },
    { value: 'GENERAL', label: 'General Public' },
    { value: 'ELDERLY', label: 'Seniors & Families' },
    { value: 'TEENAGER', label: 'Youth & Teens' },
    { value: 'NON_TECH', label: 'Non-Tech Workers' },
  ];

  const filteredGuides = guides.filter(
    (g) =>
      g.title.toLowerCase().includes(search.toLowerCase()) ||
      g.summary.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-3">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.literacy.title}</h1>
        <p className="text-slate-600 max-w-2xl">{COPY.literacy.subtitle}</p>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="w-full sm:w-72">
          <Input
            id="hub-search"
            placeholder={COPY.literacy.searchGuides}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          {audienceGroups.map((grp) => (
            <button
              key={grp.value}
              type="button"
              onClick={() => setSelectedGroup(grp.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                selectedGroup === grp.value
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {grp.label}
            </button>
          ))}
        </div>
      </div>

      {/* Responsive Cards Grid */}
      {isLoading ? (
        <div className="py-16 text-center text-sm text-slate-500">Loading educational guides...</div>
      ) : filteredGuides.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-3">
          <BookOpen className="w-12 h-12 text-slate-300 mx-auto" />
          <h2 className="text-base font-bold text-slate-800">No guides found</h2>
          <p className="text-xs text-slate-500">Try adjusting your search query or audience filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredGuides.map((guide) => (
            <article
              key={guide.id}
              className="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-6 flex flex-col justify-between space-y-4"
            >
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1 font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    <Tag className="w-3 h-3" />
                    <span>{guide.tactics?.[0] || 'DEFENSE'}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>{guide.reading_time_minutes || 3} min</span>
                  </span>
                </div>

                <h2 className="text-lg font-bold text-slate-900 leading-snug hover:text-slate-700">
                  <Link to={`/literacy/${guide.slug}`}>
                    {guide.title}
                  </Link>
                </h2>
                <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                  {guide.summary}
                </p>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                <span>{formatDate(guide.published_at || guide.created_at)}</span>
                <Link
                  to={`/literacy/${guide.slug}`}
                  className="font-semibold text-slate-900 hover:underline"
                >
                  Read Article →
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};
