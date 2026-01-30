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
