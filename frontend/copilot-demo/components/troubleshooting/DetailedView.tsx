// frontend/copilot-demo/components/troubleshooting/DetailedView.tsx
"use client";

import React from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SuccessBadge } from "./SuccessBadge";
import { RelevanceScore } from "./RelevanceScore";
import { TrialTimeline } from "./TrialTimeline";

interface DetailedViewProps {
  data: TroubleshootingIssue;
  onCollapse: () => void;
  className?: string;
}

export const DetailedView: React.FC<DetailedViewProps> = ({
  data,
  onCollapse,
  className = "",
}) => {
  return (
    <div
      className={`bg-white border-2 border-teal-300 rounded-lg shadow-lg max-w-full ${className}`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 sm:p-4 border-b-2 border-teal-100">
        <div className="flex items-start gap-2 sm:gap-3 min-w-0 flex-1">
          <button
            onClick={onCollapse}
            className="text-gray-500 hover:text-gray-700 flex-shrink-0 mt-0.5"
            aria-label="Collapse details"
          >
            <svg
              className="w-4 h-4 sm:w-5 sm:h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <div className="min-w-0 flex-1">
            <h3 className="text-base sm:text-lg font-semibold text-gray-800 break-words">
              Case {data.case_id} #{data.issue_number}
            </h3>
            <p className="text-xs sm:text-sm text-gray-500 break-words">
              Part: {data.part_number} | Trial: {data.trial_version}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <SuccessBadge
            trialVersion={data.trial_version}
            status={data.result_t2 || data.result_t1 || null}
          />
          {data.severity && (
            <span className={`px-2 py-1 rounded-full text-xs font-semibold uppercase ${data.severity.toLowerCase() === 'critical' || data.severity.toLowerCase() === 'high' ? 'bg-red-100 text-red-700' :
                data.severity.toLowerCase() === 'medium' ? 'bg-orange-100 text-orange-700' :
                  'bg-blue-100 text-blue-700'
              }`}>
              {data.severity}
            </span>
          )}
          <RelevanceScore score={data.relevance_score} />
        </div>
      </div>

      {/* Content */}
      <div className="p-3 sm:p-4 md:p-6 space-y-4 sm:space-y-6">
        {/* Problem & Solution */}
        <div className="space-y-3 sm:space-y-4">
          <div className="min-w-0">
            <h4 className="text-xs sm:text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span aria-hidden="true">📋</span>
              Problem
            </h4>
            <p className="text-xs sm:text-sm text-gray-800 leading-relaxed whitespace-pre-wrap break-words">
              {data.problem}
            </p>
          </div>

          <div className="min-w-0">
            <h4 className="text-xs sm:text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span aria-hidden="true">✅</span>
              Solution
            </h4>
            <p className="text-xs sm:text-sm text-gray-800 leading-relaxed whitespace-pre-wrap break-words">
              {data.solution}
            </p>
          </div>
        </div>

        {/* Trial Timeline */}
        <div className="overflow-x-auto">
          <h4 className="text-xs sm:text-sm font-semibold text-gray-700 mb-3">
            Trial Progression
          </h4>
          <TrialTimeline
            trialVersion={data.trial_version}
            resultT1={data.result_t1 || null}
            resultT2={data.result_t2 || null}
          />
        </div>

        {/* Images */}
        {data.images.length > 0 && (
          <div>
            <h4 className="text-xs sm:text-sm font-semibold text-gray-700 mb-3">
              Visual Evidence ({data.image_count} images)
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
              {data.images.map((img) => (
                <div
                  key={img.image_id}
                  className="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200 hover:border-teal-400 transition-colors"
                >
                  <img
                    src={img.image_url}
                    alt={img.description || `Image ${img.image_id}`}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.src = "/placeholder-image.png";
                      target.alt = "Image failed to load";
                    }}
                  />
                  {img.description && (
                    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-1 sm:p-2 opacity-0 group-hover:opacity-100 transition-opacity break-words">
                      {img.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="pt-3 sm:pt-4 border-t border-gray-200">
          <h4 className="text-xs sm:text-sm font-semibold text-gray-700 mb-2">
            Case Details
          </h4>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-xs sm:text-sm">
            <div className="min-w-0">
              <dt className="text-gray-500">Case ID</dt>
              <dd className="text-gray-800 font-medium break-words">{data.case_id}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-gray-500">Part Number</dt>
              <dd className="text-gray-800 font-medium break-words">{data.part_number}</dd>
            </div>
            {data.category && (
              <div className="min-w-0">
                <dt className="text-gray-500">Category</dt>
                <dd className="text-gray-800 font-medium break-words">{data.category}</dd>
              </div>
            )}
            {data.defect_types && data.defect_types.length > 0 && (
              <div className="min-w-0">
                <dt className="text-gray-500">Defect Types</dt>
                <dd className="text-gray-800 font-medium break-words">
                  {data.defect_types.join(", ")}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* VLM Insights */}
        {(data.key_insights || data.tags) && (
          <div className="pt-3 sm:pt-4 border-t border-gray-200">
            {data.tags && data.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {data.tags.map(tag => (
                  <span key={tag} className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 text-xs border border-indigo-100">
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {data.key_insights && data.key_insights.length > 0 && (
              <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                <h4 className="text-xs sm:text-sm font-semibold text-amber-800 mb-2 flex items-center gap-1">
                  <span aria-hidden="true">🤖</span> AI Insights
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  {data.key_insights.map((insight, i) => (
                    <li key={i} className="text-xs sm:text-sm text-amber-900 leading-relaxed">
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer - Placeholder for Phase 4 social features */}
      <div className="px-3 sm:px-4 md:px-6 py-3 sm:py-4 bg-gray-50 border-t border-gray-200">
        <div className="text-xs text-gray-500 break-words">
          👍 Mark as Helpful | 💬 Comments | 🔗 Share
        </div>
      </div>
    </div>
  );
};
