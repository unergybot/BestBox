"use client";

import { parseRagCitations, formatCitation, extractDomain, RagCitation } from '@/lib/ragCitationParser';
import { useState } from 'react';

/**
 * RagCitationBadge - Displays RAG citations with visual styling
 *
 * Renders citations from knowledge base searches with:
 * - Light blue background
 * - Book icon 📚
 * - Collapsible sources section
 */

interface RagCitationBadgeProps {
  /** Assistant message text */
  text: string;
}

export function RagCitationBadge({ text }: RagCitationBadgeProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(true);
  const parsed = parseRagCitations(text);

  if (!parsed.hasRag) {
    // No RAG content, render as-is
    return <div className="whitespace-pre-wrap">{text}</div>;
  }

  const domain = parsed.citations.length > 0
    ? extractDomain(parsed.citations[0].source)
    : null;

  return (
    <div className="space-y-3">
      {/* RAG Indicator Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-sm">
        <span className="text-lg">📚</span>
        <span className="font-medium text-blue-900">
          Searched: {domain || 'Knowledge Base'}
        </span>
      </div>

      {/* Message Content */}
      {parsed.plainText && (
        <div className="whitespace-pre-wrap text-gray-900">
          {parsed.plainText}
        </div>
      )}

      {/* Citations/Sources Section */}
      {parsed.citations.length > 0 && (
        <div className="border-t border-gray-200 pt-3 mt-3">
          <button
            onClick={() => setSourcesExpanded(!sourcesExpanded)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
          >
            <svg
              className={`w-4 h-4 transition-transform ${sourcesExpanded ? 'rotate-90' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Sources ({parsed.citations.length})
          </button>

          {sourcesExpanded && (
            <div className="mt-2 space-y-2">
              {parsed.citations.map((citation, idx) => (
                <CitationItem key={idx} citation={citation} />
              ))}
            </div>
          )}

          {/* Footer info */}
          {parsed.footer && (
            <div className="mt-2 text-xs text-gray-500 italic">
              {parsed.footer}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Individual citation item
 */
function CitationItem({ citation }: { citation: RagCitation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-center justify-between gap-2 group"
      >
        <div className="flex items-center gap-2 flex-1">
          <svg
            className="w-4 h-4 text-blue-600 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors">
            {formatCitation(citation)}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && citation.text && (
        <div className="mt-2 pt-2 border-t border-gray-300 text-sm text-gray-700 whitespace-pre-wrap">
          {citation.text}
        </div>
      )}
    </div>
  );
}

/**
 * Hook to use with CopilotKit message renderer
 * Returns a render function that can be passed to CopilotKit
 */
export function useRagMessageRenderer() {
  return (message: { content: string; role: string }) => {
    if (message.role === 'assistant') {
      return <RagCitationBadge text={message.content} />;
    }
    return <div className="whitespace-pre-wrap">{message.content}</div>;
  };
}
