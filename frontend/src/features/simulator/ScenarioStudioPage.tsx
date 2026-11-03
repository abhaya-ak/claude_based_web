import React, { useState, useEffect } from 'react';
import { literacyApi } from '../../api/literacy';
import type { StudioScenario, ScenarioTactic } from '../../api/schema';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Alert } from '../../components/Alert';
import { Modal } from '../../components/Modal';
import {
  Layers,
  Plus,
  Send,
  Flag,
  Search,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { formatDate } from '../../lib/format';

export const ScenarioStudioPage: React.FC = () => {
  const [scenarios, setScenarios] = useState<StudioScenario[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Author Scenario Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState('SMS');
  const [isScam, setIsScam] = useState(true);
  const [tactic, setTactic] = useState<ScenarioTactic>('URGENCY');
  const [difficulty, setDifficulty] = useState(1);
  const [imageAlt, setImageAlt] = useState('');
  const [explanation, setExplanation] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Red Flag Hotspot Modal State
  const [activeScenarioForFlag, setActiveScenarioForFlag] = useState<StudioScenario | null>(null);
  const [flagCode, setFlagCode] = useState('URGENCY');
  const [xPct, setXPct] = useState(10);
  const [yPct, setYPct] = useState(20);
  const [wPct, setWPct] = useState(40);
  const [hPct, setHPct] = useState(15);
  const [flagExplanation, setFlagExplanation] = useState('');
  const [isSubmittingFlag, setIsSubmittingFlag] = useState(false);

  const fetchScenarios = async () => {
    setIsLoading(true);
    try {
      const data = await literacyApi.getStudioScenarios();
      setScenarios(data.results || []);
    } catch {
      setErrorMsg('Failed to load training scenarios.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchScenarios();
  }, []);

  const handleIsScamToggle = (val: boolean) => {
    setIsScam(val);
    if (!val) {
      setTactic('NONE');
    } else if (tactic === 'NONE') {
      setTactic('URGENCY');
    }
  };

  const handleCreateScenario = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !explanation.trim() || !selectedFile) {
      setErrorMsg('Please provide a title, explanation, and screenshot image.');
      return;
    }

    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('title', title.trim());
      formData.append('channel', channel);
      formData.append('is_scam', String(isScam));
      formData.append('tactic', isScam ? tactic : 'NONE');
      formData.append('difficulty', String(difficulty));
      formData.append('image_alt', imageAlt.trim() || title.trim());
      formData.append('explanation', explanation.trim());
      formData.append('image', selectedFile);

      await literacyApi.createStudioScenario(formData);
      setSuccessMsg('Scenario draft created successfully.');
      setIsCreateModalOpen(false);
      setTitle('');
      setImageAlt('');
      setExplanation('');
      setSelectedFile(null);
      fetchScenarios();
    } catch {
      setErrorMsg('Failed to create scenario draft.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePublishScenario = async (id: string) => {
    try {
      await literacyApi.publishStudioScenario(id);
      setSuccessMsg('Scenario published to the public Simulator queue!');
      fetchScenarios();
    } catch {
      setErrorMsg('Failed to publish scenario.');
    }
  };

  const handleAddFlag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeScenarioForFlag || !flagExplanation.trim()) return;

    setIsSubmittingFlag(true);
    try {
      await literacyApi.addScenarioRedFlag(activeScenarioForFlag.id, {
        flag_code: flagCode,
        x_pct: xPct,
        y_pct: yPct,
        w_pct: wPct,
        h_pct: hPct,
        explanation: flagExplanation.trim(),
      });
      setSuccessMsg('Red flag hotspot attached.');
      setActiveScenarioForFlag(null);
      setFlagExplanation('');
      fetchScenarios();
    } catch {
      setErrorMsg('Failed to attach red flag hotspot.');
    } finally {
      setIsSubmittingFlag(false);
    }
  };

  const filteredScenarios = scenarios.filter((s) => {
    const matchesStatus = statusFilter === 'ALL' || s.status === statusFilter;
    const matchesQuery =
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.tactic.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesQuery;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Layers className="w-7 h-7 text-indigo-600" />
            <span>Scenario Authoring Studio</span>
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Author interactive scam simulation cards with anti-cheat masking and coordinate-based red flag hotspots.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            onClick={() => setIsCreateModalOpen(true)}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Create Scenario
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
            placeholder="Search scenarios by title or tactic..."
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

      {/* Scenarios Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Title & Channel</th>
                <th className="py-3 px-4">Nature</th>
                <th className="py-3 px-4">Tactic</th>
                <th className="py-3 px-4">Difficulty</th>
                <th className="py-3 px-4">Hotspots</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 text-xs">
                    Loading simulation scenarios...
                  </td>
                </tr>
              ) : filteredScenarios.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 text-xs">
                    No scenarios found. Click "Create Scenario" to author one.
                  </td>
                </tr>
              ) : (
                filteredScenarios.map((scen) => (
                  <tr key={scen.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{scen.title}</div>
                      <div className="text-xs font-mono text-slate-400 mt-0.5">[{scen.channel}]</div>
                    </td>
                    <td className="py-3 px-4">
                      {scen.is_scam ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800">
                          <AlertTriangle className="w-3 h-3" />
                          <span>SCAM</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>LEGITIMATE</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-700">
                      {scen.tactic}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      Level {scen.difficulty}
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-700">
                      {scen.red_flags?.length || 0} flags
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          scen.status === 'PUBLISHED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {scen.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                      {formatDate(scen.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveScenarioForFlag(scen)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900 px-2 py-1 rounded hover:bg-slate-100 transition-colors"
                          title="Add red flag hotspot"
                        >
                          <Flag className="w-3.5 h-3.5" />
                          <span>Hotspot</span>
                        </button>

                        {scen.status === 'DRAFT' && (
                          <button
                            type="button"
                            onClick={() => handlePublishScenario(scen.id)}
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

      {/* Author Scenario Modal */}
      {isCreateModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsCreateModalOpen(false)}
          title="Author Training Scenario Card"
        >
          <form onSubmit={handleCreateScenario} className="space-y-4">
            <div>
              <label htmlFor="scen-title" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Scenario Headline *
              </label>
              <Input
                id="scen-title"
                type="text"
                required
                placeholder="e.g. Courier Parcel Delivery Reschedule SMS"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="scen-channel" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Communication Channel *
                </label>
                <select
                  id="scen-channel"
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900 bg-white"
                >
                  <option value="SMS">SMS Message</option>
                  <option value="WHATSAPP">WhatsApp</option>
                  <option value="TELEGRAM">Telegram</option>
                  <option value="EMAIL">Email</option>
                  <option value="WEBSITE">Website Portal</option>
                  <option value="PHONE_CALL">Voice Call</option>
                </select>
              </div>

              <div>
                <label htmlFor="scen-diff" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Difficulty Level
                </label>
                <select
                  id="scen-diff"
                  value={difficulty}
                  onChange={(e) => setDifficulty(Number(e.target.value))}
                  className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900 bg-white"
                >
                  <option value={1}>Level 1: Obvious / Beginner</option>
                  <option value={2}>Level 2: Moderate / Heuristic Clues</option>
                  <option value={3}>Level 3: Subtle / Advanced Impersonation</option>
                </select>
              </div>
            </div>

            {/* Is Scam Toggle & Tactic */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div>
                <span className="block text-xs font-bold text-slate-700 uppercase mb-2">
                  Incident Classification *
                </span>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer">
                    <input
                      type="radio"
                      name="is_scam"
                      checked={isScam === true}
                      onChange={() => handleIsScamToggle(true)}
                    />
                    <span className="text-red-700">Scam Attack</span>
                  </label>
                  <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer">
                    <input
                      type="radio"
                      name="is_scam"
                      checked={isScam === false}
                      onChange={() => handleIsScamToggle(false)}
                    />
                    <span className="text-emerald-700">Legitimate</span>
                  </label>
                </div>
              </div>

              {isScam && (
                <div>
                  <label htmlFor="scen-tactic" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                    Primary Psychological Tactic *
                  </label>
                  <select
                    id="scen-tactic"
                    value={tactic}
                    onChange={(e) => setTactic(e.target.value as ScenarioTactic)}
                    className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:outline-slate-900 bg-white"
                  >
                    <option value="URGENCY">Urgency (Time pressure)</option>
                    <option value="FEAR">Fear (Account suspended / Lawsuit)</option>
                    <option value="AUTHORITY">Authority (Police, Tax, Bank)</option>
                    <option value="GREED">Greed (Prize, High ROI)</option>
                    <option value="FAMILIARITY">Familiarity (Impersonating friend)</option>
                    <option value="ISOLATION">Isolation (Keep secret)</option>
                  </select>
                </div>
              )}
            </div>

            {/* Image Upload */}
            <div>
              <label htmlFor="scen-file" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Scenario Image (PNG, JPG - max 5MB) *
              </label>
              <input
                id="scen-file"
                type="file"
                required
                accept="image/png,image/jpeg"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                  }
                }}
                className="w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-slate-900 file:text-white hover:file:bg-slate-800"
              />
            </div>

            <div>
              <label htmlFor="scen-alt" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Message Transcript / Visual Prompt
              </label>
              <textarea
                id="scen-alt"
                rows={2}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900"
                placeholder="Text transcription of message content for accessibility and fallback."
                value={imageAlt}
                onChange={(e) => setImageAlt(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="scen-expl" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Educator Rationale / Explanation *
              </label>
              <textarea
                id="scen-expl"
                required
                rows={3}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900"
                placeholder="Detailed rationale displayed upon citizen assessment."
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" isLoading={isSubmitting}>
                Save Scenario Draft
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Red Flag Hotspot Modal */}
      {activeScenarioForFlag && (
        <Modal
          isOpen={true}
          onClose={() => setActiveScenarioForFlag(null)}
          title={`Attach Hotspot to "${activeScenarioForFlag.title}"`}
        >
          <form onSubmit={handleAddFlag} className="space-y-4">
            <p className="text-xs text-slate-600">
              Define the percentage bounding box coordinates (0-100%) highlighting deceptive indicators on the scenario image.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div>
                <label htmlFor="hp-x" className="font-bold text-slate-600">X Position (%)</label>
                <input
                  id="hp-x"
                  type="number"
                  min={0}
                  max={100}
                  value={xPct}
                  onChange={(e) => setXPct(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded"
                />
              </div>
              <div>
                <label htmlFor="hp-y" className="font-bold text-slate-600">Y Position (%)</label>
                <input
                  id="hp-y"
                  type="number"
                  min={0}
                  max={100}
                  value={yPct}
                  onChange={(e) => setYPct(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded"
                />
              </div>
              <div>
                <label htmlFor="hp-w" className="font-bold text-slate-600">Width (%)</label>
                <input
                  id="hp-w"
                  type="number"
                  min={1}
                  max={100}
                  value={wPct}
                  onChange={(e) => setWPct(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded"
                />
              </div>
              <div>
                <label htmlFor="hp-h" className="font-bold text-slate-600">Height (%)</label>
                <input
                  id="hp-h"
                  type="number"
                  min={1}
                  max={100}
                  value={hPct}
                  onChange={(e) => setHPct(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded"
                />
              </div>
            </div>

            <div>
              <label htmlFor="flag-code" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Deception Tactic Code
              </label>
              <Input
                id="flag-code"
                type="text"
                value={flagCode}
                onChange={(e) => setFlagCode(e.target.value.toUpperCase())}
              />
            </div>

            <div>
              <label htmlFor="flag-expl" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Hotspot Specific Feedback *
              </label>
              <textarea
                id="flag-expl"
                required
                rows={3}
                placeholder="Explain why this exact region indicates psychological manipulation..."
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900"
                value={flagExplanation}
                onChange={(e) => setFlagExplanation(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setActiveScenarioForFlag(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" isLoading={isSubmittingFlag}>
                Attach Hotspot
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
