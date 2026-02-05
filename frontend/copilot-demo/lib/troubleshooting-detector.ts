// frontend/copilot-demo/lib/troubleshooting-detector.ts

import { TroubleshootingSearchResults, TroubleshootingResult, TroubleshootingIssue } from "@/types/troubleshooting";

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
 * Check if parsed JSON is a troubleshooting result (specific solution or full case)
 * Accepts multiple formats:
 * - { result_type: "specific_solution", ... }
 * - { case_id, part_number, trial_version, problem, solution, ... }
 */
export function isTroubleshootingResult(data: any): data is TroubleshootingResult {
  if (!data || typeof data !== "object") return false;

  // Format 1: Has result_type field
  if ("result_type" in data) {
    return data.result_type === "specific_solution" || data.result_type === "full_case";
  }

  // Format 2: Has case_id and problem/solution (legacy or transformed format)
  if ("case_id" in data && "problem" in data && "solution" in data) {
    return true;
  }

  return false;
}

/**
 * Check if parsed JSON is a search results wrapper
 */
function isTroubleshootingSearchResults(data: any): data is TroubleshootingSearchResults {
  if (!data || typeof data !== "object") return false;

  // Must have results array
  if (!("results" in data) || !Array.isArray(data.results)) return false;

  if (data.results.length === 0) return false;

  // Check if first item is a troubleshooting result
  return isTroubleshootingResult(data.results[0]);
}

/**
 * Normalize a result to TroubleshootingIssue format
 */
export function normalizeToTroubleshootingIssue(item: any): TroubleshootingIssue {
  const buildImageUrl = (img: any, idx: number): string => {
    if (typeof img?.image_url === "string" && img.image_url.length > 0) {
      // If backend already provided a local path, normalize it through the Next.js proxy
      // to ensure proper URL encoding and consistent extension handling.
      const prefix = "/api/troubleshooting/images/";
      if (img.image_url.startsWith(prefix)) {
        const rawTail = img.image_url.slice(prefix.length);
        let decodedTail = rawTail;
        try {
          decodedTail = decodeURIComponent(rawTail);
        } catch {
          // keep as-is
        }

        const hasExtension = /\.[a-zA-Z0-9]{2,5}$/.test(decodedTail);
        const filename = hasExtension ? decodedTail : `${decodedTail}.jpg`;
        return `${prefix}${encodeURIComponent(filename)}`;
      }

      // Absolute URLs (or other paths) are used as-is.
      return img.image_url;
    }
    if (typeof img?.url === "string" && img.url.length > 0) return img.url;

    const rawId = (img?.image_id ?? `img-${idx}`).toString();
    const hasExtension = /\.[a-zA-Z0-9]{2,5}$/.test(rawId);
    const filename = hasExtension ? rawId : `${rawId}.jpg`;

    // Served by Next.js proxy route: /api/troubleshooting/images/[image_id]
    return `/api/troubleshooting/images/${encodeURIComponent(filename)}`;
  };

  // If already has result_type, return as-is
  if ("result_type" in item) {
    return item as TroubleshootingIssue;
  }

  // Normalize legacy/transformed format
  return {
    result_type: "specific_solution",
    relevance_score: item.relevance_score || 0.9,
    case_id: item.case_id || "",
    part_number: item.part_number || "",
    issue_number: item.issue_number || 1,
    problem: item.problem || "",
    solution: item.solution || "",
    trial_version: item.trial_version || "T0",
    result_t1: item.result_t1 || null,
    result_t2: item.result_t2 || null,
    success_status: item.success_status || (item.success === true ? "OK" : item.success === false ? null : null),
    defect_types: item.defect_types || [],
    has_images: Array.isArray(item.images) && item.images.length > 0,
    image_count: Array.isArray(item.images) ? item.images.length : 0,
    images: Array.isArray(item.images) ? item.images.map((img: any, idx: number) => ({
      image_id: img.image_id || `img-${idx}`,
      image_url: buildImageUrl(img, idx),
      description: img.description || img.vl_description || "Image",
      defect_type: img.defect_type || ""
    })) : [],
    // VLM Fields
    vlm_confidence: item.vlm_confidence,
    severity: item.severity,
    tags: Array.isArray(item.tags) ? item.tags : [],
    key_insights: Array.isArray(item.key_insights) ? item.key_insights : [],
    suggested_actions: Array.isArray(item.suggested_actions) ? item.suggested_actions : []
  };
}

/**
 * Detect troubleshooting results in message content
 * Returns array of results found in the message
 */
export function detectTroubleshootingResults(content: string): TroubleshootingResult[] {
  const results: TroubleshootingResult[] = [];

  // Extract JSON from code blocks
  const jsonBlocks = extractCodeBlocks(content, "json");

  for (const block of jsonBlocks) {
    try {
      const parsed = JSON.parse(block);

      // Check if it's a search results wrapper with results array
      if (isTroubleshootingSearchResults(parsed)) {
        for (const result of parsed.results) {
          if (isTroubleshootingResult(result)) {
            results.push(normalizeToTroubleshootingIssue(result));
          }
        }
      }
      // Check if it's a raw array of troubleshooting results (some models output this format)
      else if (Array.isArray(parsed)) {
        for (const result of parsed) {
          if (isTroubleshootingResult(result)) {
            results.push(normalizeToTroubleshootingIssue(result));
          }
        }
      }
      // Check if it's a single troubleshooting result
      else if (isTroubleshootingResult(parsed)) {
        results.push(normalizeToTroubleshootingIssue(parsed));
      }
    } catch (error) {
      // Ignore JSON parse errors - not all code blocks are valid JSON
      continue;
    }
  }

  return results;
}
