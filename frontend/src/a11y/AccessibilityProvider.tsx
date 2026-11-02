import React, { createContext, useContext, useState, useEffect } from 'react';
import { useSpeech, UseSpeechReturn } from './useSpeech';

export type FontScale = 'normal' | 'large' | 'xlarge';

interface AccessibilityContextValue {
  highContrast: boolean;
  toggleHighContrast: () => void;
  fontScale: FontScale;
  setFontScale: (scale: FontScale) => void;
  speech: UseSpeechReturn;
  announce: (message: string) => void;
}

const AccessibilityContext = createContext<AccessibilityContextValue | undefined>(undefined);

export const AccessibilityProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [highContrast, setHighContrast] = useState<boolean>(() => {
    return localStorage.getItem('scamshield_a11y_contrast') === 'true';
  });

  const [fontScale, setFontScaleState] = useState<FontScale>(() => {
    const saved = localStorage.getItem('scamshield_a11y_scale');
    return saved === 'large' || saved === 'xlarge' ? saved : 'normal';
  });

  const [announcement, setAnnouncement] = useState<string>('');
  const speech = useSpeech();

  // Sync high contrast class on root HTML element
  useEffect(() => {
    const root = document.documentElement;
    if (highContrast) {
      root.classList.add('high-contrast');
    } else {
      root.classList.remove('high-contrast');
    }
    localStorage.setItem('scamshield_a11y_contrast', String(highContrast));
  }, [highContrast]);

  // Sync font scale class on root HTML element
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('font-scale-large', 'font-scale-xlarge');
    if (fontScale === 'large') {
      root.classList.add('font-scale-large');
    } else if (fontScale === 'xlarge') {
      root.classList.add('font-scale-xlarge');
    }
    localStorage.setItem('scamshield_a11y_scale', fontScale);
  }, [fontScale]);

  const toggleHighContrast = () => setHighContrast((prev) => !prev);
  const setFontScale = (scale: FontScale) => setFontScaleState(scale);

  const announce = (message: string) => {
    setAnnouncement(message);
    // Clear after announcement is picked up
    setTimeout(() => setAnnouncement(''), 1000);
  };

  return (
    <AccessibilityContext.Provider
      value={{
        highContrast,
        toggleHighContrast,
        fontScale,
        setFontScale,
        speech,
        announce,
      }}
    >
      {/* WCAG Live Announcement Region */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {announcement}
      </div>
      {children}
    </AccessibilityContext.Provider>
  );
};

export function useAccessibility(): AccessibilityContextValue {
  const context = useContext(AccessibilityContext);
  if (!context) {
    throw new Error('useAccessibility must be used within an AccessibilityProvider');
  }
  return context;
}
