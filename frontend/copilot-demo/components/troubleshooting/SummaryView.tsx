// frontend/copilot-demo/components/troubleshooting/SummaryView.tsx
"use client";

import React from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SuccessBadge } from "./SuccessBadge";
import { RelevanceScore } from "./RelevanceScore";

interface SummaryViewProps {
  data: TroubleshootingIssue;
  onExpand: () => void;
  className?: string;
}

export const SummaryView: React.FC<SummaryViewProps> = ({
  data,
  onExpand,
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
      className={`bg-white border-2 border-teal-200 rounded-lg shadow-sm hover:shadow-md transition-shadow ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-700">
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
      <div className="p-4 space-y-2">
        {/* Problem */}
        <div>
          <span className="text-xs font-medium text-gray-500">Problem:</span>
          <p className="text-sm text-gray-800 mt-0.5">
            {truncate(data.problem, 80)}
          </p>
        </div>

        {/* Solution */}
        <div>
          <span className="text-xs font-medium text-gray-500">Solution:</span>
          <p className="text-sm text-gray-600 mt-0.5">
            {truncate(data.solution, 120)}
          </p>
        </div>

        {/* Image preview */}
        {data.image_count > 0 && data.images?.length > 0 && (
          <div className="flex items-center gap-1 pt-2">
            <div className="flex gap-1">
              {data.images.slice(0, 3).map((img) => (
                <div
                  key={img.image_id}
                  className="w-16 h-16 bg-gray-100 rounded border border-gray-200 overflow-hidden"
                >
                  <img
                    src={img.image_url}
                    alt={img.description || "Defect image"}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                </div>
              ))}
            </div>
            {data.image_count > 3 && (
              <span className="text-xs text-gray-500 ml-1">
                +{data.image_count - 3} more
              </span>
            )}
          </div>
        )}

        {/* Metadata row */}
        <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
          Part: {data.part_number}
          {data.category && ` | Category: ${data.category}`}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <div className="text-xs text-gray-500">
          {/* Placeholder for social metrics (Phase 4) */}
          👍 0 helpful
        </div>
        <button
          onClick={onExpand}
          className="text-sm font-medium text-teal-600 hover:text-teal-700 flex items-center gap-1"
          aria-label="View full troubleshooting details"
        >
          View Full Details
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
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
