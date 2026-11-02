import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { literacyApi } from '../../api/literacy';
import type { LiteracyGuide } from '../../api/schema';
import { useSpeech } from '../../a11y/useSpeech';
import { MarkdownViewer } from '../../components/MarkdownViewer';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import {
  ArrowLeft,
  Clock,
  Tag,
  Volume2,
  VolumeX,
  FileText,
  Download,
  AlertCircle,
  Share2,
} from 'lucide-react';
import { formatDate } from '../../lib/format';

export const GuideDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [guide, setGuide] = useState<LiteracyGuide | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const { isSpeaking, speak, stop, isSupported } = useSpeech();

  useEffect(() => {
    if (!slug) return;
    const fetchGuide = async () => {
      setIsLoading(true);
      try {
        const data = await literacyApi.getGuideDetail(slug);
        setGuide(data);
      } catch {
        setErrorMsg('Failed to load educational guide. It may have been archived or does not exist.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchGuide();
  }, [slug]);

  const handleReadAloudToggle = () => {
    if (isSpeaking) {
      stop();
    } else if (guide) {
      const speechText = `${guide.title}. ${guide.summary}. ${guide.body_markdown.replace(/[#*>-]/g, '')}`;
      speak(speechText);
    }
  };

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center text-sm text-slate-500">
        Loading educational advisory...
      </div>
    );
  }

  if (errorMsg || !guide) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 space-y-4">
        <Alert variant="error">{errorMsg || 'Guide not found'}</Alert>
        <Link
          to="/literacy"
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to All Guides</span>
        </Link>
      </div>
    );
  }

  return (
    <article className="max-w-4xl mx-auto px-4 py-10 space-y-8">
      {/* Navigation & Controls Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <Link
          to="/literacy"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Learning Hub</span>
        </Link>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={isSpeaking ? 'danger' : 'outline'}
            onClick={handleReadAloudToggle}
            leftIcon={isSpeaking ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
            title={isSupported ? 'Read guide content aloud' : 'Speech synthesis not supported on this browser'}
          >
            {isSpeaking ? 'Stop Speech' : 'Listen / Read Aloud'}
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleShare}
            leftIcon={<Share2 className="w-3.5 h-3.5" />}
          >
            {copiedLink ? 'Link Copied!' : 'Share Guide'}
          </Button>
        </div>
      </div>

      {/* Guide Header */}
      <header className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {guide.tactics?.map((tactic) => (
            <span
              key={tactic}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold bg-amber-100 text-amber-800 border border-amber-200"
            >
              <Tag className="w-3 h-3" />
              <span>{tactic}</span>
            </span>
          ))}

          {guide.audience_groups?.map((group) => (
            <span
              key={group}
              className="px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-700"
            >
              {group}
            </span>
          ))}
        </div>

        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight leading-tight">
          {guide.title}
        </h1>

        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            <span>{guide.reading_time_minutes || 3} min read</span>
          </span>
          <span>•</span>
          <span>Published on {formatDate(guide.published_at || guide.created_at)}</span>
        </div>

        {/* Executive Summary Box */}
        <div className="bg-slate-50 border-l-4 border-slate-900 p-4 rounded-r-lg">
          <p className="text-sm font-medium text-slate-800 leading-relaxed">
            {guide.summary}
          </p>
        </div>
      </header>

      {/* Guide Main Body Markdown */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 sm:p-8">
        <MarkdownViewer content={guide.body_markdown} />
      </div>

      {/* Assets & Downloads Vault */}
      {guide.assets && guide.assets.length > 0 && (
        <section className="bg-slate-50 rounded-xl border border-slate-200 p-6 space-y-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileText className="w-5 h-5 text-slate-700" />
            <span>Downloadable Materials & Evidence Infographics</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {guide.assets.map((asset) => (
              <a
                key={asset.id}
                href={asset.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-lg bg-white border border-slate-200 hover:border-slate-300 text-xs font-semibold text-slate-800 transition-colors shadow-sm"
              >
                <div className="flex items-center gap-2 truncate">
                  <Download className="w-4 h-4 text-slate-500 shrink-0" />
                  <span className="truncate">{asset.alt_text || 'Educational Asset'}</span>
                </div>
                <span className="text-[10px] text-slate-400 shrink-0 uppercase ml-2">
                  {asset.asset_type}
                </span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Protective Reminders Footer */}
      <div className="p-5 rounded-xl bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <strong className="block font-bold">Suspect you have been targeted?</strong>
          <p className="leading-relaxed">
            Immediately contact your financial institution to freeze unauthorized transactions.
            You can also submit an official report to the national defense registry via our public reporting wizard.
          </p>
          <div className="pt-2">
            <Link
              to="/report"
              className="inline-block font-bold text-amber-950 underline hover:text-black"
            >
              Report a Scam Incident Now →
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
};
