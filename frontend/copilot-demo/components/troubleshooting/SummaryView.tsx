// frontend/copilot-demo/components/troubleshooting/SummaryView.tsx
"use client";

import React from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SuccessBadge } from "./SuccessBadge";
import { RelevanceScore } from "./RelevanceScore";
import { ImageGallery } from "./ImageGallery";

interface SummaryViewProps {
  data: TroubleshootingIssue;
  onExpand: () => void;
  onImageClick: (index: number) => void;
  className?: string;
}

export const SummaryView: React.FC<SummaryViewProps> = ({
  data,
  onExpand,
  onImageClick,
  className = "",
}) => {
  // Truncate text helper
  const truncate = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + "...";
  };

  // Get primary trial result for badge
  const primaryResult = data.result_t2 || data.result_t1 || null;

  return (
    <div
      className={`bg-white border-2 border-teal-200 rounded-lg shadow-sm hover:shadow-md transition-shadow max-w-full ${className}`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-2 sm:p-3 border-b border-gray-100">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xs sm:text-sm font-semibold text-gray-700 truncate">
            🏭 Case #{data.part_number}-{data.issue_number}
          </span>
          <SuccessBadge
            trialVersion={data.trial_version}
            status={primaryResult}
          />
        </div>
        <RelevanceScore score={data.relevance_score} />
      </div>

      {/* Body */}
      <div className="p-3 sm:p-4 space-y-2">
        {/* Problem */}
        <div className="min-w-0">
          <span className="text-xs font-medium text-gray-500">Problem:</span>
          <p className="text-xs sm:text-sm text-gray-800 mt-0.5 break-words">
            {truncate(data.problem, 200)}
          </p>
        </div>

        {/* Solution */}
        <div className="min-w-0">
          <span className="text-xs font-medium text-gray-500">Solution:</span>
          <p className="text-xs sm:text-sm text-gray-600 mt-0.5 break-words">
            {truncate(data.solution, 300)}
          </p>
        </div>

        {/* Image preview - shows all images in compact horizontal scroll */}
        {data.images && data.images.length > 0 && (
          <ImageGallery
            images={data.images}
            onImageClick={onImageClick}
            variant="compact"
          />
        )}

        {/* Metadata row */}
        <div className="text-xs text-gray-500 pt-2 border-t border-gray-100 truncate">
          Part: {data.part_number}
          {data.category && ` | Category: ${data.category}`}
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 sm:px-4 py-2 sm:py-3 bg-gray-50 border-t border-gray-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div className="text-xs text-gray-500">
          {/* Placeholder for social metrics (Phase 4) */}
          👍 0 helpful
        </div>
        <button
          onClick={onExpand}
          className="text-xs sm:text-sm font-medium text-teal-600 hover:text-teal-700 flex items-center gap-1 whitespace-nowrap"
          aria-label="View full troubleshooting details"
        >
          View Full Details
          <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};
