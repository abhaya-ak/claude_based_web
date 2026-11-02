import React from 'react';

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // Split lines and parse safe elements
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];

  const flushList = () => {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="list-disc pl-5 my-3 space-y-1 text-slate-700">
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  const parseInline = (text: string): React.ReactNode => {
    // Simple inline bold parser without raw HTML injection
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushList();
      return;
    }

    // Heading 1
    if (trimmed.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={index} className="text-2xl font-black text-slate-900 mt-6 mb-3 tracking-tight">
          {parseInline(trimmed.slice(2))}
        </h2>
      );
      return;
    }

    // Heading 2
    if (trimmed.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={index} className="text-xl font-bold text-slate-900 mt-5 mb-2 tracking-tight">
          {parseInline(trimmed.slice(3))}
        </h3>
      );
      return;
    }

    // Heading 3
    if (trimmed.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={index} className="text-base font-bold text-slate-900 mt-4 mb-2">
          {parseInline(trimmed.slice(4))}
        </h4>
      );
      return;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      flushList();
      elements.push(
        <blockquote
          key={index}
          className="border-l-4 border-amber-500 bg-amber-50/50 pl-4 py-2 my-3 text-sm italic text-slate-700 rounded-r"
        >
          {parseInline(trimmed.slice(2))}
        </blockquote>
      );
      return;
    }

    // Bullet points
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      inList = true;
      listItems.push(
        <li key={index} className="text-sm leading-relaxed">
          {parseInline(trimmed.slice(2))}
        </li>
      );
      return;
    }

    // Standard paragraph
    flushList();
    elements.push(
      <p key={index} className="text-sm leading-relaxed text-slate-700 my-2">
        {parseInline(trimmed)}
      </p>
    );
  });

  flushList();

  return <div className={`prose-slate max-w-none ${className}`}>{elements}</div>;
};
