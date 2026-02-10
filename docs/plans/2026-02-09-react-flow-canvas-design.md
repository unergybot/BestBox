# React Flow Workflow Canvas - Design Document

**Date:** February 9, 2026
**Status:** Approved
**Prototype Scope:** Visual workflow editor with Pi Coding Agent integration

---

## 1. Architecture Overview

### Core Components

1. **Frontend Canvas** (`frontend/copilot-demo/app/[locale]/workflows/page.tsx`)
   - React Flow canvas for drag-and-drop workflow design
   - Custom node components for each agent type (Pi Coding Agent, ERP, CRM, IT Ops, etc.)
   - Real-time validation and edge connections
   - Save/load workflows from PostgreSQL

2. **Canvas State Management** (Zustand store)
   - Nodes: `{ id, type, position, data }`
   - Edges: `{ id, source, target, sourceHandle, targetHandle }`
   - Workflow metadata: `{ name, description, created_at, updated_at }`

3. **Backend API** (`services/agent_api.py`)
   - `POST /api/workflows` - Save canvas JSON
   - `GET /api/workflows/:id` - Load canvas JSON
   - `POST /api/workflows/:id/compile` - Generate LangGraph Python code
   - `POST /api/workflows/:id/execute` - Run compiled workflow

4. **Code Generator** (`agents/canvas_compiler.py`)
   - Parse React Flow JSON → generate LangGraph Python code
   - Handle node types: start, pi_coding_agent, router, tool, condition, end
   - Generate state definitions and edge logic

### Database Schema

```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    canvas_json JSONB NOT NULL,
    generated_code TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 2. Node Types & Configuration

### Custom Node Types

#### 1. Start Node (entry point)
- No configuration needed
- Single output handle
- Auto-created for every workflow

#### 2. Pi Coding Agent Node ⭐ (prototype focus)
**Inputs:**
- `message` (string) - Task description for pi agent
- `workspace` (string) - Working directory path
- `allow_writes` (boolean) - Enable edit/write tools
- `tools` (multiselect) - Allowed tools: read, grep, find, ls, bash, edit, write

**Outputs:**
- `result` (string) - Pi agent's response
- `error` (string) - Error message if failed

**Visual appearance:** Purple node with pi logo

#### 3. Router Node (decision point)
- Routes to different agents based on query classification
- Outputs: erp, crm, it_ops, oa, general (one edge per domain)
- Uses existing `router_node` logic from BestBox

#### 4. Tool Node (generic tool execution)
- Select from available LangChain tools in registry
- Dynamic input/output based on tool schema
- Used for: search_knowledge_base, database queries, API calls

#### 5. Condition Node (if/else logic)
- Simple condition evaluation (equals, contains, greater than, etc.)
- Two outputs: true branch, false branch

#### 6. End Node (termination)
- Outputs final response to user
- No configuration needed

### Node Configuration UI
- Right-side panel that opens when node is selected
- Form fields dynamically generated from node type schema
- Validation: required fields, type checking, constraint validation

---

## 3. Canvas-to-LangGraph Compilation

### Compilation Strategy

The canvas JSON gets transformed into LangGraph Python code in three phases:

#### Phase 1: Parse Canvas JSON

```python
def parse_canvas(canvas_json: dict) -> WorkflowDefinition:
    """Extract nodes, edges, and validate structure."""
    nodes = canvas_json["nodes"]  # [{ id, type, data, position }]
    edges = canvas_json["edges"]  # [{ source, target, sourceHandle, targetHandle }]

    # Validate: must have exactly one start node, at least one end node
    # Validate: no cycles (LangGraph requires DAG)
    # Validate: all edges connect valid handles

    return WorkflowDefinition(nodes, edges, metadata)
```

#### Phase 2: Generate Node Functions

```python
def generate_pi_node(node_config: dict) -> str:
    """Generate Python function for pi_coding_agent node."""
    return f'''
def pi_node_{node_config['id']}(state: AgentState):
    from plugins_contrib.pi_coding_agent import pi_coding_agent_tool

    result = pi_coding_agent_tool.invoke({{
        "message": "{node_config['data']['message']}",
        "workspace": "{node_config['data']['workspace']}",
        "allow_writes": {node_config['data']['allow_writes']}
    }})

    # Append result to messages
    state["messages"].append(AIMessage(content=result))
    return state
'''
```

#### Phase 3: Generate Graph Structure

```python
def generate_graph(workflow: WorkflowDefinition) -> str:
    """Generate LangGraph StateGraph with nodes and edges."""
    code = [
        "from langgraph.graph import StateGraph",
        "from agents.state import AgentState",
        "",
        "graph = StateGraph(AgentState)",
        ""
    ]

    # Add all nodes
    for node in workflow.nodes:
        code.append(f"graph.add_node('{node.id}', {node.function_name})")

    # Add all edges
    for edge in workflow.edges:
        code.append(f"graph.add_edge('{edge.source}', '{edge.target}')")

    code.append("workflow = graph.compile()")
    return "\n".join(code)
```

### Generated Code Location
- Save to `agents/generated/workflow_{workflow_id}.py`
- Import dynamically at runtime: `importlib.import_module(f"agents.generated.workflow_{workflow_id}")`

---

## 4. Frontend Implementation

### Technology Stack
- **React Flow** (reactflow v11) - Canvas library
- **Zustand** - State management for canvas state
- **Tailwind CSS 4** - Styling (already in BestBox)
- **React 19** - Already in Next.js 16

### Canvas Component Structure

```tsx
// frontend/copilot-demo/app/[locale]/workflows/page.tsx
export default function WorkflowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, addNode } = useWorkflowStore();

  return (
    <div className="h-screen flex">
      {/* Left Sidebar - Node Palette */}
      <NodePalette onAddNode={addNode} />

      {/* Center - Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={customNodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>

      {/* Right Sidebar - Node Configuration */}
      <NodeConfigPanel />
    </div>
  );
}
```

### Custom Node Components

```tsx
// components/workflow/nodes/PiCodingAgentNode.tsx
export function PiCodingAgentNode({ data, id, selected }: NodeProps) {
  return (
    <div className={`px-4 py-3 border-2 rounded-lg ${selected ? 'border-purple-500' : 'border-gray-300'}`}>
      <div className="flex items-center gap-2 mb-2">
        <PiIcon className="w-5 h-5 text-purple-600" />
        <span className="font-semibold">Pi Coding Agent</span>
      </div>

      <Handle type="target" position={Position.Top} />

      <div className="text-xs text-gray-600">
        {data.message ? `Task: ${data.message.slice(0, 30)}...` : 'Configure task'}
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

### Zustand Store

```tsx
// stores/workflowStore.ts
export const useWorkflowStore = create<WorkflowState>((set) => ({
  nodes: [{ id: 'start', type: 'start', position: { x: 250, y: 0 }, data: {} }],
  edges: [],

  onNodesChange: (changes) => set((state) => ({
    nodes: applyNodeChanges(changes, state.nodes)
  })),

  addNode: (type: string) => set((state) => ({
    nodes: [...state.nodes, createNode(type, state.nodes.length)]
  })),

  saveWorkflow: async () => {
    const { nodes, edges } = get();
    await fetch('/api/workflows', {
      method: 'POST',
      body: JSON.stringify({ nodes, edges })
    });
  }
}));
```

---

## 5. Workflow Execution & Testing

### Execution Flow

1. **User clicks "Run Workflow" button in canvas**

2. **Frontend sends execution request:**
   ```tsx
   const executeWorkflow = async (workflowId: string, inputs: Record<string, any>) => {
     const response = await fetch(`/api/workflows/${workflowId}/execute`, {
       method: 'POST',
       body: JSON.stringify({ inputs })
     });

     // Stream execution events via SSE
     const eventSource = new EventSource(`/api/workflows/${workflowId}/stream`);
     eventSource.onmessage = (event) => {
       const { node_id, status, output } = JSON.parse(event.data);
       updateNodeStatus(node_id, status, output);
     };
   };
   ```

3. **Backend compiles and executes:**
   ```python
   @app.post("/api/workflows/{workflow_id}/execute")
   async def execute_workflow(workflow_id: str, inputs: dict):
       # Load workflow from DB
       workflow = await db.fetch_one("SELECT * FROM workflows WHERE id = %s", workflow_id)

       # Compile if needed
       if not workflow["generated_code"]:
           code = compile_canvas_to_langgraph(workflow["canvas_json"])
           await db.execute("UPDATE workflows SET generated_code = %s WHERE id = %s", (code, workflow_id))

       # Execute workflow
       module = load_workflow_module(workflow_id)
       state = {"messages": [HumanMessage(content=inputs["message"])], ...}
       result = await module.workflow.ainvoke(state)

       return {"result": result["messages"][-1].content}
   ```

4. **Visual feedback in canvas:**
   - Nodes light up green as they execute
   - Show node output in hover tooltip
   - Final result displayed in output panel
   - Execution trace saved to `execution_traces` table for debugging

### Testing Strategy

**Unit tests:**
- `test_canvas_compiler.py` - Validate code generation
- `test_workflow_nodes.py` - Test custom node functions

**Integration tests:**
- Create canvas → compile → execute → verify output
- Test pi_coding_agent node with various configurations

**E2E test:**
- Load canvas UI → add pi node → configure → save → execute → see result

---

## 6. Prototype Scope (MVP)

### ✅ Included in Prototype
- React Flow canvas with drag-and-drop
- Pi Coding Agent node (primary node type)
- Start/End nodes
- Save/load workflows to PostgreSQL
- Compile canvas → LangGraph Python code
- Execute workflow and show results
- Node configuration panel

### ❌ Deferred to Phase 2
- Router/Condition/Tool nodes
- Real-time collaboration
- Workflow versioning
- Advanced visual features (zoom, pan, alignment)

---

## 7. Implementation Plan

### Phase 1: Backend Foundation (Week 1)
1. Create database migration for `workflows` table
2. Implement `canvas_compiler.py` with basic code generation
3. Add API endpoints in `agent_api.py`
4. Write unit tests for compiler

### Phase 2: Frontend Canvas (Week 2)
1. Install React Flow and Zustand dependencies
2. Create workflow canvas page
3. Implement custom Pi Coding Agent node
4. Add node palette and configuration panel
5. Implement save/load functionality

### Phase 3: Integration & Testing (Week 3)
1. Connect frontend to backend API
2. Test end-to-end workflow execution
3. Add visual execution feedback
4. Write integration tests
5. Document usage

### Phase 4: Polish & Demo (Week 4)
1. UI/UX improvements
2. Error handling and validation
3. Create demo workflows
4. Record video demonstration

---

## 8. Success Criteria

- [ ] User can drag Pi Coding Agent node onto canvas
- [ ] User can configure node with message and workspace
- [ ] User can save workflow to database
- [ ] System generates valid LangGraph Python code
- [ ] Workflow executes successfully and returns results
- [ ] Visual feedback shows execution progress
- [ ] All tests pass (unit + integration + E2E)

---

## 9. Future Enhancements (Post-Prototype)

1. **Additional Node Types**
   - ERP/CRM/IT Ops agent nodes
   - Knowledge base search nodes
   - Database query nodes
   - HTTP API nodes

2. **Advanced Features**
   - Workflow versioning and rollback
   - Real-time collaboration (multiple users)
   - Workflow templates and marketplace
   - Export to YAML/JSON for sharing

3. **Developer Experience**
   - Hot reload for workflow changes
   - Debug mode with breakpoints
   - Performance profiling
   - Workflow documentation generation

---

## 10. References

- **Coze Studio Analysis:** `/home/apexai/BestBox/docs/coze-studio-analysis.md`
- **Pi-mono Integration:** `/home/apexai/BestBox/plugins_contrib/pi_coding_agent/`
- **React Flow Documentation:** https://reactflow.dev/
- **LangGraph Documentation:** https://github.com/langchain-ai/langgraph

---

**Approval Date:** February 9, 2026
**Approved By:** User
**Next Steps:** Set up implementation environment (git worktree recommended)
