import React, { useState, useEffect } from 'react';
import { literacyApi } from '../../api/literacy';
import type { LiteracyGuide, AudienceGroup } from '../../api/schema';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Alert } from '../../components/Alert';
import { Modal } from '../../components/Modal';
import { MarkdownViewer } from '../../components/MarkdownViewer';
import {
  BookOpen,
  Plus,
  Send,
  UploadCloud,
  Search,
  Eye,
  Edit3,
} from 'lucide-react';
import { formatDate } from '../../lib/format';

export const EducatorStudioPage: React.FC = () => {
  const [guides, setGuides] = useState<LiteracyGuide[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Guide Create / Edit Modal State
  const [isEditorModalOpen, setIsEditorModalOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<'write' | 'preview'>('write');
  const [title, setTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [summary, setSummary] = useState('');
  const [bodyMarkdown, setBodyMarkdown] = useState('');
  const [readingTime, setReadingTime] = useState<number>(3);
  const [selectedAudiences, setSelectedAudiences] = useState<AudienceGroup[]>(['GENERAL']);
  const [tacticsInput, setTacticsInput] = useState('URGENCY, AUTHORITY');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Asset Upload Modal State
  const [uploadGuideItem, setUploadGuideItem] = useState<LiteracyGuide | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [altText, setAltText] = useState('');
  const [isUploadingAsset, setIsUploadingAsset] = useState(false);

  const fetchStudioGuides = async () => {
    setIsLoading(true);
    try {
      const data = await literacyApi.getStudioGuides();
      setGuides(data.results || []);
    } catch {
      setErrorMsg('Failed to load studio educational guides.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStudioGuides();
  }, []);

  const handleTitleChange = (val: string) => {
    setTitle(val);
    const generatedSlug = val
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '');
    setSlug(generatedSlug);
  };

  const handleToggleAudience = (aud: AudienceGroup) => {
    if (selectedAudiences.includes(aud)) {
      if (selectedAudiences.length > 1) {
        setSelectedAudiences(selectedAudiences.filter((a) => a !== aud));
      }
    } else {
      setSelectedAudiences([...selectedAudiences, aud]);
    }
  };

  const handleSaveGuide = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !slug.trim() || !summary.trim() || !bodyMarkdown.trim()) {
      setErrorMsg('Please complete all required fields.');
      return;
    }

    setIsSubmitting(true);
    try {
      const tactics = tacticsInput
        .split(',')
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);

      await literacyApi.createStudioGuide({
        title: title.trim(),
        slug: slug.trim(),
        summary: summary.trim(),
        body_markdown: bodyMarkdown,
        reading_time_minutes: readingTime,
        audience_groups: selectedAudiences,
        tactics,
      });

      setSuccessMsg('Guide draft created successfully.');
      setIsEditorModalOpen(false);
      setTitle('');
      setSlug('');
      setSummary('');
      setBodyMarkdown('');
      fetchStudioGuides();
    } catch {
      setErrorMsg('Failed to save guide draft. Ensure the slug is unique.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePublish = async (guideId: string) => {
    try {
      await literacyApi.publishStudioGuide(guideId);
      setSuccessMsg('Guide published successfully to the public Learning Hub!');
      fetchStudioGuides();
    } catch {
      setErrorMsg('Failed to publish guide.');
    }
  };

  const handleAssetUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadGuideItem || !selectedFile) return;

    setIsUploadingAsset(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('alt_text', altText.trim() || selectedFile.name);

      await literacyApi.uploadGuideAsset(uploadGuideItem.id, formData);
      setSuccessMsg(`Asset "${selectedFile.name}" attached successfully.`);
      setUploadGuideItem(null);
      setSelectedFile(null);
      setAltText('');
      fetchStudioGuides();
    } catch {
      setErrorMsg('Failed to upload asset. Supported formats: PDF, PNG, JPG, MP3 (max 10MB).');
    } finally {
      setIsUploadingAsset(false);
    }
  };

  const filteredGuides = guides.filter((g) => {
    const matchesStatus = statusFilter === 'ALL' || g.status === statusFilter;
    const matchesQuery =
      g.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      g.slug.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesQuery;
  });

  return (
    <div className="space-y-6">
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <BookOpen className="w-7 h-7 text-indigo-600" />
            <span>Educator Literacy Studio</span>
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Author multi-audience educational guides, publish scam counter-tactics, and attach media resources.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            onClick={() => setIsEditorModalOpen(true)}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Create New Guide
          </Button>
        </div>
      </div>

      {successMsg && (
        <Alert variant="success" onDismiss={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {errorMsg && (
        <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm text-xs">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search guides by title or slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs outline-none bg-transparent placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-1.5">
          {(['ALL', 'DRAFT', 'PUBLISHED', 'ARCHIVED'] as const).map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-colors ${
                statusFilter === st
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Guides Grid / List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Title & Slug</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Audience</th>
                <th className="py-3 px-4">Tactics</th>
                <th className="py-3 px-4">Assets</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 text-xs">
                    Loading studio guides...
                  </td>
                </tr>
              ) : filteredGuides.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 text-xs">
                    No guides found for the selected filter. Click "Create New Guide" to draft one.
                  </td>
                </tr>
              ) : (
                filteredGuides.map((guide) => (
                  <tr key={guide.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{guide.title}</div>
                      <div className="text-xs font-mono text-slate-400 mt-0.5">/{guide.slug}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          guide.status === 'PUBLISHED'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : guide.status === 'DRAFT'
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {guide.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      <div className="flex flex-wrap gap-1">
                        {guide.audience_groups?.map((aud) => (
                          <span key={aud} className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px]">
                            {aud}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs">
                      <div className="flex flex-wrap gap-1">
                        {guide.tactics?.map((tac) => (
                          <span key={tac} className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 text-[10px]">
                            {tac}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-600">
                      {guide.assets?.length || 0} files
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                      {formatDate(guide.published_at || guide.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setUploadGuideItem(guide)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900 px-2 py-1 rounded hover:bg-slate-100 transition-colors"
                          title="Attach educational asset"
                        >
                          <UploadCloud className="w-3.5 h-3.5" />
                          <span>Asset</span>
                        </button>

                        {guide.status === 'DRAFT' && (
                          <button
                            type="button"
                            onClick={() => handlePublish(guide.id)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 px-2.5 py-1 rounded transition-colors"
                          >
                            <Send className="w-3.5 h-3.5" />
                            <span>Publish</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create / Edit Guide Modal */}
      {isEditorModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsEditorModalOpen(false)}
          title="Author Educational Guide"
        >
          <form onSubmit={handleSaveGuide} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="guide-title" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Guide Title *
                </label>
                <Input
                  id="guide-title"
                  type="text"
                  required
                  placeholder="e.g. Recognizing Deepfake Phone Call Scams"
                  value={title}
                  onChange={(e) => handleTitleChange(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="guide-slug" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  URL Slug (Auto-generated) *
                </label>
                <Input
                  id="guide-slug"
                  type="text"
                  required
                  placeholder="recognizing-deepfake-phone-call-scams"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label htmlFor="guide-summary" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Executive Summary *
              </label>
              <textarea
                id="guide-summary"
                required
                rows={2}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900"
                placeholder="A concise 2-sentence overview displayed on card previews."
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
              />
            </div>

            {/* Audience Groups & Tactics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <span className="block font-bold text-slate-700 uppercase mb-1">Target Audiences *</span>
                <div className="flex flex-wrap gap-2 pt-1">
                  {(['GENERAL', 'ELDERLY', 'TEENAGER', 'NON_TECH'] as AudienceGroup[]).map((grp) => (
                    <button
                      key={grp}
                      type="button"
                      onClick={() => handleToggleAudience(grp)}
                      className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                        selectedAudiences.includes(grp)
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {grp}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="guide-tactics" className="block font-bold text-slate-700 uppercase mb-1">
                  Scam Tactics (Comma-separated)
                </label>
                <Input
                  id="guide-tactics"
                  type="text"
                  placeholder="URGENCY, AUTHORITY, FEAR"
                  value={tacticsInput}
                  onChange={(e) => setTacticsInput(e.target.value)}
                />
              </div>
            </div>

            {/* Markdown Body with Tabbed Preview */}
            <div className="space-y-2">
              <div className="flex items-center justify-between border-b border-slate-200 pb-1">
                <label htmlFor="guide-markdown" className="block text-xs font-bold text-slate-700 uppercase">
                  Content Markdown *
                </label>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setEditorMode('write')}
                    className={`px-2 py-0.5 rounded text-xs font-semibold flex items-center gap-1 ${
                      editorMode === 'write' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Edit3 className="w-3 h-3" />
                    <span>Write</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditorMode('preview')}
                    className={`px-2 py-0.5 rounded text-xs font-semibold flex items-center gap-1 ${
                      editorMode === 'preview' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Eye className="w-3 h-3" />
                    <span>Live Preview</span>
                  </button>
                </div>
              </div>

              {editorMode === 'write' ? (
                <textarea
                  id="guide-markdown"
                  required
                  rows={8}
                  className="w-full text-xs font-mono rounded-lg border border-slate-300 p-3 focus:outline-slate-900"
                  placeholder="# Section 1: Red Flags\n\nExplain the scam scenario and defensive steps..."
                  value={bodyMarkdown}
                  onChange={(e) => setBodyMarkdown(e.target.value)}
                />
              ) : (
                <div className="min-h-[190px] max-h-[250px] overflow-y-auto p-3 rounded-lg border border-slate-200 bg-slate-50">
                  <MarkdownViewer content={bodyMarkdown || '*No content entered yet.*'} />
                </div>
              )}
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-slate-100">
              <div className="flex items-center gap-2 text-xs">
                <label htmlFor="guide-reading-time" className="font-semibold text-slate-600">Reading Time (Min):</label>
                <input
                  id="guide-reading-time"
                  type="number"
                  min={1}
                  max={60}
                  value={readingTime}
                  onChange={(e) => setReadingTime(Number(e.target.value))}
                  className="w-16 p-1 rounded border border-slate-300 text-xs"
                />
              </div>

              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" onClick={() => setIsEditorModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" isLoading={isSubmitting}>
                  Save as Draft
                </Button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {/* Asset Upload Modal */}
      {uploadGuideItem && (
        <Modal
          isOpen={true}
          onClose={() => setUploadGuideItem(null)}
          title={`Upload Asset for "${uploadGuideItem.title}"`}
        >
          <form onSubmit={handleAssetUpload} className="space-y-4">
            <p className="text-xs text-slate-600">
              Attach supporting educational materials such as PDF guides, audio explainers, or infographic charts.
            </p>

            <div>
              <label htmlFor="asset-file" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Select File (PDF, PNG, JPG, MP3 - max 10MB) *
              </label>
              <input
                id="asset-file"
                type="file"
                required
                accept=".pdf,image/png,image/jpeg,audio/mpeg"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                  }
                }}
                className="w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-slate-900 file:text-white hover:file:bg-slate-800"
              />
            </div>

            <div>
              <label htmlFor="asset-alt" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Accessibility Alt Text / Description
              </label>
              <Input
                id="asset-alt"
                type="text"
                placeholder="e.g. Infographic showing fake banking SMS indicators"
                value={altText}
                onChange={(e) => setAltText(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setUploadGuideItem(null)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isUploadingAsset}
                disabled={!selectedFile}
              >
                Upload & Attach
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
