import React from 'react';
import { useAccessibility } from '../a11y/AccessibilityProvider';
import { COPY } from '../lib/copy';
import { Volume2, VolumeX, Eye } from 'lucide-react';

export const AccessibilityBar: React.FC = () => {
  const { highContrast, toggleHighContrast, fontScale, setFontScale, speech } =
    useAccessibility();

  const handleReadAloud = () => {
    if (speech.isSpeaking) {
      speech.stop();
    } else {
      const mainContent = document.getElementById('main-content');
      const textToRead = mainContent?.innerText || document.body.innerText;
      speech.speak(textToRead.slice(0, 2000)); // Read first section
    }
  };

  return (
    <aside
      aria-label={COPY.a11y.barTitle}
      className="bg-slate-900 text-slate-200 border-b border-slate-800 text-xs py-1.5 px-4"
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        {/* Skip to Main Content Link (Visible on Tab/Focus) */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-2 focus:bg-gov-yellow focus:text-slate-900 focus:font-bold rounded"
        >
          {COPY.nav.skipToContent}
        </a>

        {/* Accessibility Features Indicator */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">
            {COPY.a11y.barTitle}:
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-4">
          {/* High Contrast Toggle */}
          <button
            type="button"
            onClick={toggleHighContrast}
            aria-pressed={highContrast}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white ${
              highContrast
                ? 'bg-yellow-400 text-slate-950 font-bold'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
            }`}
          >
            <Eye className="w-3.5 h-3.5" aria-hidden="true" />
            <span>
              {highContrast ? COPY.a11y.highContrastOn : COPY.a11y.highContrast}
            </span>
          </button>

          {/* Font Scaling Controls */}
          <div className="flex items-center gap-1 bg-slate-800 rounded p-0.5" role="group" aria-label={COPY.a11y.fontSize}>
            <button
              type="button"
              onClick={() => setFontScale('normal')}
              aria-pressed={fontScale === 'normal'}
              className={`px-2 py-0.5 rounded text-xs transition-colors focus-visible:outline focus-visible:outline-2 ${
                fontScale === 'normal'
                  ? 'bg-gov-blue text-white font-bold'
                  : 'text-slate-300 hover:text-white'
              }`}
              title={COPY.a11y.fontNormal}
            >
              <span className="text-xs">A</span>
            </button>
            <button
              type="button"
              onClick={() => setFontScale('large')}
              aria-pressed={fontScale === 'large'}
              className={`px-2 py-0.5 rounded text-xs transition-colors focus-visible:outline focus-visible:outline-2 ${
                fontScale === 'large'
                  ? 'bg-gov-blue text-white font-bold'
                  : 'text-slate-300 hover:text-white'
              }`}
              title={COPY.a11y.fontLarge}
            >
              <span className="text-sm font-semibold">A+</span>
            </button>
            <button
              type="button"
              onClick={() => setFontScale('xlarge')}
              aria-pressed={fontScale === 'xlarge'}
              className={`px-2 py-0.5 rounded text-xs transition-colors focus-visible:outline focus-visible:outline-2 ${
                fontScale === 'xlarge'
                  ? 'bg-gov-blue text-white font-bold'
                  : 'text-slate-300 hover:text-white'
              }`}
              title={COPY.a11y.fontXLarge}
            >
              <span className="text-base font-bold">A++</span>
            </button>
          </div>

          {/* Text to Speech Toggle */}
          {speech.isSupported && (
            <button
              type="button"
              onClick={handleReadAloud}
              aria-pressed={speech.isSpeaking}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white ${
                speech.isSpeaking
                  ? 'bg-gov-red text-white animate-pulse'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
              }`}
            >
              {speech.isSpeaking ? (
                <>
                  <VolumeX className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>{COPY.a11y.stopSpeech}</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>{COPY.a11y.readAloud}</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};
