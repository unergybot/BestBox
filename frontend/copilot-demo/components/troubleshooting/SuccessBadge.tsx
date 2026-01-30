"use client";

import React from "react";

interface SuccessBadgeProps {
  trialVersion: string;
  status: string | null;
  className?: string;
}

export const SuccessBadge: React.FC<SuccessBadgeProps> = ({
  trialVersion,
  status,
  className = "",
}) => {
  const isSuccess = status === "OK";
  const isPending = status === null || status === undefined;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold ${
        isSuccess
          ? "bg-green-100 text-green-800 border border-green-200"
          : isPending
          ? "bg-gray-100 text-gray-600 border border-gray-200"
          : "bg-red-100 text-red-800 border border-red-200"
      } ${className}`}
    >
      <span>{trialVersion}:</span>
      {isSuccess ? (
        <span className="flex items-center gap-0.5">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          OK
        </span>
      ) : isPending ? (
        <span>Pending</span>
      ) : (
        <span className="flex items-center gap-0.5">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
          NG
        </span>
      )}
    </span>
  );
};
