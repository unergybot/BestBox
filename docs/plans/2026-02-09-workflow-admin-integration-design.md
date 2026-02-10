# Workflow Canvas Admin Integration Design

**Date:** 2026-02-09
**Status:** Approved
**Goal:** Integrate the React Flow workflow canvas into the BestBox Admin UI with dashboard, metrics, and execution tracking

## Overview

This design adds a comprehensive workflow management section to the Admin UI, providing visibility into workflow usage, execution history, and time-series metrics. The integration builds on the existing React Flow canvas prototype and adds production-ready features for monitoring and management.

## Design Decisions

### 1. Navigation & Route Structure

**Admin Navigation:**
- Add "Workflows" as a new top-level navigation item in the admin sidebar
- Position between "KB" and "Users" (automation/tools section)
- Use a flow/diagram icon for visual distinction

**Route Structure:**
```
/[locale]/admin/workflows                    # Dashboard overview
/[locale]/admin/workflows/designer           # Canvas designer (new workflow)
/[locale]/admin/workflows/designer/[id]      # Edit existing workflow
/[locale]/admin/workflows/[id]               # View workflow details & execution history
```

**Authentication:**
- Admin role only (JWT token required)
- Inherits authentication from existing `AdminLayout`
- All routes nested under `/admin` for automatic auth protection

**Internationalization:**
Add to `AdminNew` translation namespace:
- `nav.workflows` - "Workflows"
- `workflows.dashboard.*` - Dashboard page strings
- `workflows.designer.*` - Designer page strings
- `workflows.execution.*` - Execution history strings

### 2. Dashboard Overview Page

**Layout:**

**Stat Cards Grid (4 cards):**
1. **Total Workflows** - Count of all workflows in system
2. **Executions (24h)** - Runs in last 24 hours
3. **Success Rate (7d)** - Percentage successful over 7 days
4. **Avg Duration** - Average execution time

**Charts Section:**
- **Executions Timeline** - Line chart showing executions/day over 30 days (success vs failed)
- **Popular Workflows** - Top 5 most-executed workflows (bar chart or table)

**Workflows Table:**
Sortable/filterable table with columns:
- Workflow name
- Last executed timestamp
- Status badge (draft/active/archived)
- Execution count
- Actions (Edit, Run, View Details, Delete)

**Quick Actions:**
- Primary: "Create New Workflow" button → `/admin/workflows/designer`
- Secondary: Filter by status, search by name, export definitions

**API Endpoint:**
```
GET /api/workflows/metrics
Response:
{
  "totalWorkflows": 12,
  "executions24h": 45,
  "successRate7d": 94.2,
  "avgDurationMs": 2340,
  "executionTimeline": [
    {"date": "2026-02-09", "success": 23, "failed": 2},
    ...
  ],
  "topWorkflows": [
    {"id": "uuid", "name": "...", "executionCount": 156},
    ...
  ],
  "recentWorkflows": [...]
}
```

### 3. Designer Integration

**Reuse Existing Canvas:**
The current `/workflows` page has fully functional components:
- Node palette (Start, Pi Coding Agent, End nodes)
- Canvas with drag-and-drop
- Node configuration panel
- Toolbar (Save/Compile/Execute)

**Integration Approach:**

1. **Extract Components:**
   - Move `CanvasInner`, `Toolbar` from `/workflows/page.tsx` to shared components
   - Keep `workflowStore.ts` as-is (handles API correctly)
   - Create `/admin/workflows/designer/page.tsx` that imports these components

2. **Admin-Specific Enhancements:**
   - Add breadcrumbs: Admin > Workflows > Designer
   - Match admin color scheme (gray-900 sidebar)
   - After save: "Return to Dashboard" or "Continue Editing" options
   - Support loading existing workflow via ID parameter

**Extended Workflow Metadata:**
Add fields to workflow model:
- `created_by` - Admin user who created it
- `created_at`, `updated_at` - Timestamps
- `status` - enum: 'draft', 'active', 'archived'

### 4. Execution Tracking & Metrics

**Database Schema:**

New table for execution history:
```sql
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    executed_by VARCHAR(255),  -- Admin username/email
    executed_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20),  -- 'success', 'failed', 'timeout'
    duration_ms INTEGER,  -- Execution time in milliseconds
    input_message TEXT,  -- Message/parameters sent
    output_result TEXT,  -- Result or error message
    error_details JSONB,  -- Full error stack if failed
    node_trace JSONB  -- Optional: node execution trace
);

CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_executed_at ON workflow_executions(executed_at);
```

**Metrics Collection Flow:**

1. **On Execute:**
   - Insert row: `status='running'`, `executed_at=NOW()`
   - Execute workflow (existing logic)
   - Update row: final status, duration, output
   - On error: capture stack in `error_details`

2. **API Endpoints:**
   - `GET /api/workflows/metrics` - Dashboard stats & time-series
   - `GET /api/workflows/{id}/executions` - History for specific workflow
   - `POST /api/workflows/{id}/execute` - Execute & record

**Retention Policy:**
- Keep execution logs for 90 days (configurable)
- Document cleanup job or manual deletion process

### 5. Workflow Detail View

**Page Structure (`/admin/workflows/[id]`):**

**Header:**
- Workflow name (inline editable)
- Status badge and metadata
- Actions: Edit, Execute, Duplicate, Archive, Delete

**Tabs:**

1. **Overview Tab:**
   - Description and summary
   - Node count and types
   - Canvas thumbnail preview

2. **Execution History Tab:**
   - Paginated table of executions
   - Columns: Timestamp, Status, Duration, Input
   - Expandable rows for full output/errors
   - Filters: Status, date range
   - Export execution logs

3. **Metrics Tab:**
   - Execution trend chart (time-series)
   - Success rate over time
   - Average duration trend
   - Comparison to other workflows

4. **Configuration Tab:**
   - Compiled LangGraph code (read-only)
   - View generated Python
   - Download workflow definition (JSON)

**List View Features (Dashboard Table):**
- Bulk actions: Archive multiple, export multiple
- Filters: All/Active/Draft/Archived
- Sort: Name, Last executed, Count, Success rate
- Quick execute: Run with default parameters

### 6. Error Handling & UX

**Notifications:**
- Toast messages for actions (save, execute, delete)
- Clear error messages for compilation failures
- Loading states for async operations

**Error Scenarios:**
- Workflow not found (deleted) → redirect to dashboard
- Execution timeout → show partial results + timeout notice
- Compilation errors → highlight problematic nodes

**Mobile Responsiveness:**
- Admin is desktop-focused
- Stat cards stack on smaller screens
- Tables scroll horizontally on mobile

## Implementation Order

1. **Phase 1: Database & API** (Backend)
   - Add `workflow_executions` table migration
   - Add execution tracking to workflow endpoint
   - Create metrics aggregation endpoint

2. **Phase 2: Navigation & Dashboard** (Frontend)
   - Add Workflows to admin sidebar
   - Create dashboard page with stats/charts
   - Build workflows table with actions

3. **Phase 3: Designer Integration** (Frontend)
   - Extract canvas components
   - Create admin designer page
   - Add breadcrumbs and admin styling

4. **Phase 4: Detail View** (Frontend)
   - Build workflow detail page
   - Add execution history tab
   - Add metrics charts

5. **Phase 5: Polish**
   - Add translations
   - Error handling and loading states
   - Testing and refinement

## Technical Dependencies

**Frontend:**
- Existing React Flow canvas components
- Zustand workflow store
- Chart library (e.g., recharts or Chart.js)
- next-intl for translations

**Backend:**
- PostgreSQL (existing)
- FastAPI workflow endpoints (existing)
- New metrics aggregation queries

**Infrastructure:**
- No new services required
- Database migration for execution tracking

## Success Criteria

1. Admin users can access Workflows section from sidebar
2. Dashboard displays real-time workflow metrics
3. Users can create/edit workflows in designer
4. Execution history is tracked and viewable
5. Time-series charts show usage trends
6. All actions require admin authentication

## Future Enhancements (Out of Scope)

- Role-based access (view vs edit permissions)
- Workflow templates library
- Scheduled workflow execution
- Workflow versioning
- Real-time execution monitoring (WebSocket)
- Workflow export/import between environments
