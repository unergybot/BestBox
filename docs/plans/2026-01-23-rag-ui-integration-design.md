# RAG Pipeline UI Integration Design

**Date:** 2026-01-23
**Status:** Design Complete
**Target:** BestBox Frontend (Next.js + CopilotKit)
**Scope:** Full-featured RAG citation display with document preview, search history, and confidence scores

---

## 1. Architecture Overview

### High-Level Structure

The RAG UI integration adds three main layers to the existing Next.js + CopilotKit frontend:

1. **Message Parser Layer** - Intercepts agent responses and extracts RAG citations from the text format `[Source: filename.md, Section]`. Converts these into structured metadata attached to each message.

2. **Component Layer** - New React components:
   - `CitationCard` - Displays source info with relevance tier
   - `CitationBadge` - Inline reference numbers [1][2]
   - `DocumentPreviewModal` - Modal for viewing source documents
   - `SearchHistoryPanel` - Sidebar showing recent RAG queries
   - `RAGIndicator` - Badge showing when knowledge base was used

3. **API Layer** - New Next.js API routes:
   - `/api/documents/[domain]/[filename]` - Serves documents with rate limiting
   - Rate limit: 100 requests/hour per IP using simple in-memory tracking

### Data Flow

```
Agent Response → Message Parser → Structured Citations →
React Components → User clicks citation → API fetches document →
Modal displays with highlighting
```

### Storage

- Search history: Browser localStorage (max 50 queries)
- Rate limiting: Next.js in-memory Map (resets on restart)
- Documents: Read from `data/demo_docs/` server-side

---

## 2. Message Parser Implementation

### Citation Parsing Logic

The message parser processes agent responses in real-time:

```typescript
// utils/ragParser.ts
interface ParsedCitation {
  id: number;              // Sequential: 1, 2, 3...
  source: string;          // "sample_erp.md"
  section?: string;        // "Purchase Order Procedures"
  relevanceScore?: number; // If backend provides it
  relevanceTier: 'high' | 'medium' | 'low'; // Based on position
  startIndex: number;      // Text position for inline badge
}

interface ParsedMessage {
  text: string;           // Original message text
  citations: ParsedCitation[];
  hasRAG: boolean;        // True if RAG was used
  searchQuery?: string;   // Extracted from "Retrieved N passages" footer
}
```

### Parsing Strategy

1. **Detect RAG usage** - Look for "Based on the knowledge base:" header
2. **Extract citations** - Regex pattern: `/\[Source: ([^\]]+)\]/g`
3. **Parse metadata** - Split on comma to get filename and section
4. **Assign relevance tiers**:
   - First 2 citations: "high" (top results from reranker)
   - Next 2 citations: "medium"
   - Remaining: "low"
5. **Insert inline references** - Replace `[Source: ...]` with numbered badges
6. **Store in localStorage** - Save query + timestamp to search history

The parser runs as a React hook that wraps CopilotKit's message stream, transforming messages before they're displayed.

---

## 3. React Component Design

### Component Hierarchy

```
<CopilotSidebar>
  └─ <EnhancedMessage>  // Wraps each agent message
       ├─ <RAGIndicator />  // Shows "🔍 Used Knowledge Base"
       ├─ Message text with inline <CitationBadge /> components
       └─ <CitationCardsSection>
            └─ <CitationCard /> (for each citation)
                 └─ onClick → <DocumentPreviewModal />

<SearchHistoryPanel />  // Floating sidebar
```

### Key Component Props

**CitationBadge** (Inline reference):
- `number`: Citation ID [1], [2], etc.
- `onClick`: Opens corresponding citation card or scrolls to it
- Style: Small superscript, blue color, clickable

**CitationCard** (Bottom of message):
- `citation`: ParsedCitation object
- `onPreview`: Opens document modal
- Display: Source filename, section, relevance tier (stars/badge), "View Source" button
- Relevance visual:
  - High: 3 stars + green badge
  - Medium: 2 stars + yellow badge
  - Low: 1 star + gray badge
- Hover shows exact score tooltip (if available)

**DocumentPreviewModal**:
- `document`: Fetched markdown/content
- `highlightSection`: Section name to scroll to
- `domain`: For API request
- Features: Markdown rendering, scroll-to-section, close button, "View Full Document" link

---

## 4. API Routes and Document Serving

### Document API Endpoint

**Route:** `/api/documents/[domain]/[filename]/route.ts`

**Rate Limiting:**
- In-memory Map: `{ ip: { count: number, resetTime: timestamp } }`
- Limit: 100 requests/hour per IP
- Response: 429 Too Many Requests if exceeded

**Request Flow:**
1. Check rate limit for client IP
2. Validate domain (erp, crm, itops, oa)
3. Validate filename (alphanumeric + .md/.pdf only, prevent path traversal)
4. Read file from `data/demo_docs/${domain}/${filename}`
5. Return content with CORS headers

**Security Measures:**
- Path sanitization: Strip "../", absolute paths
- Allowed extensions: .md, .pdf, .docx only
- Domain whitelist: erp, crm, itops, oa
- No directory listing
- Rate limiting per IP

### Response Format

**Success (200):**
```json
{
  "content": "string",        // Markdown/text content
  "filename": "string",       // "sample_erp.md"
  "domain": "string",         // "erp"
  "section": "string"         // If specified in query param
}
```

**Rate Limited (429):**
```json
{
  "error": "Rate limit exceeded",
  "retryAfter": 3600        // Seconds until reset
}
```

**Not Found (404):**
```json
{
  "error": "Document not found"
}
```

The API uses Next.js edge functions for fast response times and minimal server load.

---

## 5. Search History Implementation

### localStorage Schema

**Storage key:** `bestbox_rag_history`

```typescript
interface RAGHistoryEntry {
  id: string;              // UUID
  query: string;           // User's question that triggered RAG
  timestamp: number;       // Unix timestamp
  domain?: string;         // Filter used (erp, crm, etc.)
  resultCount: number;     // Number of citations returned
  citations: string[];     // Array of source filenames
}

interface RAGHistory {
  entries: RAGHistoryEntry[];  // Max 50 entries
  version: number;              // Schema version for migrations
}
```

### Search History Panel Features

**Display:**
- Floating panel on right side (collapsible)
- Toggle button: "Recent Searches" with count badge
- List shows most recent 10 entries by default
- "Show All" expands to 50 entries
- Each entry shows: query text, timestamp (relative: "2 hours ago"), domain tag, result count

**Interactions:**
- Click entry → Copy query to chat input (or auto-send)
- Hover shows full citation list in tooltip
- "Clear History" button with confirmation
- Auto-cleanup: Remove entries older than 30 days

**Storage Management:**
- Max 50 entries (FIFO - oldest removed first)
- Compressed storage: Only store essential fields
- Lazy loading: Only load when panel opens
- Export option: Download as JSON (future enhancement)

---

## 6. Error Handling and Edge Cases

### Citation Parsing Failures

**Scenario 1: Malformed citation format**
- If `[Source: ...]` is incomplete or has unexpected format
- Fallback: Display raw text, log warning to console
- User sees: Original message without citation cards
- No breaking errors

**Scenario 2: Missing document file**
- When user clicks citation but document doesn't exist
- API returns 404
- Modal shows: "Document not available" message with option to report issue
- Search history still records the query

**Scenario 3: Rate limit exceeded**
- User hits 100 requests/hour limit
- Modal shows: "Too many requests. Please try again in X minutes"
- Countdown timer displays time until reset
- Citation cards remain clickable but disabled visually

### Document Rendering Errors

**Large documents (>1MB):**
- Show loading skeleton during fetch
- Implement pagination: Show first 50KB, "Load More" button for rest
- Timeout after 10 seconds, show partial content

**Unsupported formats:**
- PDF/DOCX: Show "Preview not available, download to view" message
- Only markdown (.md) gets full preview
- Future: Add PDF.js library for PDF rendering

### Network Failures

- Document fetch fails: Retry once automatically, then show error
- localStorage quota exceeded: Clear old search history entries
- Parser crashes: Wrap in try-catch, fallback to plain text display

### Browser Compatibility

- localStorage not available: Disable search history feature gracefully
- IE11/old browsers: Show basic citations without fancy animations
- Feature detection for CSS Grid/Flexbox fallbacks

---

## 7. Visual Design and Styling

### Design System Integration

All components follow the existing BestBox design language using Tailwind CSS.

### Color Palette

- RAG Indicator: Blue-500 (matches existing system status cards)
- Relevance Tiers:
  - High: Green-500 with green-50 background
  - Medium: Yellow-500 with yellow-50 background
  - Low: Gray-500 with gray-50 background
- Citation badges: Blue-600, hover blue-700
- Modal overlay: Gray-900 with 50% opacity

### Component Styling

**CitationBadge (inline):**
```
[1] - Superscript, 12px, blue-600, rounded px-1
Hover: blue-700, cursor pointer, slight scale transform
```

**CitationCard:**
```
- White background, rounded-lg, shadow-md
- Border-l-4 with tier color (green/yellow/gray)
- Padding: 16px
- Flex layout: Icon | Content | Action Button
- Star rating: Filled/outlined stars based on tier
- Hover: shadow-lg transition
```

**DocumentPreviewModal:**
```
- Full-screen overlay with backdrop blur
- Centered card: max-w-4xl, max-h-90vh
- Header: Document name + close button
- Body: Scrollable markdown content
- Highlighted section: Yellow background, scroll into view
- Footer: "View Full Document" link
```

**SearchHistoryPanel:**
```
- Fixed right: 320px width
- Slide-in animation from right
- Semi-transparent background (white 95%)
- Shadow-2xl for depth
- Scrollable list with hover states
- Compact entries: 2-line max with ellipsis
```

### Responsive Design

- Desktop (>1024px): All features visible
- Tablet (768-1024px): SearchHistoryPanel collapsible only
- Mobile (<768px):
  - Modal becomes full-screen
  - Citations stack vertically
  - Search history hidden by default, accessible via icon

---

## 8. CopilotKit Integration Strategy

### Hooking into CopilotKit Messages

**1. Message Interception (Client-side):**

```typescript
// Custom hook: hooks/useRAGEnhancedMessages.ts
export function useRAGEnhancedMessages() {
  const { messages } = useCopilotChat();

  return useMemo(() => {
    return messages.map(msg => {
      // Only process assistant messages
      if (msg.role !== 'assistant') return msg;

      // Parse for RAG citations
      const parsed = parseRAGCitations(msg.content);

      // Attach metadata
      return {
        ...msg,
        ragMetadata: {
          citations: parsed.citations,
          hasRAG: parsed.hasRAG,
          searchQuery: parsed.searchQuery
        }
      };
    });
  }, [messages]);
}
```

**2. Custom Message Renderer:**

Replace CopilotKit's default message component:

```typescript
// In page.tsx
<CopilotSidebar
  MessageRenderer={({ message }) => (
    <EnhancedMessage message={message} />
  )}
>
```

### Backend Integration

The Python backend already returns formatted responses with `[Source: ...]` citations. No backend changes needed - the citation format is already perfect for parsing.

### Data Flow

```
1. User asks question in CopilotKit chat
2. Request → Python agent API (existing)
3. Agent calls search_knowledge_base tool
4. Response includes "[Source: ...]" in text
5. Frontend receives message
6. useRAGEnhancedMessages parses citations
7. EnhancedMessage renders with citation cards
8. User clicks citation → Modal fetches document
```

### State Management

- RAG metadata: Attached directly to message objects
- Search history: Separate localStorage, synced via useEffect
- Modal state: Local component state (which document is open)
- Rate limiting: Server-side only, no client state needed

---

## 9. Performance Optimization

### Frontend Performance

**Message Parsing Optimization:**
- Parse citations only once per message (memoized with useMemo)
- Debounce localStorage writes (300ms delay)
- Lazy load search history panel (code splitting)
- Virtual scrolling for >50 search history entries

**Rendering Optimization:**
```typescript
// Memoize expensive components
const CitationCard = React.memo(({ citation }) => ...);
const DocumentPreviewModal = React.memo(({ document }) => ...);

// Only re-render when citation data changes
// Not when parent message re-renders
```

**Asset Loading:**
- Code split modal component: Loads only when user clicks citation
- Lazy load markdown renderer library (react-markdown): ~40KB saved on initial load
- Defer search history panel until user opens it

### Backend Performance

**Document Serving:**
- In-memory document cache (LRU, max 20 documents)
- Cache hit = instant response (<1ms)
- Cache miss = read from disk (~5-10ms)
- Cache expiry: 5 minutes or on file change

**Rate Limiting Efficiency:**
- In-memory Map for rate limit tracking (no database overhead)
- Cleanup stale entries every 10 minutes
- Max 10,000 IP entries before cleanup

### Network Optimization

- Document API uses HTTP caching headers:
  - `Cache-Control: public, max-age=3600` (1 hour)
  - `ETag` support for conditional requests
- Compress responses with gzip (Next.js automatic)
- CDN-ready: Static assets can be served from edge

### Performance Targets

- Citation parsing: <5ms per message
- Document fetch: <100ms (cache hit), <500ms (cache miss)
- Modal open animation: 60fps (CSS transforms only)
- Search history render: <50ms for 50 entries

---

## 10. Testing Strategy

### Component Testing (Jest + React Testing Library)

**Unit Tests:**

```typescript
// utils/ragParser.test.ts
- parseRAGCitations() with valid citations
- parseRAGCitations() with malformed citations
- parseRAGCitations() with no citations
- Relevance tier assignment logic
- Edge cases: empty strings, special characters

// hooks/useRAGEnhancedMessages.test.ts
- Message enhancement flow
- Memoization works correctly
- Search history updates on new RAG usage
```

**Component Tests:**

```typescript
// CitationBadge.test.tsx
- Renders with correct number
- Click handler fires
- Hover states work

// CitationCard.test.tsx
- Displays source and section correctly
- Relevance tier shows right stars/badge
- Preview button opens modal
- Tooltip shows exact score on hover

// DocumentPreviewModal.test.tsx
- Fetches document on mount
- Renders markdown correctly
- Highlights specified section
- Scroll-to-section works
- Close button dismisses modal
- Loading state displays
- Error state displays

// SearchHistoryPanel.test.tsx
- Loads from localStorage
- Displays recent entries
- Click entry copies to input
- Clear history works with confirmation
- Max 50 entries enforced
```

### Integration Tests

**End-to-End Flow:**

```typescript
// Using Playwright or Cypress
1. User sends message that triggers RAG
2. Verify RAG indicator appears
3. Verify citation badges render inline
4. Verify citation cards appear at bottom
5. Click citation card
6. Verify modal opens with document
7. Verify section is highlighted
8. Verify search history updated
9. Close modal
10. Reopen from search history
```

### API Testing

**Document API Tests:**

```typescript
// app/api/documents/[domain]/[filename]/route.test.ts
- Returns document successfully
- Validates domain whitelist
- Blocks path traversal attempts (../etc/passwd)
- Rate limiting works (101st request fails)
- Returns 404 for missing documents
- Returns 429 when rate limited
- CORS headers present
```

### Manual Testing Checklist

- [ ] Test on Chrome, Firefox, Safari
- [ ] Test on mobile devices (iOS, Android)
- [ ] Test with slow network (DevTools throttling)
- [ ] Test with localStorage disabled
- [ ] Test with 100+ search history entries
- [ ] Test with very long document names
- [ ] Test with special characters in filenames
- [ ] Test rate limiting recovery after 1 hour

### Test Coverage Goals

- Utils/Parsers: 100% coverage
- Components: 90% coverage
- API Routes: 95% coverage
- Overall: 85%+ coverage

---

## 11. Implementation Roadmap and Deployment

### Implementation Phases

**Phase 1: Core Parsing (Day 1, ~4-6 hours)**
- Create `utils/ragParser.ts` with citation parsing logic
- Create `hooks/useRAGEnhancedMessages.ts` for message enhancement
- Write unit tests for parser
- **Deliverable:** Working citation extraction from messages

**Phase 2: Basic Components (Day 1-2, ~6-8 hours)**
- Build `CitationBadge` component
- Build `CitationCard` component with relevance tiers
- Build `RAGIndicator` badge
- Integrate with CopilotKit MessageRenderer
- Write component tests
- **Deliverable:** Citations display in chat UI

**Phase 3: Document Preview (Day 2, ~4-6 hours)**
- Create `/api/documents/[domain]/[filename]` route
- Implement rate limiting
- Build `DocumentPreviewModal` component
- Add markdown rendering (react-markdown)
- Add section highlighting
- Write API and component tests
- **Deliverable:** Clickable citations that open document previews

**Phase 4: Search History (Day 3, ~3-4 hours)**
- Create `SearchHistoryPanel` component
- Implement localStorage persistence
- Add history management (clear, max entries)
- Add click-to-reuse functionality
- Write tests
- **Deliverable:** Persistent search history sidebar

**Phase 5: Polish & Testing (Day 3, ~4-5 hours)**
- Responsive design refinements
- Error handling edge cases
- Performance optimization (memoization, code splitting)
- Cross-browser testing
- Accessibility improvements (ARIA labels, keyboard navigation)
- End-to-end testing
- **Deliverable:** Production-ready feature

**Total Estimate: 2.5-3 days of development**

### Deployment Checklist

**Pre-deployment:**
- [ ] All tests passing (85%+ coverage)
- [ ] No console errors in browser
- [ ] Lighthouse score: Performance >90, Accessibility >90
- [ ] Tested on Chrome, Firefox, Safari
- [ ] Tested on mobile (iOS + Android)
- [ ] Rate limiting verified (can't exceed 100/hour)
- [ ] Path traversal security tested
- [ ] localStorage quota handling works

**Deployment Steps:**
1. Merge to main branch
2. Build frontend: `npm run build`
3. Run production tests: `npm run test`
4. Deploy to staging environment first
5. Smoke test all RAG features
6. Deploy to production
7. Monitor error logs for 24 hours

**Rollback Plan:**
- Feature flagged: Can disable via environment variable `ENABLE_RAG_UI=false`
- Falls back to plain text citations if components fail to load
- No backend changes means instant rollback possible

### Documentation Needed

- Update README.md with RAG UI features
- Add screenshots to docs/
- Create user guide for search history feature
- API documentation for `/api/documents` endpoint

### Future Enhancements (Post-MVP)

- Confidence score from backend (requires backend changes)
- PDF preview support (add PDF.js library)
- Document download button
- Advanced search filters in history
- Citation export functionality
- Analytics tracking for RAG usage

---

## Summary

This design provides a comprehensive, full-featured RAG UI integration that:

✅ **Enhances user experience** - Visual citations, document preview, search history
✅ **Maintains security** - Rate limiting, path validation, authenticated document access
✅ **Performs well** - Memoization, code splitting, caching, <500ms document fetch
✅ **Tests thoroughly** - 85%+ coverage, unit/integration/E2E tests
✅ **Integrates cleanly** - No backend changes, hooks into existing CopilotKit
✅ **Scales for future** - Extensible architecture, feature flags, clear enhancement path

**Next Steps:** Create git worktree for implementation, write detailed implementation plan.
