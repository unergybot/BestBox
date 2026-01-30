# Troubleshooting Preview Cards - Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement core troubleshooting preview card components that detect JSON in chat messages and render interactive summary/expanded views with trial timelines and metadata.

**Architecture:** Progressive enhancement approach - existing JSON responses work as-is, frontend components detect `result_type: "specific_solution"` JSON blocks and render rich UI cards inline in CopilotKit chat.

**Tech Stack:** React 19, TypeScript, Next.js 16, Tailwind CSS 4, CopilotKit

**Reference Design:** `docs/plans/2026-01-29-troubleshooting-preview-design.md`

---

## Task 1: Create Type Definitions

**Files:**
- Create: `frontend/copilot-demo/types/troubleshooting.ts`

**Step 1: Write type definitions**

Create complete TypeScript interfaces for troubleshooting data structures:

```typescript
// frontend/copilot-demo/types/troubleshooting.ts

export interface TroubleshootingImage {
  image_id: string;
  image_url: string;
  description: string;
  defect_type: string;
  file_path?: string;
  cell_location?: string;
  vl_description?: string | null;
  text_in_image?: string | null;
  equipment_part?: string;
  visual_annotations?: string;
}

export interface TroubleshootingIssue {
  result_type: "specific_solution";
  relevance_score: number;
  case_id: string;
  part_number: string;
  issue_number: number;
  problem: string;
  solution: string;
  trial_version: string;
  result_t1?: string | null;
  result_t2?: string | null;
  success_status?: string | null;
  defect_types?: string[];
  has_images: boolean;
  image_count: number;
  images: TroubleshootingImage[];
  category?: string;
}

export interface TroubleshootingCase {
  result_type: "full_case";
  relevance_score: number;
  case_id: string;
  part_number: string;
  material: string;
  total_issues: number;
  summary: string;
  source_file?: string;
}

export type TroubleshootingResult = TroubleshootingIssue | TroubleshootingCase;

export interface TroubleshootingSearchResults {
  query: string;
  search_mode: string;
  total_found: number;
  results: TroubleshootingResult[];
}
```

**Step 2: Commit**

```bash
cd /home/unergy/BestBox/.worktrees/troubleshooting-preview-cards
git add frontend/copilot-demo/types/troubleshooting.ts
git commit -m "feat: add troubleshooting type definitions

- Add TypeScript interfaces for images, issues, cases
- Support both specific_solution and full_case result types
- Includes all metadata fields from backend JSON

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create JSON Detection Utility

**Files:**
- Create: `frontend/copilot-demo/lib/troubleshooting-detector.ts`
- Test manually (no formal test file for now - quick iteration)

**Step 1: Write detection function**

```typescript
// frontend/copilot-demo/lib/troubleshooting-detector.ts

import { TroubleshootingSearchResults, TroubleshootingResult } from "@/types/troubleshooting";

/**
 * Extract code blocks from markdown text
 */
function extractCodeBlocks(text: string, language?: string): string[] {
  const pattern = language
    ? new RegExp(`\`\`\`${language}\\n([\\s\\S]*?)\`\`\``, "g")
    : /```(?:\w+)?\n([\s\S]*?)```/g;

  const blocks: string[] = [];
  let match;

  while ((match = pattern.exec(text)) !== null) {
    blocks.push(match[1]);
  }

  return blocks;
}

/**
 * Check if parsed JSON is a troubleshooting result
 */
function isTroubleshootingResult(data: any): data is TroubleshootingResult {
  return (
    typeof data === "object" &&
    data !== null &&
    ("result_type" in data) &&
    (data.result_type === "specific_solution" || data.result_type === "full_case")
  );
}

/**
 * Check if parsed JSON is a search results object
 */
function isTroubleshootingSearchResults(data: any): data is TroubleshootingSearchResults {
  return (
    typeof data === "object" &&
    data !== null &&
    "results" in data &&
    Array.isArray(data.results) &&
    data.results.length > 0 &&
    isTroubleshootingResult(data.results[0])
  );
}

/**
 * Detect troubleshooting results in message content
 * Returns array of results found in the message
 */
export function detectTroubleshootingResults(content: string): TroubleshootingResult[] {
  const jsonBlocks = extractCodeBlocks(content, "json");
  const results: TroubleshootingResult[] = [];

  for (const block of jsonBlocks) {
    try {
      const parsed = JSON.parse(block);

      // Check if it's a search results object
      if (isTroubleshootingSearchResults(parsed)) {
        results.push(...parsed.results);
      }
      // Check if it's a single result
      else if (isTroubleshootingResult(parsed)) {
        results.push(parsed);
      }
    } catch (error) {
      // Ignore JSON parse errors - not all code blocks are valid JSON
      continue;
    }
  }

  return results;
}
```

**Step 2: Test manually in console**

Create test file to verify:

```bash
cat > /tmp/test-detector.ts << 'EOF'
import { detectTroubleshootingResults } from './lib/troubleshooting-detector';

const testMessage = `
I found 3 solutions:
\`\`\`json
{
  "query": "产品披锋",
  "search_mode": "ISSUE_LEVEL",
  "total_found": 3,
  "results": [
    {
      "result_type": "specific_solution",
      "relevance_score": 0.74,
      "case_id": "TS-1947688-ED736A0501",
      "part_number": "1947688",
      "issue_number": 14,
      "problem": "1.产品披锋",
      "solution": "1、设计改图，将3016工件图示位置加铁0.03mm",
      "trial_version": "T2",
      "result_t1": "OK",
      "result_t2": null,
      "success_status": "OK",
      "has_images": true,
      "image_count": 4,
      "images": []
    }
  ]
}
\`\`\`
`;

const results = detectTroubleshootingResults(testMessage);
console.log('Found results:', results.length);
console.log('First result:', results[0]);
EOF
# Run: npx tsx /tmp/test-detector.ts
# Expected: "Found results: 1", shows parsed result object
```

**Step 3: Commit**

```bash
git add frontend/copilot-demo/lib/troubleshooting-detector.ts
git commit -m "feat: add JSON detection utility for troubleshooting results

- Extract code blocks from markdown messages
- Detect troubleshooting result types
- Support both single results and search results arrays

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create Badge Components

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/SuccessBadge.tsx`
- Create: `frontend/copilot-demo/components/troubleshooting/RelevanceScore.tsx`

**Step 1: Create SuccessBadge component**

```tsx
// frontend/copilot-demo/components/troubleshooting/SuccessBadge.tsx
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
```

**Step 2: Create RelevanceScore component**

```tsx
// frontend/copilot-demo/components/troubleshooting/RelevanceScore.tsx
"use client";

import React from "react";

interface RelevanceScoreProps {
  score: number;
  className?: string;
}

export const RelevanceScore: React.FC<RelevanceScoreProps> = ({
  score,
  className = "",
}) => {
  // Color based on score: >0.7 green, 0.5-0.7 yellow, <0.5 gray
  const getColor = (score: number) => {
    if (score >= 0.7) return "text-green-600 bg-green-50";
    if (score >= 0.5) return "text-yellow-600 bg-yellow-50";
    return "text-gray-600 bg-gray-50";
  };

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${getColor(
        score
      )} ${className}`}
    >
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
      {score.toFixed(2)}
    </span>
  );
};
```

**Step 3: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/SuccessBadge.tsx
git add frontend/copilot-demo/components/troubleshooting/RelevanceScore.tsx
git commit -m "feat: add badge components for trial status and relevance

- SuccessBadge: Color-coded T0/T1/T2 with OK/NG/Pending
- RelevanceScore: Score display with color coding
- Both use Tailwind for styling consistency

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create Trial Timeline Component

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/TrialTimeline.tsx`

**Step 1: Write timeline component**

```tsx
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
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : isFailed ? (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
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
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/TrialTimeline.tsx
git commit -m "feat: add trial timeline component

- Visual T0→T1→T2 progression with checkmarks/crosses
- Color-coded by success/failure/pending
- Shows active trial state

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create Summary Card Component

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/SummaryView.tsx`

**Step 1: Write summary card component**

```tsx
// frontend/copilot-demo/components/troubleshooting/SummaryView.tsx
"use client";

import React from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SuccessBadge } from "./SuccessBadge";
import { RelevanceScore } from "./RelevanceScore";

interface SummaryViewProps {
  data: TroubleshootingIssue;
  onExpand: () => void;
  className?: string;
}

export const SummaryView: React.FC<SummaryViewProps> = ({
  data,
  onExpand,
  className = "",
}) => {
  // Truncate text helper
  const truncate = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + "...";
  };

  // Get primary trial result for badge
  const primaryResult = data.result_t2 || data.result_t1 || null;

  return (
    <div
      className={`bg-white border-2 border-teal-200 rounded-lg shadow-sm hover:shadow-md transition-shadow ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-700">
            🏭 Case #{data.part_number}-{data.issue_number}
          </span>
          <SuccessBadge
            trialVersion={data.trial_version}
            status={primaryResult}
          />
        </div>
        <RelevanceScore score={data.relevance_score} />
      </div>

      {/* Body */}
      <div className="p-4 space-y-2">
        {/* Problem */}
        <div>
          <span className="text-xs font-medium text-gray-500">Problem:</span>
          <p className="text-sm text-gray-800 mt-0.5">
            {truncate(data.problem, 80)}
          </p>
        </div>

        {/* Solution */}
        <div>
          <span className="text-xs font-medium text-gray-500">Solution:</span>
          <p className="text-sm text-gray-600 mt-0.5">
            {truncate(data.solution, 120)}
          </p>
        </div>

        {/* Image preview */}
        {data.image_count > 0 && (
          <div className="flex items-center gap-1 pt-2">
            <div className="flex gap-1">
              {data.images.slice(0, 3).map((img, idx) => (
                <div
                  key={idx}
                  className="w-16 h-16 bg-gray-100 rounded border border-gray-200 overflow-hidden"
                >
                  <img
                    src={img.image_url}
                    alt={img.description || "Defect image"}
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
            {data.image_count > 3 && (
              <span className="text-xs text-gray-500 ml-1">
                +{data.image_count - 3} more
              </span>
            )}
          </div>
        )}

        {/* Metadata row */}
        <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
          Part: {data.part_number}
          {data.category && ` | Category: ${data.category}`}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <div className="text-xs text-gray-500">
          {/* Placeholder for social metrics (Phase 4) */}
          👍 0 helpful
        </div>
        <button
          onClick={onExpand}
          className="text-sm font-medium text-teal-600 hover:text-teal-700 flex items-center gap-1"
        >
          View Full Details
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/SummaryView.tsx
git commit -m "feat: add summary card component

- Inline card view with problem/solution preview
- Image thumbnails (first 3, show +N more)
- Metadata row with part number and category
- Expand button to show full details
- Teal accent color matching mold theme

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Create Detailed View Component

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/DetailedView.tsx`

**Step 1: Write detailed view component**

```tsx
// frontend/copilot-demo/components/troubleshooting/DetailedView.tsx
"use client";

import React from "react";
import { TroubleshootingIssue } from "@/types/troubleshooting";
import { SuccessBadge } from "./SuccessBadge";
import { RelevanceScore } from "./RelevanceScore";
import { TrialTimeline } from "./TrialTimeline";

interface DetailedViewProps {
  data: TroubleshootingIssue;
  onCollapse: () => void;
  className?: string;
}

export const DetailedView: React.FC<DetailedViewProps> = ({
  data,
  onCollapse,
  className = "",
}) => {
  return (
    <div
      className={`bg-white border-2 border-teal-300 rounded-lg shadow-lg ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-2 border-teal-100">
        <div className="flex items-center gap-3">
          <button
            onClick={onCollapse}
            className="text-gray-500 hover:text-gray-700"
            aria-label="Collapse details"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <div>
            <h3 className="text-lg font-semibold text-gray-800">
              Case {data.case_id} #{data.issue_number}
            </h3>
            <p className="text-sm text-gray-500">
              Part: {data.part_number} | Trial: {data.trial_version}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SuccessBadge
            trialVersion={data.trial_version}
            status={data.result_t2 || data.result_t1 || null}
          />
          <RelevanceScore score={data.relevance_score} />
        </div>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Problem & Solution */}
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span>📋</span>
              Problem
            </h4>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {data.problem}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span>✅</span>
              Solution
            </h4>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {data.solution}
            </p>
          </div>
        </div>

        {/* Trial Timeline */}
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">
            Trial Progression
          </h4>
          <TrialTimeline
            trialVersion={data.trial_version}
            resultT1={data.result_t1 || null}
            resultT2={data.result_t2 || null}
          />
        </div>

        {/* Images */}
        {data.images.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">
              Visual Evidence ({data.image_count} images)
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {data.images.map((img, idx) => (
                <div
                  key={idx}
                  className="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200 hover:border-teal-400 transition-colors"
                >
                  <img
                    src={img.image_url}
                    alt={img.description || `Image ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                  {img.description && (
                    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {img.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="pt-4 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">
            Case Details
          </h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-gray-500">Case ID</dt>
              <dd className="text-gray-800 font-medium">{data.case_id}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Part Number</dt>
              <dd className="text-gray-800 font-medium">{data.part_number}</dd>
            </div>
            {data.category && (
              <div>
                <dt className="text-gray-500">Category</dt>
                <dd className="text-gray-800 font-medium">{data.category}</dd>
              </div>
            )}
            {data.defect_types && data.defect_types.length > 0 && (
              <div>
                <dt className="text-gray-500">Defect Types</dt>
                <dd className="text-gray-800 font-medium">
                  {data.defect_types.join(", ")}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Footer - Placeholder for Phase 4 social features */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          👍 Mark as Helpful | 💬 Comments | 🔗 Share
        </div>
      </div>
    </div>
  );
};
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/DetailedView.tsx
git commit -m "feat: add detailed view component

- Full problem and solution text display
- Trial timeline visualization
- Image grid with hover descriptions
- Complete metadata display
- Collapse button to return to summary

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Create Main Card Wrapper

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/TroubleshootingCard.tsx`

**Step 1: Write main card component**

```tsx
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
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/TroubleshootingCard.tsx
git commit -m "feat: add main card wrapper with expand/collapse state

- Manages summary vs detailed view state
- Simple toggle between views
- Delegates rendering to SummaryView/DetailedView

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Create Card Detector Component

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/TroubleshootingCardDetector.tsx`

**Step 1: Write detector component**

```tsx
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
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/TroubleshootingCardDetector.tsx
git commit -m "feat: add card detector component

- Scans message content for troubleshooting results
- Renders TroubleshootingCard for each result found
- Filters to specific_solution type only
- Returns null if no results found

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Create Component Index

**Files:**
- Create: `frontend/copilot-demo/components/troubleshooting/index.ts`

**Step 1: Create barrel export**

```typescript
// frontend/copilot-demo/components/troubleshooting/index.ts

export { TroubleshootingCard } from "./TroubleshootingCard";
export { TroubleshootingCardDetector } from "./TroubleshootingCardDetector";
export { SummaryView } from "./SummaryView";
export { DetailedView } from "./DetailedView";
export { SuccessBadge } from "./SuccessBadge";
export { RelevanceScore } from "./RelevanceScore";
export { TrialTimeline } from "./TrialTimeline";
```

**Step 2: Commit**

```bash
git add frontend/copilot-demo/components/troubleshooting/index.ts
git commit -m "feat: add troubleshooting components barrel export

- Single import point for all components
- Cleaner imports in consuming code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Integration Test Plan

**Files:**
- Document manual testing steps (no automated tests for now - quick iteration)

**Test Plan:**

1. **Component Rendering Test**
   - Create a test page at `frontend/copilot-demo/app/test-troubleshooting/page.tsx`
   - Import TroubleshootingCard
   - Render with sample data from tools/troubleshooting_tools.py example

2. **Detection Test**
   - Add TroubleshootingCardDetector to ChatMessage or similar component
   - Test with real agent response containing JSON
   - Verify cards render inline

3. **Interaction Test**
   - Click "View Full Details" → Expands to DetailedView
   - Click back arrow → Collapses to SummaryView
   - Verify state transitions smooth

4. **Styling Test**
   - Check responsive layout (mobile vs desktop)
   - Verify teal accent colors match mold theme
   - Check badges render correctly (OK green, NG red)
   - Verify timeline shows correct trial progression

**Manual Test Commands:**

```bash
# Start frontend dev server
cd frontend/copilot-demo
npm run dev

# Navigate to http://localhost:3000
# Test with mold agent query: "产品披锋怎么解决？"
# Verify cards appear in chat
```

---

## Summary

**What We Built:**
- ✅ Complete type definitions for troubleshooting data
- ✅ JSON detection utility (extracts results from markdown)
- ✅ Badge components (success status, relevance score)
- ✅ Trial timeline visualization (T0→T1→T2)
- ✅ Summary card view (inline preview)
- ✅ Detailed card view (expanded full details)
- ✅ Main card wrapper (manages expand/collapse)
- ✅ Card detector (scans messages, renders cards)

**Files Created:** 9 TypeScript/TSX files
**Commits:** 9 focused commits
**Next Phase:** Integrate into CopilotKit message renderer, add high-quality image handling

---

## Integration Notes

To integrate with existing CopilotKit setup:

1. Find where chat messages are rendered (likely in `app/[locale]/page.tsx` or custom message renderer)
2. Import `TroubleshootingCardDetector`
3. Add detection after each assistant message:
   ```tsx
   {message.role === "assistant" && (
     <TroubleshootingCardDetector message={message.content} />
   )}
   ```
4. Cards will automatically appear when JSON is detected

**Estimated Time:** Phase 1 complete in ~2-3 hours of implementation
