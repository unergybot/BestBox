# Frontend Enhancements Design

**Date:** 2026-01-23
**Status:** Approved
**Phase:** 3 - Demo Applications (Frontend Track)

## Overview

This design enhances the BestBox frontend with streaming responses, context sharing, and generative UI components to create a production-quality demo experience.

## Goals

1. **Streaming Responses** - Show tokens as they generate for better UX
2. **Context Sharing** - Share app state with agents for context-aware responses
3. **Generative UI** - Render agent responses as interactive components (tables, charts)

## Current State

**Working:**
- CopilotKit sidebar integration
- Basic chat functionality
- Demo scenario buttons
- Agent API connection

**Missing:**
- Streaming (full response wait)
- Context awareness (agent doesn't know selected scenario)
- Visual components (plain text only)

## Design

### 1. Streaming Responses

**Current Problem:**
Users wait 3-5 seconds for full agent response before seeing anything.

**Solution:**
Enable token-by-token streaming from agent API through to UI.

**Architecture:**

```
LLM (llama-server:8080)
    ↓ streams tokens
Agent API (8000) - astream()
    ↓ SSE stream
CopilotKit route (3000)
    ↓ streams to client
CopilotSidebar UI
    ↓ renders tokens as they arrive
```

**Changes Required:**

1. **Agent API** (`services/agent_api.py`):
```python
# Change from:
result = await app.ainvoke(messages)
return {"response": result}

# To:
async def stream_response():
    async for chunk in app.astream(messages):
        if "messages" in chunk:
            for msg in chunk["messages"]:
                if hasattr(msg, "content"):
                    yield f"data: {json.dumps({'token': msg.content})}\n\n"

return StreamingResponse(stream_response(), media_type="text/event-stream")
```

2. **CopilotKit Route** (`app/api/copilotkit/route.ts`):
   - Already supports streaming via LangChainAdapter
   - Verify connection uses streaming endpoint

3. **No UI changes needed** - CopilotSidebar handles streaming automatically

### 2. CopilotKit Context Sharing

**Current Problem:**
Agent doesn't know which demo scenario is active or any UI state.

**Solution:**
Use `useCopilotReadable` to share app state with agent automatically.

**Context Schema:**

```typescript
interface AppContext {
  selectedScenario: "erp" | "crm" | "it_ops" | "oa" | null;
  scenarioDescription: string;
  userPreferences: {
    detailLevel: "summary" | "detailed";
    responseFormat: "text" | "structured";
  };
}
```

**Implementation:**

**New File:** `app/hooks/useAppContext.ts`
```typescript
import { useCopilotReadable } from "@copilotkit/react-core";
import { useState } from "react";

export function useAppContext() {
  const [scenario, setScenario] = useState<string | null>(null);

  useCopilotReadable({
    description: "Current demo scenario and user preferences",
    value: {
      selectedScenario: scenario,
      scenarioDescription: getScenarioDescription(scenario),
      userPreferences: {
        detailLevel: "summary",
        responseFormat: "structured"
      }
    }
  });

  return { scenario, setScenario };
}
```

**Updated:** `app/page.tsx`
```typescript
const { scenario, setScenario } = useAppContext();

// When user clicks scenario button
<button onClick={() => setScenario("erp")}>
  ERP Copilot
</button>
```

**Agent Behavior:**
- CopilotKit injects context into system prompt automatically
- Agent sees: "User is currently in ERP Copilot scenario"
- Agent routes correctly without explicit instruction

### 3. Generative UI Components

**Current Problem:**
All agent responses are plain text. Data should render as interactive components.

**Solution:**
Use `useCopilotAction` to define actions that return React components.

**Components to Build:**

1. **InventoryTable** - Stock levels with color-coded alerts
2. **LeadScorecard** - Ranked leads with progress bars
3. **AlertDashboard** - IT alerts with severity badges
4. **DocumentPreview** - Generated documents with edit capability
5. **FinancialChart** - Bar/line charts for financial data

**Implementation Pattern:**

**New File:** `app/components/InventoryTable.tsx`
```typescript
interface InventoryItem {
  id: string;
  product: string;
  warehouse: string;
  quantity: number;
  reorderLevel: number;
}

export function InventoryTable({ items }: { items: InventoryItem[] }) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th>Product</th>
            <th>Warehouse</th>
            <th>Quantity</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.id} className={item.quantity < item.reorderLevel ? "bg-red-50" : ""}>
              <td>{item.product}</td>
              <td>{item.warehouse}</td>
              <td>{item.quantity}</td>
              <td>
                {item.quantity < item.reorderLevel ? (
                  <span className="text-red-600 font-semibold">Low Stock</span>
                ) : (
                  <span className="text-green-600">OK</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Updated:** `app/page.tsx`
```typescript
useCopilotAction({
  name: "displayInventory",
  description: "Display inventory levels as an interactive table",
  parameters: [
    {
      name: "items",
      type: "object[]",
      description: "Array of inventory items with product, warehouse, quantity, reorderLevel"
    }
  ],
  render: ({ items }) => <InventoryTable items={items} />
});
```

**Agent Integration:**

Agent needs to return structured data for actions. Update agent prompts to include:

```python
# In agents/erp_agent.py system prompt
"""
When displaying inventory data, call the displayInventory action with this format:
{
  "items": [
    {"id": "INV-001", "product": "Widget A", "warehouse": "WH-1", "quantity": 50, "reorderLevel": 100}
  ]
}
"""
```

**Example Flow:**

```
User: "Show me low stock items"
    ↓
Agent: Calls get_inventory_levels tool
    ↓
Agent: Streams text "I found 12 items below reorder level..."
    ↓
Agent: Calls displayInventory action with structured data
    ↓
UI: Renders InventoryTable component inline in chat
    ↓
User: Can sort, filter, interact with table
```

## Component Specifications

### InventoryTable
- **Props:** `items: InventoryItem[]`
- **Features:** Color-coded rows, sortable columns, filter by warehouse
- **Styling:** Tailwind with red highlights for low stock

### LeadScorecard
- **Props:** `leads: Lead[]`
- **Features:** Score progress bars, deal size badges, click to expand
- **Styling:** Card layout with gradient backgrounds

### AlertDashboard
- **Props:** `alerts: Alert[]`
- **Features:** Severity badges (critical/warning/info), filter, acknowledge button
- **Styling:** Grid layout with color-coded severity

### DocumentPreview
- **Props:** `document: Document`
- **Features:** Markdown preview, edit mode, copy to clipboard
- **Styling:** Document-style layout with toolbar

### FinancialChart
- **Props:** `data: FinancialData, chartType: "bar" | "line"`
- **Features:** Interactive chart using recharts library, hover tooltips
- **Styling:** Responsive chart with legend

## File Changes

### New Files
```
frontend/copilot-demo/app/
├── hooks/
│   └── useAppContext.ts
└── components/
    ├── InventoryTable.tsx
    ├── LeadScorecard.tsx
    ├── AlertDashboard.tsx
    ├── DocumentPreview.tsx
    └── FinancialChart.tsx
```

### Modified Files
```
services/agent_api.py
  - Add streaming support with astream()
  - Return SSE instead of JSON

frontend/copilot-demo/app/page.tsx
  - Import and use useAppContext hook
  - Register 5 CopilotKit actions with render functions
  - Update scenario button handlers

frontend/copilot-demo/app/api/copilotkit/route.ts
  - Verify streaming configuration
  - Ensure connection to agent API streaming endpoint

agents/erp_agent.py, crm_agent.py, it_ops_agent.py, oa_agent.py
  - Update system prompts to describe available actions
  - Include structured output format examples
```

### Dependencies to Add
```json
{
  "recharts": "^2.10.0"  // For FinancialChart
}
```

## Integration Flow

```
User clicks "ERP Copilot" button
    ↓
useAppContext sets scenario state
    ↓
useCopilotReadable shares {selectedScenario: "erp"} to agent
    ↓
User: "Show me low stock items"
    ↓
Agent sees context, knows it's ERP scenario
    ↓
Agent calls get_inventory_levels tool
    ↓
Agent streams response: "I found 12 items below reorder level..."
    ↓
Agent calls displayInventory action with structured data
    ↓
CopilotKit renders InventoryTable component inline
    ↓
User interacts (sort, filter, acknowledge)
```

## Implementation Plan

### Week 1: Streaming + Context Sharing
**Days 1-2: Backend Streaming**
- Update `services/agent_api.py` to use `astream()`
- Implement SSE response format
- Test streaming with curl/Postman

**Days 3-4: Context Sharing**
- Create `useAppContext.ts` hook
- Integrate `useCopilotReadable` in page.tsx
- Test context visibility in agent prompts

**Day 5: Testing & Validation**
- Verify streaming works end-to-end
- Verify agent sees context in all scenarios
- Fix any integration issues

### Week 2: Generative UI Components
**Days 1-2: Core Components**
- Build InventoryTable component
- Build LeadScorecard component
- Build AlertDashboard component

**Days 3-4: Advanced Components**
- Build DocumentPreview component
- Build FinancialChart component (with recharts)
- Add interactivity (sort, filter, expand)

**Day 5: Action Integration**
- Register all 5 actions in page.tsx
- Update agent prompts with action descriptions
- Test each component with mock data
- End-to-end testing with live agents

## Testing Strategy

### Streaming Tests
1. Start agent API and frontend
2. Send query via UI
3. Verify tokens appear incrementally (not all at once)
4. Check network tab for SSE stream
5. Measure time-to-first-token (<500ms target)

### Context Sharing Tests
1. Select ERP scenario
2. Send query without mentioning "ERP"
3. Verify agent responds with ERP-specific data
4. Switch to CRM scenario
5. Send same query, verify CRM response

### Generative UI Tests
1. Query: "Show inventory" → Verify InventoryTable renders
2. Query: "Top leads" → Verify LeadScorecard renders
3. Query: "System alerts" → Verify AlertDashboard renders
4. Query: "Draft email" → Verify DocumentPreview renders
5. Query: "Q4 revenue" → Verify FinancialChart renders

### Interactive Component Tests
- Click table headers to sort
- Use filter dropdowns
- Expand/collapse cards
- Edit document preview
- Hover chart for tooltips

## Success Metrics

1. **Streaming:** Time-to-first-token < 500ms
2. **Context:** Agent correctly identifies scenario 100% of time
3. **UI:** All 5 components render without errors
4. **Interactivity:** Sorting, filtering work smoothly
5. **UX:** User feedback positive on visual components

## Risks & Mitigations

**Risk:** Streaming breaks with tool calls
**Mitigation:** Test tool calls separately, ensure proper SSE formatting

**Risk:** Context sharing increases prompt size
**Mitigation:** Keep context minimal (<500 tokens), monitor latency

**Risk:** Components don't render correctly
**Mitigation:** Build with TypeScript, test with storybook/isolated tests

**Risk:** Agent doesn't call actions correctly
**Mitigation:** Provide clear examples in system prompts, validate parameters

## Future Enhancements

- Voice input support (CopilotKit audio)
- Human-in-the-loop approvals (for document edits, purchases)
- Export components to PDF/Excel
- Mobile-responsive component layouts
- Dark mode support for all components

## References

- [CopilotKit Streaming Docs](https://docs.copilotkit.ai/concepts/streaming)
- [CopilotKit Actions Docs](https://docs.copilotkit.ai/concepts/copilot-actions)
- [CopilotKit Readable Context](https://docs.copilotkit.ai/reference/hooks/useCopilotReadable)
- [LangGraph Streaming](https://langchain-ai.github.io/langgraph/concepts/streaming/)
