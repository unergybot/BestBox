// frontend/copilot-demo/components/troubleshooting/ImageLightbox.tsx
"use client";

import React, { useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { TroubleshootingImage } from "@/types/troubleshooting";

interface ImageLightboxProps {
  images: TroubleshootingImage[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export const ImageLightbox: React.FC<ImageLightboxProps> = ({
  images,
  currentIndex,
  onClose,
  onNavigate,
}) => {
  const currentImage = images[currentIndex];
  const hasMultiple = images.length > 1;

  const goToPrev = useCallback(() => {
    onNavigate(currentIndex > 0 ? currentIndex - 1 : images.length - 1);
  }, [currentIndex, images.length, onNavigate]);

  const goToNext = useCallback(() => {
    onNavigate(currentIndex < images.length - 1 ? currentIndex + 1 : 0);
  }, [currentIndex, images.length, onNavigate]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft" && hasMultiple) {
        goToPrev();
      } else if (e.key === "ArrowRight" && hasMultiple) {
        goToNext();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    // Prevent body scroll when lightbox is open
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose, goToPrev, goToNext, hasMultiple]);

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const lightboxContent = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Image viewer"
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between p-4">
        <button
          onClick={onClose}
          className="p-2 text-white hover:text-teal-300 transition-colors rounded-full hover:bg-white/10"
          aria-label="Close lightbox"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        {hasMultiple && (
          <span className="text-white text-sm font-medium bg-black/50 px-3 py-1 rounded-full">
            {currentIndex + 1} / {images.length}
          </span>
        )}
      </div>

      {/* Navigation - Previous */}
      {hasMultiple && (
        <button
          onClick={goToPrev}
          className="absolute left-2 sm:left-4 p-2 sm:p-3 text-white hover:text-teal-300 transition-colors rounded-full hover:bg-white/10"
          aria-label="Previous image"
        >
          <svg className="w-8 h-8 sm:w-10 sm:h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Main Image */}
      <div className="flex flex-col items-center max-w-[90vw] max-h-[85vh]">
        <img
          src={currentImage.image_url}
          alt={currentImage.description || `Image ${currentIndex + 1}`}
          className="max-w-full max-h-[70vh] object-contain rounded-lg shadow-2xl"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.src = "/placeholder-image.svg";
            target.alt = "Image failed to load";
          }}
        />

        {/* Description */}
        {currentImage.description && (
          <div className="mt-4 max-w-2xl bg-black/70 text-white text-sm p-3 rounded-lg line-clamp-3">
            {currentImage.defect_type && (
              <span className="inline-block bg-teal-600 text-white text-xs px-2 py-0.5 rounded mr-2 mb-1">
                {currentImage.defect_type}
              </span>
            )}
            {currentImage.description}
          </div>
        )}
      </div>

      {/* Navigation - Next */}
      {hasMultiple && (
        <button
          onClick={goToNext}
          className="absolute right-2 sm:right-4 p-2 sm:p-3 text-white hover:text-teal-300 transition-colors rounded-full hover:bg-white/10"
          aria-label="Next image"
        >
          <svg className="w-8 h-8 sm:w-10 sm:h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}
    </div>
  );

  // Render via portal to document.body
  if (typeof window === "undefined") {
    return null;
  }

  return createPortal(lightboxContent, document.body);
};
