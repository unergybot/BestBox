/**
 * RAG Citation Parser
 *
 * Parses assistant messages for RAG citations and extracts structured data.
 * Detects patterns like:
 * - "Based on the knowledge base:"
 * - "[Source: filename, section]"
 * - "Retrieved N relevant passage(s)."
 */

export interface RagCitation {
  source: string;
  section?: string;
  text: string;
}

export interface ParsedRagMessage {
  hasRag: boolean;
  header?: string; // "Based on the knowledge base:"
  citations: RagCitation[];
  footer?: string; // "Retrieved N relevant passage(s)."
  plainText: string; // Message with RAG markers removed
}

/**
 * Check if a message contains RAG content
 */
export function hasRagContent(text: string): boolean {
  return (
    text.includes('Based on the knowledge base:') ||
    text.includes('[Source:') ||
    text.includes('Retrieved') && text.includes('relevant passage')
  );
}

/**
 * Parse RAG citations from assistant message
 */
export function parseRagCitations(text: string): ParsedRagMessage {
  if (!hasRagContent(text)) {
    return {
      hasRag: false,
      citations: [],
      plainText: text,
    };
  }

  const citations: RagCitation[] = [];
  let header: string | undefined;
  let footer: string | undefined;
  let plainText = text;

  // Extract header
  const headerMatch = text.match(/Based on the knowledge base:\s*/i);
  if (headerMatch) {
    header = headerMatch[0].trim();
    plainText = plainText.replace(headerMatch[0], '').trim();
  }

  // Extract footer
  const footerMatch = text.match(/\n?---\s*\nRetrieved (\d+) relevant passage\(s\)\./);
  if (footerMatch) {
    footer = footerMatch[0].trim();
    plainText = plainText.replace(footerMatch[0], '').trim();
  }

  // Extract citations with their associated text
  // Pattern: [Source: filename, section]\ntext content
  const citationPattern = /\[Source:\s*([^\],]+)(?:,\s*([^\]]+))?\]\s*\n([^\[]+)/g;
  let match;

  while ((match = citationPattern.exec(text)) !== null) {
    const source = match[1].trim();
    const section = match[2]?.trim();
    const citationText = match[3].trim();

    citations.push({
      source,
      section,
      text: citationText,
    });

    // Remove from plain text
    plainText = plainText.replace(match[0], '').trim();
  }

  // Also handle standalone citations without text (edge case)
  const standaloneCitationPattern = /\[Source:\s*([^\],]+)(?:,\s*([^\]]+))?\]/g;
  plainText = plainText.replace(standaloneCitationPattern, '').trim();

  // Clean up extra whitespace
  plainText = plainText.replace(/\n\s*\n/g, '\n\n').trim();

  return {
    hasRag: true,
    header,
    citations,
    footer,
    plainText,
  };
}

/**
 * Extract domain from source filename
 * e.g., "erp_procedures.md" → "ERP"
 */
export function extractDomain(source: string): string | null {
  const lowerSource = source.toLowerCase();

  if (lowerSource.includes('erp')) return 'ERP';
  if (lowerSource.includes('crm')) return 'CRM';
  if (lowerSource.includes('it_ops') || lowerSource.includes('itops')) return 'IT Ops';
  if (lowerSource.includes('oa') || lowerSource.includes('office')) return 'OA';

  return null;
}

/**
 * Format citation for display
 * e.g., { source: "erp_procedures.md", section: "Purchase Orders" }
 *    → "ERP Procedures - Purchase Orders"
 */
export function formatCitation(citation: RagCitation): string {
  const source = citation.source.replace(/\.md$/, '').replace(/_/g, ' ');
  const formatted = source.charAt(0).toUpperCase() + source.slice(1);

  if (citation.section) {
    return `${formatted} - ${citation.section}`;
  }

  return formatted;
}
