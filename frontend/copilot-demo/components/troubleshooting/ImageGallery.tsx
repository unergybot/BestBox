// frontend/copilot-demo/components/troubleshooting/ImageGallery.tsx
"use client";

import React from "react";
import { TroubleshootingImage } from "@/types/troubleshooting";

interface ImageGalleryProps {
  images: TroubleshootingImage[];
  onImageClick: (index: number) => void;
  variant: "compact" | "grid";
  className?: string;
}

export const ImageGallery: React.FC<ImageGalleryProps> = ({
  images,
  onImageClick,
  variant,
  className = "",
}) => {
  if (!images || images.length === 0) {
    return null;
  }

  if (variant === "compact") {
    return (
      <div className={`flex items-center gap-1.5 pt-2 overflow-x-auto ${className}`}>
        {images.map((img, index) => (
          <button
            key={img.image_id}
            onClick={() => onImageClick(index)}
            className="w-12 h-12 sm:w-14 sm:h-14 bg-gray-100 rounded border border-gray-200 overflow-hidden flex-shrink-0 cursor-pointer hover:border-teal-400 hover:shadow-md transition-all focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-1"
            aria-label={`View image ${index + 1}: ${img.description || "Defect image"}`}
          >
            <img
              src={img.image_url}
              alt={img.description || "Defect image"}
              className="w-full h-full object-cover"
              loading="lazy"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = "none";
              }}
            />
          </button>
        ))}
        <span className="text-xs text-gray-500 ml-1 flex-shrink-0 whitespace-nowrap">
          {images.length} image{images.length > 1 ? "s" : ""}
        </span>
      </div>
    );
  }

  // Grid variant
  return (
    <div className={`grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 sm:gap-3 ${className}`}>
      {images.map((img, index) => (
        <button
          key={img.image_id}
          onClick={() => onImageClick(index)}
          className="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200 hover:border-teal-400 hover:scale-[1.02] transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2"
          aria-label={`View image ${index + 1}: ${img.description || "Defect image"}`}
        >
          <img
            src={img.image_url}
            alt={img.description || `Image ${img.image_id}`}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.src = "/placeholder-image.svg";
              target.alt = "Image failed to load";
            }}
          />
          {/* Hover overlay with zoom icon */}
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
            <svg
              className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
              />
            </svg>
          </div>
          {/* Description tooltip on hover */}
          {img.description && (
            <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white text-xs p-1.5 sm:p-2 opacity-0 group-hover:opacity-100 transition-opacity line-clamp-2">
              {img.description}
            </div>
          )}
        </button>
      ))}
    </div>
  );
};
