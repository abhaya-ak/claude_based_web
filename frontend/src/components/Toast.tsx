import React, { useEffect } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastType = 'info' | 'success' | 'error';

export interface ToastProps {
  id?: string;
  type?: ToastType;
  message: string;
  onClose: () => void;
  durationMs?: number;
}

export const Toast: React.FC<ToastProps> = ({
  type = 'info',
  message,
  onClose,
  durationMs = 4000,
}) => {
  useEffect(() => {
    if (durationMs <= 0) return;
    const timer = setTimeout(() => {
      onClose();
    }, durationMs);
    return () => clearTimeout(timer);
  }, [durationMs, onClose]);

  const icons = {
    info: <Info className="h-5 w-5 text-blue-400" aria-hidden="true" />,
    success: <CheckCircle2 className="h-5 w-5 text-emerald-400" aria-hidden="true" />,
    error: <AlertCircle className="h-5 w-5 text-red-400" aria-hidden="true" />,
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-5 right-5 z-50 flex items-center gap-3 rounded-lg bg-slate-900 px-4 py-3 text-white shadow-xl ring-1 ring-white/10"
    >
      <div>{icons[type]}</div>
      <p className="text-sm font-medium">{message}</p>
      <button
        type="button"
        onClick={onClose}
        className="ml-3 rounded p-1 text-slate-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
        aria-label="Close notification"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};
