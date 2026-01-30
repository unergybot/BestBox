# Troubleshooting KB Document Preview System - Design

**Date**: 2026-01-29
**Status**: Approved - Ready for Implementation
**Author**: Claude Sonnet 4.5

---

## Executive Summary

Design for a rich document preview system that displays troubleshooting knowledge base results in the chat interface as interactive cards with high-quality image support, smart grouping, and collaborative features.

**Key Goals:**
- Make troubleshooting cases visually scannable in chat
- Prioritize image quality for defect analysis (critical for manufacturing)
- Enable quick comparison of multiple solutions
- Build collaborative knowledge over time

---

## 1. Architecture Overview

### 1.1 Component Flow

```
Agent (Mold Agent)
  ↓ Uses search_troubleshooting_kb tool
  ↓ Returns JSON in chat message
Frontend (Chat Message Renderer)
  ↓ Detects ```json blocks
  ↓ Identifies troubleshooting result structure
TroubleshootingPreviewCard Component
  ↓ Renders summary (collapsed) or details (expanded)
  ↓ Fetches additional data if needed
```

### 1.2 Key Design Decisions

1. **Progressive Enhancement**: Existing JSON responses work as-is. Frontend enhancement is additive - no backend changes required initially.

2. **No Backend Changes Required Initially**: The agent tools already return rich JSON with all needed data (images, metadata, scores). Frontend simply renders it beautifully.

3. **Two-Level Rendering**:
   - **Level 1 (Summary)**: Inline card in chat, ~150-200px tall, shows key info
   - **Level 2 (Expanded)**: Modal or expanded section, optimized for detail viewing

4. **Data Format Detection**: Frontend looks for JSON blocks with `"result_type": "specific_solution"` or `"full_case"` to identify troubleshooting results.

5. **Component Library**: Use Tailwind CSS + shadcn/ui for consistent styling with existing BestBox UI.

---

## 2. UI Design

### 2.1 Summary Card (Inline View)

**Visual Layout:**

```
┌─────────────────────────────────────────────────────┐
│ 🏭 Case #1947688-14  [T2: ✓ OK]    Score: 0.74     │
├─────────────────────────────────────────────────────┤
│ Problem: 产品披锋                                    │
│ Solution: 设计改图，将3016工件图示位置加铁0.03mm...  │
│                                                      │
│ [img] [img] [img] +2 more                           │
│                                                      │
│ Part: 1947688 | Material: PC | Category: C9         │
│                                                      │
│ [👍 12 helpful] [💬 3 comments] [View Full Details →]│
└─────────────────────────────────────────────────────┘
```

**Information Hierarchy (Summary):**
- **Header**: Case ID, issue number, trial success status, relevance score
- **Body**:
  - Problem text (1 line, truncated)
  - Solution preview (2-3 lines, truncated with "...")
  - Image thumbnails (first 2-3, show "+N more" indicator)
  - Key metadata (part number, material, category)
- **Footer**: Social metrics (helpful count, comments), expand button

**Component Structure:**

```tsx
<TroubleshootingCard variant="summary">
  <CardHeader>
    <Badge>Case ID + Issue Number</Badge>
    <SuccessIndicator>T2: OK/NG</SuccessIndicator>
    <RelevanceScore>0.74</RelevanceScore>
  </CardHeader>

  <CardBody>
    <ProblemText>1 line, truncated</ProblemText>
    <SolutionPreview>2-3 lines, truncated with "..."</SolutionPreview>
    <ImageThumbnails max={3} grouped={false} />
    <MetadataRow>Part, Material, Category</MetadataRow>
  </CardBody>

  <CardFooter>
    <SocialMetrics>Helpful count, comments</SocialMetrics>
    <ExpandButton>View Full Details</ExpandButton>
  </CardFooter>
</TroubleshootingCard>
```

**Styling Notes:**
- Card: Subtle border, white background, shadow on hover
- Success badge: Green (OK), Red (NG), Gray (pending)
- Relevance score: Color-coded (>0.7 green, 0.5-0.7 yellow, <0.5 gray)
- Images: Responsive thumbnails with rounded corners
- Teal accent color to match mold scenario theme

### 2.2 Expanded Detail View

**Modal/Panel Layout:**

```
┌─────────────────────────────────────────────────────────┐
│ ← Back to Chat    Case TS-1947688-ED736A0501 #14    [×] │
├─────────────────────────────────────────────────────────┤
│ Header Section:                                          │
│   🏭 Part 1947688 | Material: PC | Mold: ED736A0501     │
│   Relevance: ████████░░ 0.74 | Status: T2 ✓ Success     │
├─────────────────────────────────────────────────────────┤
│ Problem & Solution:                                      │
│   📋 Problem                                             │
│   1.产品披锋 (Product Flash Defect)                      │
│                                                          │
│   ✅ Solution                                            │
│   1、设计改图，将3016工件图示位置加铁0.03mm，           │
│   修正产品披锋。                                         │
│   [📋 Copy] [📄 Export PDF]                              │
├─────────────────────────────────────────────────────────┤
│ Trial Timeline:                                          │
│   T0 → T1 (OK) → T2 (OK) ✓                              │
│   [Visual timeline with checkmarks/crosses]              │
├─────────────────────────────────────────────────────────┤
│ Visual Evidence (9 images grouped):                      │
│   ▼ Product Edge Defects (4 images)                     │
│     [img] [img] [img] [img]                             │
│   ▼ Mold Surface (3 images)                             │
│     [img] [img] [img]                                   │
│   ▼ After Treatment (2 images)                          │
│     [img] [img]                                         │
├─────────────────────────────────────────────────────────┤
│ Community Feedback:                                      │
│   👍 Mark as Helpful (12) | 💬 Comments (3)              │
│   🔗 Share Link | 🔖 Save to My Cases                    │
├─────────────────────────────────────────────────────────┤
│ Related Cases (AI-suggested):                            │
│   • Case #1947688-07: Similar flash issue → T1 OK       │
│   • Case #2103456-12: Edge defect solution → T2 OK      │
└─────────────────────────────────────────────────────────┘
```

**Expanded View Features:**

1. **Trial Timeline Visualization**: Shows progression T0→T1→T2 with visual indicators
2. **Smart Image Grouping**: Images grouped by defect_type or equipment_part
3. **Action Buttons**: Copy solution, export PDF, accessible in header
4. **Collaborative Elements**: Helpful counter, comments, share link
5. **Related Cases**: Vector similarity search for discovery

---

## 3. Image Handling (High-Quality Focus)

### 3.1 Responsive Sizing Strategy

**Adaptive Thumbnails:**

| View | Mobile | Desktop (PC) |
|------|--------|--------------|
| Summary thumbnails | 100x100px | 160x160px |
| Expanded thumbnails | 200x200px | 300x300px |
| Sidebar width | 100% | 900px |
| Hover preview | Full resolution | Full resolution |

**CSS Implementation:**

```css
/* Summary view thumbnails */
.thumbnail-summary {
  width: 100px;
  height: 100px;
  object-fit: cover;
}

@media (min-width: 1024px) {
  .thumbnail-summary {
    width: 160px;
    height: 160px;
  }
}

/* Expanded view thumbnails */
.thumbnail-expanded {
  width: 200px;
  height: 200px;
  object-fit: cover;
}

@media (min-width: 1024px) {
  .thumbnail-expanded {
    width: 300px;
    height: 300px;
  }
}

/* Sidebar expansion */
.copilot-sidebar-expanded {
  width: 100%;
}

@media (min-width: 1024px) {
  .copilot-sidebar-expanded {
    width: 900px;
  }
}
```

### 3.2 Hover Preview (Tooltip-Style)

**Interaction Model:**
- Hover over any thumbnail → Full resolution image appears next to cursor
- Follows mouse movement
- Appears with 100ms delay (prevents accidental triggers)
- Size: Up to 800x800px on PC, scales to fit screen
- No click required - optimized for fast scanning

**Component Implementation:**

```tsx
function HoverImagePreview({ thumbnail, fullResUrl }) {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  return (
    <>
      <img
        src={thumbnail}
        className="cursor-zoom-in"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onMouseMove={(e) => setPosition({
          x: e.clientX + 20,  // Offset from cursor
          y: e.clientY + 20
        })}
      />

      {isHovered && (
        <Portal>
          <div
            className="fixed z-50 pointer-events-none"
            style={{
              left: position.x,
              top: position.y,
              maxWidth: '800px',
              maxHeight: '800px'
            }}
          >
            <img
              src={fullResUrl}  // Original quality
              className="shadow-2xl border-4 border-white rounded"
              alt="Full resolution preview"
            />
          </div>
        </Portal>
      )}
    </>
  );
}
```

### 3.3 Smart Image Grouping

**Grouping Algorithm:**

```typescript
function groupImagesByDefect(images: Image[]) {
  // Primary: Group by defect_type (from VL metadata)
  const byDefect = images.reduce((groups, img) => {
    const key = img.defect_type || 'Other';
    groups[key] = groups[key] || [];
    groups[key].push(img);
    return groups;
  }, {});

  // Sort groups by priority
  const priority = ['产品披锋', '拉白', '火花纹', '模具污染', 'Other'];
  return priority
    .filter(key => byDefect[key])
    .map(key => ({
      groupName: key,
      images: byDefect[key],
      count: byDefect[key].length
    }));
}
```

**Fallback Strategy (VL Disabled):**

Since VL is currently disabled, implement fallbacks:
1. **Fallback 1**: Group by `equipment_part` if available
2. **Fallback 2**: Group by cell location proximity (images within 20 rows)
3. **Fallback 3**: Single group "All Images" if no metadata

### 3.4 Image Quality & Loading

**Quality Settings:**
- **Thumbnails**: Serve at 2x display size for retina (160x160 → 320px source)
- **Full Resolution**: Original quality, no compression
- **Format**: WebP with JPEG fallback for compatibility

**Loading Strategy:**
- Thumbnails: Eager-loaded for visible cards
- Full-res: Preloaded on hover (100ms delay)
- Lazy loading: Images below fold load on scroll

---

## 4. Technical Implementation

### 4.1 Component Structure

```
components/troubleshooting/
  ├── TroubleshootingCardDetector.tsx    // Scans chat for JSON
  ├── TroubleshootingCard.tsx            // Main card wrapper
  ├── SummaryView.tsx                    // Collapsed inline view
  ├── DetailedView.tsx                   // Expanded modal view
  ├── ImageGallery.tsx                   // Grouped image display
  ├── HoverImagePreview.tsx              // Cursor-following preview
  ├── TrialTimeline.tsx                  // T0→T1→T2 visualization
  └── RelatedCases.tsx                   // Similar cases suggestions
```

### 4.2 Detection & Rendering

```tsx
// In CopilotKit message renderer
function detectTroubleshootingResults(message: string) {
  const jsonBlocks = extractCodeBlocks(message, 'json');

  return jsonBlocks
    .map(block => JSON.parse(block))
    .filter(data =>
      data.result_type === 'specific_solution' ||
      data.result_type === 'full_case'
    );
}

// Auto-render cards
{message.content.includes('```json') && (
  <TroubleshootingCardDetector message={message.content}>
    {(results) => results.map(result => (
      <TroubleshootingCard key={result.case_id} data={result} />
    ))}
  </TroubleshootingCardDetector>
)}
```

### 4.3 State Management

- **Local State**: Card expanded/collapsed (React.useState)
- **Global State**: User feedback stored in PostgreSQL
- **Cache**: Images cached in browser (Service Worker)
- **Session**: Opened cases tracked for "Related Cases"

---

## 5. Data Flow & Caching

### 5.1 End-to-End Flow

```
User query: "产品披锋怎么解决？"
  ↓
Mold Agent → search_troubleshooting_kb()
  ↓
Returns JSON with:
  - Case metadata
  - Problem/solution text
  - Image URLs: /api/troubleshooting/images/{image_id}.jpg
  - Image metadata (defect_type, description)
  ↓
Agent includes JSON in response
  ↓
Frontend detects & renders TroubleshootingCard
  ↓
Images loaded progressively:
  - Summary: 3 thumbnails loaded immediately
  - Hover: Full-res preloaded on mouseEnter
  - Expanded: All thumbnails lazy-loaded
```

### 5.2 Caching Strategy

**Three-Layer Cache:**

1. **Browser Cache (Service Worker)**
   - Thumbnails: 7 days cache
   - Full-res images: 3 days cache
   - Cache-first strategy

2. **CDN/Reverse Proxy (Nginx)**
   ```nginx
   location /api/troubleshooting/images/ {
     alias /home/unergy/BestBox/data/troubleshooting/processed/images/;
     expires 30d;
     add_header Cache-Control "public, immutable";
   }
   ```

3. **Backend (FastAPI)**
   ```python
   @app.get("/api/troubleshooting/images/{image_id}.jpg")
   async def serve_image(image_id: str, size: str = "original"):
     # size: "thumb-160", "thumb-300", "original"
     # Generate/cache thumbnails on first request
   ```

### 5.3 Progressive Loading

1. **Initial render** (0ms): Skeleton placeholders
2. **First pass** (0-500ms): Load visible thumbnails (low priority)
3. **On hover** (100ms delay): Preload full-res (high priority)
4. **On expand**: Lazy-load expanded view thumbnails in viewport
5. **Background**: Preload full-res for all visible thumbnails

---

## 6. Collaborative Features

### 6.1 Database Schema

```sql
-- Feedback tracking
CREATE TABLE troubleshooting_feedback (
  id SERIAL PRIMARY KEY,
  case_id VARCHAR(100) NOT NULL,
  issue_number INTEGER,
  user_id VARCHAR(100),
  action_type VARCHAR(20) NOT NULL,  -- 'helpful', 'not_helpful'
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(case_id, issue_number, user_id, action_type)
);

-- Comments
CREATE TABLE troubleshooting_comments (
  id SERIAL PRIMARY KEY,
  case_id VARCHAR(100) NOT NULL,
  issue_number INTEGER,
  user_id VARCHAR(100) NOT NULL,
  user_name VARCHAR(100),
  comment_text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_feedback_case ON troubleshooting_feedback(case_id, issue_number);
CREATE INDEX idx_comments_case ON troubleshooting_comments(case_id, issue_number);
```

### 6.2 API Endpoints

```typescript
// Mark as helpful
POST /api/troubleshooting/feedback
Body: { case_id, issue_number, action: "helpful" | "not_helpful" }
Response: { helpful_count: 13, user_has_marked: true }

// Get feedback stats
GET /api/troubleshooting/feedback/{case_id}/{issue_number}
Response: { helpful_count, not_helpful_count, user_has_marked, comments_count }

// Add comment
POST /api/troubleshooting/comments
Body: { case_id, issue_number, comment_text }

// Get comments
GET /api/troubleshooting/comments/{case_id}/{issue_number}
Response: { comments: [...] }

// Get related cases (similarity search)
GET /api/troubleshooting/related/{case_id}?limit=5
Response: { related: [...] }
```

### 6.3 Authentication

- Use existing BestBox auth (JWT tokens)
- Fallback: Anonymous mode (session-based, limited features)
- User name extracted from token or session

---

## 7. Error Handling

### 7.1 Graceful Degradation

```typescript
// JSON parsing fails → Show as code block (default)
try {
  const data = JSON.parse(jsonBlock);
  return <TroubleshootingCard data={data} />;
} catch (e) {
  return <CodeBlock language="json">{jsonBlock}</CodeBlock>;
}

// Image loading fails → Show placeholder
<img
  src={imageUrl}
  onError={(e) => {
    e.target.src = '/placeholder-defect-image.svg';
  }}
/>

// Missing metadata → Use defaults
const partNumber = data.part_number || 'Unknown';
const defectType = data.defect_type || 'Uncategorized';

// VL descriptions empty → Show placeholder
{img.vl_description || <span className="text-gray-400">No description</span>}

// API timeout → Show error with retry
{feedbackError && <ErrorBanner retry={handleRetry} />}
```

### 7.2 Edge Cases

1. **Very long solutions** (>500 chars): Truncate with "Read more"
2. **Many images** (>20): Paginate image groups
3. **No successful results**: Show "No successful solutions" badge
4. **Mixed trial results**: Show both T1/T2 with appropriate icons
5. **Slow network**: Skeleton loaders, progressive enhancement
6. **Mobile Safari hover**: Disable hover on touch, use tap-to-preview
7. **Related cases empty**: Hide section entirely
8. **Unauthenticated user**: Allow anonymous helpful votes (session-based)

---

## 8. Accessibility

### 8.1 ARIA & Semantic HTML

```tsx
<TroubleshootingCard
  role="article"
  aria-label={`Case ${caseId}, issue ${issueNumber}`}
>
  <ExpandButton
    aria-expanded={isExpanded}
    aria-controls={`case-details-${caseId}`}
  >
    View Full Details
  </ExpandButton>

  <div
    id={`case-details-${caseId}`}
    aria-hidden={!isExpanded}
  />
</TroubleshootingCard>
```

### 8.2 Keyboard Navigation

- **Enter/Space**: Toggle expand/collapse
- **Escape**: Close expanded view
- **Tab**: Navigate through interactive elements
- **Arrow keys**: Navigate image gallery (when in lightbox)

### 8.3 Visual Accessibility

- **Color contrast**: WCAG AA compliant (4.5:1 minimum)
- **Focus indicators**: 2px solid outline on all interactive elements
- **Alt text**: Descriptive for all images
- **Screen reader**: Live regions for dynamic content updates

---

## 9. Performance Targets

| Metric | Target | How We Achieve |
|--------|--------|----------------|
| Initial render | <100ms | Skeleton placeholders, lazy components |
| Time to Interactive | <500ms | Progressive enhancement |
| Hover preview delay | 100ms | Preload on mouseEnter with debounce |
| Image load (viewport) | <2s | Eager loading, CDN, compression |
| Expand animation | 300ms | CSS transitions, GPU-accelerated |
| API response | <200ms | Database indexes, caching |

---

## 10. Implementation Phases

### Phase 1: Core Preview (Week 1)
- [ ] Create TroubleshootingCard components (summary + expanded)
- [ ] Implement JSON detection in chat messages
- [ ] Build responsive thumbnail grid (adaptive sizing)
- [ ] Add expand/collapse interaction
- [ ] Trial timeline visualization
- [ ] Basic metadata display
- **Deliverable**: Functional preview cards without advanced features

### Phase 2: High-Quality Images (Week 1-2)
- [ ] Implement hover preview (cursor-following tooltip)
- [ ] Add image grouping by defect_type (with fallbacks)
- [ ] Create image serving endpoint with size variants
- [ ] Set up caching strategy (browser + nginx)
- [ ] Lazy loading for expanded view
- [ ] Responsive sidebar width (900px on PC)
- **Deliverable**: Full image quality experience

### Phase 3: Actions & Export (Week 2)
- [ ] Copy solution to clipboard
- [ ] PDF export endpoint and generation
- [ ] Share link generation (deep linking)
- [ ] Image download (single + batch ZIP)
- **Deliverable**: Actionable preview cards with export

### Phase 4: Collaborative Features (Week 3)
- [ ] Database schema for feedback/comments
- [ ] "Mark as helpful" button + counter
- [ ] Comments section in expanded view
- [ ] User authentication integration
- [ ] Related cases suggestion (vector similarity)
- **Deliverable**: Social/collaborative knowledge base

### Phase 5: Polish & Optimization (Week 4)
- [ ] Animation polish
- [ ] Mobile optimization and testing
- [ ] Performance profiling
- [ ] Error handling and fallbacks
- [ ] Analytics tracking
- **Deliverable**: Production-ready experience

---

## 11. Technology Stack

- **Frontend**: React + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI (existing) + PostgreSQL (for feedback)
- **Images**: Nginx static serving + browser cache + lazy loading
- **Search**: Qdrant (existing, for related cases similarity)
- **Caching**: Service Worker + Nginx + FastAPI

---

## 12. Success Metrics

**User Engagement:**
- 70%+ of users expand at least one card per session
- Average 3+ hover previews per expanded card
- 20%+ helpful vote rate on solutions

**Performance:**
- <100ms initial card render
- <2s image load in viewport
- 95%+ browser cache hit rate for images

**Quality:**
- WCAG AA accessibility compliance
- Zero layout shift (CLS score)
- <5% error rate on image loads

---

## 13. Future Enhancements

**Post-MVP Ideas:**
- Image annotation tools (draw on images to highlight defects)
- Side-by-side comparison mode for similar cases
- Machine learning to auto-tag images with defect types
- Export case as work order directly to ERP
- Offline mode with ServiceWorker caching
- Multi-language support for international teams

---

## Conclusion

This design delivers a **production-ready document preview system** that transforms the troubleshooting knowledge base from text-only search into a rich, visual, collaborative platform. By prioritizing image quality, smart organization, and progressive enhancement, engineers can quickly find and apply solutions to manufacturing defects with confidence.

**Key Differentiators:**
- ✅ High-quality image handling (hover-to-preview at full resolution)
- ✅ Smart grouping by defect type
- ✅ Responsive design (mobile → PC optimization)
- ✅ Zero backend changes required initially
- ✅ Phased rollout with clear milestones

**Status**: Ready for implementation planning and development.
