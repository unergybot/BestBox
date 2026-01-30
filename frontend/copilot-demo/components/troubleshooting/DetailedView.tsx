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
      className={`bg-white border-2 border-teal-300 rounded-lg shadow-lg ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-2 border-teal-100">
        <div className="flex items-center gap-3">
          <button
            onClick={onCollapse}
            className="text-gray-500 hover:text-gray-700"
            aria-label="Collapse details"
          >
            <svg
              className="w-5 h-5"
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
          <div>
            <h3 className="text-lg font-semibold text-gray-800">
              Case {data.case_id} #{data.issue_number}
            </h3>
            <p className="text-sm text-gray-500">
              Part: {data.part_number} | Trial: {data.trial_version}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SuccessBadge
            trialVersion={data.trial_version}
            status={data.result_t2 || data.result_t1 || null}
          />
          <RelevanceScore score={data.relevance_score} />
        </div>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Problem & Solution */}
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span aria-hidden="true">📋</span>
              Problem
            </h4>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {data.problem}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span aria-hidden="true">✅</span>
              Solution
            </h4>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {data.solution}
            </p>
          </div>
        </div>

        {/* Trial Timeline */}
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">
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
            <h4 className="text-sm font-semibold text-gray-700 mb-3">
              Visual Evidence ({data.image_count} images)
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
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
                    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {img.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="pt-4 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">
            Case Details
          </h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-gray-500">Case ID</dt>
              <dd className="text-gray-800 font-medium">{data.case_id}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Part Number</dt>
              <dd className="text-gray-800 font-medium">{data.part_number}</dd>
            </div>
            {data.category && (
              <div>
                <dt className="text-gray-500">Category</dt>
                <dd className="text-gray-800 font-medium">{data.category}</dd>
              </div>
            )}
            {data.defect_types && data.defect_types.length > 0 && (
              <div>
                <dt className="text-gray-500">Defect Types</dt>
                <dd className="text-gray-800 font-medium">
                  {data.defect_types.join(", ")}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Footer - Placeholder for Phase 4 social features */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          👍 Mark as Helpful | 💬 Comments | 🔗 Share
        </div>
      </div>
    </div>
  );
};
