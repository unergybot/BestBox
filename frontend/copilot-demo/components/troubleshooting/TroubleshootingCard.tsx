// frontend/copilot-demo/components/troubleshooting/TroubleshootingCard.tsx
"use client";

import React, { useState, useCallback } from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SummaryView } from "./SummaryView";
import { DetailedView } from "./DetailedView";
import { ImageLightbox } from "./ImageLightbox";

interface TroubleshootingCardProps {
  data: TroubleshootingIssue;
  className?: string;
}

export const TroubleshootingCard: React.FC<TroubleshootingCardProps> = ({
  data,
  className = "",
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [lightbox, setLightbox] = useState({ isOpen: false, index: 0 });

  const handleImageClick = useCallback((index: number) => {
    setLightbox({ isOpen: true, index });
  }, []);

  const handleLightboxClose = useCallback(() => {
    setLightbox((prev) => ({ ...prev, isOpen: false }));
  }, []);

  const handleLightboxNavigate = useCallback((index: number) => {
    setLightbox((prev) => ({ ...prev, index }));
  }, []);

  return (
    <div className={className}>
      {isExpanded ? (
        <DetailedView
          data={data}
          onCollapse={() => setIsExpanded(false)}
          onImageClick={handleImageClick}
        />
      ) : (
        <SummaryView
          data={data}
          onExpand={() => setIsExpanded(true)}
          onImageClick={handleImageClick}
        />
      )}

      {/* Image Lightbox */}
      {lightbox.isOpen && data.images && data.images.length > 0 && (
        <ImageLightbox
          images={data.images}
          currentIndex={lightbox.index}
          onClose={handleLightboxClose}
          onNavigate={handleLightboxNavigate}
        />
      )}
    </div>
  );
};
