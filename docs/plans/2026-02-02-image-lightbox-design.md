# Image Lightbox Design for Troubleshooting Cards

**Date:** 2026-02-02
**Status:** Approved

## Overview

Enhance troubleshooting card image display to show all images and allow viewing original quality via a lightbox modal.

## Requirements

1. Show ALL images in both Summary and Detailed views (not just 3)
2. Click any thumbnail to open a lightbox with full-size image
3. Navigate between images with arrows and keyboard
4. Match existing teal/gray design system

## Component Architecture

```
components/troubleshooting/
├── ImageLightbox.tsx      # New - modal overlay with full-size image viewer
├── ImageGallery.tsx       # New - reusable thumbnail grid with click handlers
├── SummaryView.tsx        # Modified - use ImageGallery, show all images
├── DetailedView.tsx       # Modified - use ImageGallery, show all images
└── TroubleshootingCard.tsx # Modified - manage lightbox state at card level
```

### Data Flow

1. `TroubleshootingCard` holds lightbox state: `{ isOpen: boolean, currentIndex: number }`
2. `ImageGallery` renders thumbnails and calls `onImageClick(index)` when clicked
3. `ImageLightbox` receives `images[]`, `currentIndex`, `onClose`, `onNavigate`

## ImageLightbox Component

### Visual Layout

```
┌─────────────────────────────────────────────────────────┐
│ [X]                                              1 / 4  │
│                                                         │
│   ◀                    [IMAGE]                    ▶     │
│                                                         │
│─────────────────────────────────────────────────────────│
│ Description: 披锋缺陷位于分型线处，表现为毛边...          │
└─────────────────────────────────────────────────────────┘
```

### Features

- **Backdrop**: `bg-black/80` overlay, click outside image to close
- **Image**: Centered, `max-w-[90vw] max-h-[80vh]`, `object-contain`
- **Navigation**: Left/right arrows, hidden if only 1 image
- **Counter**: "2 / 5" indicator in top-right
- **Description**: Shown below image in semi-transparent bar
- **Close**: X button in top-right corner

### Keyboard Support

- `Escape` → close lightbox
- `ArrowLeft` → previous image
- `ArrowRight` → next image

### Accessibility

- `role="dialog"` and `aria-modal="true"`
- Focus trap inside lightbox
- `aria-label` on navigation buttons

## ImageGallery Component

```typescript
interface ImageGalleryProps {
  images: TroubleshootingImage[];
  onImageClick: (index: number) => void;
  variant: 'compact' | 'grid';
}
```

### Compact Variant (SummaryView)

- Horizontal scrollable row
- Thumbnails: `w-12 h-12 sm:w-14 sm:h-14`
- Shows ALL images with horizontal scroll

### Grid Variant (DetailedView)

- Grid layout: `grid-cols-2 sm:grid-cols-3 md:grid-cols-4`
- Aspect-square thumbnails
- Hover effect: `border-teal-400` + scale transform

## Edge Cases

| Case | Handling |
|------|----------|
| Image load error | Show placeholder, don't break navigation |
| No images | ImageGallery renders nothing |
| Single image | Hide arrows and counter |
| Long descriptions | Truncate with `line-clamp-3` |
| Mobile | Full viewport lightbox, 44px touch targets |

## Implementation Steps

1. Create `ImageLightbox.tsx` component
2. Create `ImageGallery.tsx` component
3. Update `TroubleshootingCard.tsx` to manage lightbox state
4. Update `SummaryView.tsx` to use ImageGallery
5. Update `DetailedView.tsx` to use ImageGallery
6. Test with real troubleshooting data
