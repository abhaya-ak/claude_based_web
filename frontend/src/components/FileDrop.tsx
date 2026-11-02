import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Image as ImageIcon, X, AlertCircle } from 'lucide-react';

export interface FileDropProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  maxFiles?: number;
  maxSizeBytes?: number;
  acceptedTypes?: string[];
  disabled?: boolean;
}

export const FileDrop: React.FC<FileDropProps> = ({
  files,
  onFilesChange,
  maxFiles = 3,
  maxSizeBytes = 5 * 1024 * 1024, // 5MB
  acceptedTypes = ['image/png', 'image/jpeg', 'application/pdf'],
  disabled = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndAddFiles = (newFiles: FileList | File[]) => {
    setErrorMsg(null);
    const candidateFiles = Array.from(newFiles);

    if (files.length + candidateFiles.length > maxFiles) {
      setErrorMsg(`Maximum of ${maxFiles} evidence files permitted.`);
      return;
    }

    const validFiles: File[] = [];
    for (const file of candidateFiles) {
      if (!acceptedTypes.includes(file.type)) {
        setErrorMsg(`"${file.name}" is an unsupported format. Only PNG, JPEG, and PDF are accepted.`);
        return;
      }
      if (file.size > maxSizeBytes) {
        setErrorMsg(`"${file.name}" exceeds the 5MB size limit.`);
        return;
      }
      validFiles.push(file);
    }

    onFilesChange([...files, ...validFiles]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (!disabled && e.dataTransfer.files) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  };

  const handleRemove = (indexToRemove: number) => {
    onFilesChange(files.filter((_, idx) => idx !== indexToRemove));
  };

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
          isDragging
            ? 'border-slate-900 bg-slate-100'
            : 'border-slate-300 hover:border-slate-400 bg-slate-50/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        aria-label="Upload evidence files by drag and drop or browsing"
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={acceptedTypes.join(',')}
          className="hidden"
          disabled={disabled}
          onChange={(e) => {
            if (e.target.files) validateAndAddFiles(e.target.files);
            e.target.value = '';
          }}
        />

        <UploadCloud className="h-10 w-10 text-slate-400 mb-2" aria-hidden="true" />
        <p className="text-sm font-semibold text-slate-800">
          Drop screenshots or documents here, or <span className="text-blue-700 underline">browse</span>
        </p>
        <p className="text-xs text-slate-500 mt-1">
          PNG, JPEG, or PDF up to 5MB each (Max {maxFiles} files)
        </p>
      </div>

      {/* Validation Error */}
      {errorMsg && (
        <div className="flex items-center gap-2 text-xs font-semibold text-red-600" role="alert">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Selected Files List */}
      {files.length > 0 && (
        <ul className="space-y-2" aria-label="Attached evidence files">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm"
            >
              <div className="flex items-center gap-3 truncate">
                {file.type.includes('image') ? (
                  <ImageIcon className="h-5 w-5 text-blue-600 flex-shrink-0" />
                ) : (
                  <FileText className="h-5 w-5 text-red-600 flex-shrink-0" />
                )}
                <div className="truncate text-left">
                  <p className="font-medium text-slate-900 truncate">{file.name}</p>
                  <p className="text-[11px] text-slate-500">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleRemove(idx)}
                className="rounded p-1 text-slate-400 hover:text-red-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-600"
                aria-label={`Remove file ${file.name}`}
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
