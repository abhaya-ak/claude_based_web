import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  id?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, helperText, error, id, className = '', required, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const helperId = `${inputId}-helper`;

    const hasError = !!error;

    return (
      <div className="w-full space-y-1.5 text-left">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-semibold text-slate-800"
          >
            {label}
            {required && <span className="ml-1 text-gov-red" aria-hidden="true">*</span>}
          </label>
        )}

        <input
          ref={ref}
          id={inputId}
          required={required}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={
            hasError ? errorId : helperText ? helperId : undefined
          }
          className={`w-full rounded-md border px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-colors
            placeholder:text-slate-400
            focus-visible:outline focus-visible:outline-3 focus-visible:outline-offset-2
            disabled:bg-slate-100 disabled:cursor-not-allowed
            ${
              hasError
                ? 'border-gov-red focus-visible:outline-gov-red bg-red-50/20'
                : 'border-slate-300 hover:border-slate-400 focus-visible:outline-gov-blue'
            } ${className}`}
          {...props}
        />

        {hasError ? (
          <p id={errorId} className="text-xs font-medium text-gov-red" role="alert">
            {error}
          </p>
        ) : helperText ? (
          <p id={helperId} className="text-xs text-slate-500">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = 'Input';
