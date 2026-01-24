# RAG Citation Integration Guide

## Overview

The RAG citation system automatically detects when agents use the knowledge base and displays source citations in a user-friendly format.

## Components Created

### 1. `lib/ragCitationParser.ts`

Utility functions for parsing RAG content from assistant messages:

```typescript
import { parseRagCitations, hasRagContent } from '@/lib/ragCitationParser';

// Check if message contains RAG content
if (hasRagContent(message.content)) {
  // Parse citations
  const parsed = parseRagCitations(message.content);
  console.log(parsed.citations); // Array of {source, section, text}
}
```

### 2. `components/RagCitationBadge.tsx`

React component that renders RAG-enhanced messages:

```typescript
import { RagCitationBadge } from '@/components/RagCitationBadge';

// In your message renderer
<RagCitationBadge text={assistantMessage.content} />
```

## Integration with CopilotKit

### Option A: Custom Message Renderer (Recommended)

If CopilotKit supports custom message rendering via `Messages` prop or similar:

```typescript
import { CopilotSidebar } from "@copilotkit/react-ui";
import { RagCitationBadge } from "@/components/RagCitationBadge";

<CopilotSidebar
  Messages={(messages) => (
    <>
      {messages.map(msg => (
        msg.role === 'assistant' ? (
          <RagCitationBadge text={msg.content} />
        ) : (
          <div>{msg.content}</div>
        )
      ))}
    </>
  )}
/>
```

### Option B: Post-Processing Hook

Use CopilotKit's `useCopilotChat` to access messages and render separately:

```typescript
const { messages } = useCopilotChat();

return (
  <div>
    {messages.map(msg => (
      msg.role === 'assistant' ? (
        <RagCitationBadge text={msg.content} />
      ) : (
        <div>{msg.content}</div>
      )
    ))}
  </div>
);
```

### Option C: Backend Formatting (Current Fallback)

The RAG tool in `tools/rag_tools.py` already formats citations. The frontend will display them as plain text with inline `[Source: ...]` markers until custom rendering is integrated.

## Citation Format (Backend)

The RAG tool returns results in this format:

```
Based on the knowledge base:

[Source: erp_procedures.md, Purchase Orders]
To approve a purchase order, navigate to ERP > Procurement...

[Source: erp_workflow.md, Approval Process]
The approval workflow requires manager sign-off...

---
Retrieved 2 relevant passage(s).
```

## Visual Design

The RagCitationBadge component renders:

- 📚 **Blue badge**: "Searched: [Domain] Knowledge Base"
- **Message content**: Plain text with citations removed
- **Sources section**: Collapsible list of citations
  - Each citation shows filename and section
  - Click to expand and see full text excerpt
  - Light blue/gray styling for sources

## Testing

To test RAG citations:

1. Start all services:
   ```bash
   docker compose up -d
   ./scripts/start-llm.sh
   ./scripts/start-embeddings.sh
   ./scripts/start-agent-api.sh
   ```

2. Seed knowledge base:
   ```bash
   python scripts/seed_knowledge_base.py
   ```

3. Ask a question that triggers RAG:
   - "How do I approve a purchase order?" (ERP domain)
   - "What is the process for adding a new customer?" (CRM domain)
   - "How do I reset a user password?" (IT Ops domain)

4. Check the assistant response contains RAG markers

## TODO: Full Integration

To complete the integration:

1. Check CopilotKit v1.51.2 docs for custom message rendering API
2. If available, add `Messages` prop to CopilotSidebar in `app/[locale]/page.tsx`
3. If not available, create custom chat UI using CopilotKit hooks
4. Test with real RAG queries

## Files Modified

- ✅ `lib/ragCitationParser.ts` - Citation parsing logic
- ✅ `components/RagCitationBadge.tsx` - Citation rendering component
- ⏳ `app/[locale]/page.tsx` - Integration point (pending CopilotKit API check)
