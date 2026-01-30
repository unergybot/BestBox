// frontend/copilot-demo/components/troubleshooting/TrialTimeline.tsx
"use client";

import React from "react";

interface TrialTimelineProps {
  trialVersion: string;
  resultT1: string | null;
  resultT2: string | null;
  className?: string;
}

export const TrialTimeline: React.FC<TrialTimelineProps> = ({
  trialVersion,
  resultT1,
  resultT2,
  className = "",
}) => {
  const trials = [
    { version: "T0", result: null }, // T0 always pending/unknown
    { version: "T1", result: resultT1 },
    { version: "T2", result: resultT2 },
  ];

  // Find current trial index
  const currentIndex = trials.findIndex((t) => t.version === trialVersion);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {trials.map((trial, index) => {
        const isActive = index <= currentIndex;
        const isSuccess = trial.result === "OK";
        const isFailed = trial.result === "NG";
        const isPending = trial.result === null;

        return (
          <React.Fragment key={trial.version}>
            {/* Trial node */}
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                  isSuccess
                    ? "bg-green-500 text-white"
                    : isFailed
                    ? "bg-red-500 text-white"
                    : isActive
                    ? "bg-blue-500 text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                {isSuccess ? (
                  <svg
                    className="w-4 h-4"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    role="img"
                    aria-label="Success"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : isFailed ? (
                  <svg
                    className="w-4 h-4"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    role="img"
                    aria-label="Failed"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  trial.version
                )}
              </div>
              <span className="text-[10px] text-gray-500 mt-1">{trial.version}</span>
            </div>

            {/* Arrow connector (except after last item) */}
            {index < trials.length - 1 && (
              <svg
                className={`w-4 h-4 ${
                  isActive ? "text-blue-500" : "text-gray-300"
                }`}
                fill="currentColor"
                viewBox="0 0 20 20"
                role="img"
                aria-label="Next step"
              >
                <path
                  fillRule="evenodd"
                  d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
