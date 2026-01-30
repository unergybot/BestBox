// frontend/copilot-demo/components/troubleshooting/TroubleshootingCardDetector.tsx
"use client";

import React from "react";
import { detectTroubleshootingResults } from "@/lib/troubleshooting-detector";
import { TroubleshootingCard } from "./TroubleshootingCard";
import { TroubleshootingIssue } from "@/types/troubleshooting";

interface TroubleshootingCardDetectorProps {
  message: string;
  className?: string;
}

export const TroubleshootingCardDetector: React.FC<
  TroubleshootingCardDetectorProps
> = ({ message, className = "" }) => {
  const results = detectTroubleshootingResults(message);

  // Only render if we found troubleshooting results
  if (results.length === 0) {
    return null;
  }

  // Filter to only specific_solution type (ignore full_case for now)
  const issues = results.filter(
    (r): r is TroubleshootingIssue => r.result_type === "specific_solution"
  );

  if (issues.length === 0) {
    return null;
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {issues.map((issue, idx) => (
        <TroubleshootingCard
          key={`${issue.case_id}-${issue.issue_number}-${idx}`}
          data={issue}
        />
      ))}
    </div>
  );
};
