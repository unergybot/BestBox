// frontend/copilot-demo/components/troubleshooting/TroubleshootingCard.tsx
"use client";

import React, { useState } from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SummaryView } from "./SummaryView";
import { DetailedView } from "./DetailedView";

interface TroubleshootingCardProps {
  data: TroubleshootingIssue;
  className?: string;
}

export const TroubleshootingCard: React.FC<TroubleshootingCardProps> = ({
  data,
  className = "",
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={className}>
      {isExpanded ? (
        <DetailedView
          data={data}
          onCollapse={() => setIsExpanded(false)}
        />
      ) : (
        <SummaryView
          data={data}
          onExpand={() => setIsExpanded(true)}
        />
      )}
    </div>
  );
};
