import React from 'react';
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from 'lucide-react';

export type AlertVariant = 'info' | 'success' | 'warning' | 'error';

export interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  children,
  onDismiss,
  className = '',
}) => {
  const styles = {
    info: {
      container: 'bg-blue-50 border-blue-300 text-blue-900',
      icon: <Info className="h-5 w-5 text-blue-700 flex-shrink-0" aria-hidden="true" />,
    },
    success: {
      container: 'bg-green-50 border-green-300 text-green-900',
      icon: <CheckCircle2 className="h-5 w-5 text-green-700 flex-shrink-0" aria-hidden="true" />,
    },
    warning: {
      container: 'bg-yellow-50 border-yellow-300 text-yellow-950',
      icon: <AlertTriangle className="h-5 w-5 text-yellow-700 flex-shrink-0" aria-hidden="true" />,
    },
    error: {
      container: 'bg-red-50 border-red-300 text-red-950',
      icon: <AlertCircle className="h-5 w-5 text-gov-red flex-shrink-0" aria-hidden="true" />,
    },
  };

  const selected = styles[variant];

  return (
    <div
      role={variant === 'error' || variant === 'warning' ? 'alert' : 'status'}
      aria-live={variant === 'error' ? 'assertive' : 'polite'}
      className={`relative flex items-start gap-3 rounded-lg border p-4 text-sm ${selected.container} ${className}`}
    >
      <div className="pt-0.5">{selected.icon}</div>
      <div className="flex-1 space-y-1">
        {title && <h3 className="font-semibold">{title}</h3>}
        <div className="text-slate-800 leading-relaxed">{children}</div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-auto inline-flex p-1 text-slate-500 hover:text-slate-800 rounded focus-visible:outline focus-visible:outline-2"
          aria-label="Dismiss alert"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
};
