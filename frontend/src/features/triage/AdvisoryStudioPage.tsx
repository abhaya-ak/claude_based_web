import React, { useState, useEffect } from 'react';
import { analyticsApi } from '../../api/analytics';
import type { ThreatAdvisory } from '../../api/schema';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import { Modal } from '../../components/Modal';
import { Alert } from '../../components/Alert';
import { Radio, PlusCircle, Send, ShieldAlert } from 'lucide-react';
import { formatDate } from '../../lib/format';

export const AdvisoryStudioPage: React.FC = () => {
  const [advisories, setAdvisories] = useState<ThreatAdvisory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDraftModalOpen, setIsDraftModalOpen] = useState(false);

  // New Advisory Form Fields
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [content, setContent] = useState('');
  const [audienceGroup, setAudienceGroup] = useState<'GENERAL' | 'ELDERLY' | 'TEENAGER' | 'NON_TECH' | 'ALL'>('GENERAL');
  const [primaryCategory, setPrimaryCategory] = useState('PHISHING');

  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadAdvisories = async () => {
    setIsLoading(true);
    try {
      const res = await analyticsApi.getAdvisories();
      setAdvisories(res.results || []);
    } catch {
      // Offline fallback
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAdvisories();
  }, []);

  const handleCreateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await analyticsApi.createAdvisory({
        title,
        summary,
        content,
        audience_group: audienceGroup,
        primary_category: primaryCategory,
      });
      setActionNotice('Advisory draft created successfully.');
      setIsDraftModalOpen(false);
      setTitle('');
      setSummary('');
      setContent('');
      loadAdvisories();
    } catch {
      setActionNotice('Failed to create advisory draft.');
    }
  };

  const handlePublish = async (id: string) => {
    try {
      await analyticsApi.publishAdvisory(id);
      setActionNotice('Threat advisory published and broadcast via SNS topic!');
      loadAdvisories();
    } catch {
      setActionNotice('Failed to publish advisory.');
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Radio className="w-6 h-6 text-red-600" />
            <span>Emergency Threat Advisory Studio</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Broadcast emergency scam alerts to subscribed citizens and partner agencies via SNS fan-out.
          </p>
        </div>

        <Button
          size="sm"
          onClick={() => setIsDraftModalOpen(true)}
          leftIcon={<PlusCircle className="w-4 h-4" />}
        >
          Draft New Advisory
        </Button>
      </div>

      {actionNotice && (
        <Alert variant="info" onDismiss={() => setActionNotice(null)}>
          {actionNotice}
        </Alert>
      )}

      {/* Advisories Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-slate-500">Loading advisories...</div>
        ) : advisories.length === 0 ? (
          <div className="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-3">
            <ShieldAlert className="w-10 h-10 text-slate-300 mx-auto" />
            <h2 className="text-sm font-bold text-slate-800">No threat advisories broadcast</h2>
            <p className="text-xs text-slate-500">Draft and publish urgent threat bulletins to warn citizens.</p>
          </div>
        ) : (
          advisories.map((advisory) => (
            <div
              key={advisory.id}
              className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
            >
              <div className="space-y-1.5 max-w-2xl">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    advisory.status === 'PUBLISHED'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {advisory.status}
                  </span>
                  <span className="text-xs font-semibold text-slate-500">
                    Audience: {advisory.audience_group}
                  </span>
                </div>
                <h2 className="text-base font-bold text-slate-900">{advisory.title}</h2>
                <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                  {advisory.summary}
                </p>
                <div className="text-[11px] text-slate-400">
                  {formatDate(advisory.published_at || advisory.created_at)}
                </div>
              </div>

              {advisory.status === 'DRAFT' && (
                <Button
                  size="sm"
                  variant="primary"
                  leftIcon={<Send className="w-3.5 h-3.5" />}
                  onClick={() => handlePublish(advisory.id)}
                >
                  Publish & Broadcast
                </Button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Draft Modal */}
      <Modal
        isOpen={isDraftModalOpen}
        onClose={() => setIsDraftModalOpen(false)}
        title="Draft Urgent Threat Advisory"
      >
        <form onSubmit={handleCreateDraft} className="space-y-4">
          <Input
            id="adv-title"
            label="Advisory Headline"
            required
            placeholder="e.g. URGENT: Fake Bank SMS Campaign Impersonating OTP Verifications"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />

          <Select
            id="adv-audience"
            label="Target Audience Group"
            value={audienceGroup}
            onChange={(e) => setAudienceGroup(e.target.value as any)}
            options={[
              { value: 'ALL', label: 'All Citizens (National Broadcast)' },
              { value: 'GENERAL', label: 'General Public' },
              { value: 'ELDERLY', label: 'Seniors & Families' },
              { value: 'TEENAGER', label: 'Youth & Gaming' },
              { value: 'NON_TECH', label: 'Non-Technical Individuals' },
            ]}
          />

          <Select
            id="adv-category"
            label="Scam Category"
            value={primaryCategory}
            onChange={(e) => setPrimaryCategory(e.target.value)}
            options={[
              { value: 'PHISHING', label: 'Phishing' },
              { value: 'INVESTMENT', label: 'Investment Scam' },
              { value: 'E_COMMERCE', label: 'E-Commerce Scam' },
              { value: 'JOB', label: 'Job Scam' },
              { value: 'IMPERSONATION', label: 'Impersonation Scam' },
            ]}
          />

          <Input
            id="adv-summary"
            label="Summary Teaser"
            required
            placeholder="One-sentence executive summary for alert notifications"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />

          <div className="space-y-1.5 text-left">
            <label htmlFor="adv-content" className="block text-sm font-semibold text-slate-800">
              Full Advisory Content & Guidance <span className="text-red-600">*</span>
            </label>
            <textarea
              id="adv-content"
              required
              rows={4}
              className="w-full rounded-md border border-slate-300 p-3 text-sm focus-visible:outline focus-visible:outline-slate-900"
              placeholder="Detail the modus operandi, offending domain patterns, and citizen protective actions..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setIsDraftModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">
              Save Draft
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
