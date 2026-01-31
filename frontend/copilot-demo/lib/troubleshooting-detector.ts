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
function isTroubleshootingResult(data: any): data is TroubleshootingResult {
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
function normalizeToTroubleshootingIssue(item: any): TroubleshootingIssue {
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
      image_url: img.image_url || img.url || `/api/troubleshooting/images/img-${idx}.jpg`,
      description: img.description || img.vl_description || "Image",
      defect_type: img.defect_type || ""
    })) : []
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
