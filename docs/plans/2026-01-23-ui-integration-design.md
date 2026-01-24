# BestBox UI Integration Design - RAG & S2S Features

**Date:** 2026-01-23
**Status:** Design Complete - Ready for Implementation
**Focus:** UI/UX integration of RAG Pipeline and S2S features with service stability awareness

---

## Design Goals

1. **Automatic RAG Integration**: Knowledge base search happens transparently when agents need it
2. **Voice as Input Method**: S2S integrated into copilot chat (not standalone mode)
3. **Service Status Transparency**: UI shows what's working and degrades gracefully
4. **Resource Awareness**: Design accounts for 96GB RAM constraints and service dependencies

---

## Overall UI Architecture

### Main UI Structure

```
┌─────────────────────────────────────────┐
│  Header: BestBox + Language Switcher   │
├─────────────────────────────────────────┤
│  System Status Card (Enhanced)          │
│  • Model: Qwen2.5-14B                  │
│  • Services: [LLM] [Embeddings] [S2S]  │ ← NEW: Service indicators
│  • Status: Each shows ✓ or ⚠️          │
├─────────────────────────────────────────┤
│  Scenario Selector (ERP/CRM/Ops/OA)    │
├─────────────────────────────────────────┤
│  Sample Queries                         │
└─────────────────────────────────────────┘

┌─────────────────────┐
│  CopilotKit Sidebar │  (Right side, overlay)
│  ┌─────────────────┐│
│  │ Chat Messages   ││
│  │ • User          ││
│  │ • Assistant     ││
│  │ • [RAG]         ││ ← NEW: RAG citation badges
│  └─────────────────┘│
│  ┌─────────────────┐│
│  │ Input Area      ││
│  │ [Type...] [🎤]  ││ ← Voice button in input
│  └─────────────────┘│
└─────────────────────┘
```

### Key Architectural Decisions

1. **Voice Integration**: Move voice button from bottom-left to copilot input area (makes it clear it's an alternative input method)
2. **Service Status**: Expand system status card to show all service health (LLM, Embeddings, Reranker, S2S components)
3. **RAG Transparency**: Show when RAG is used with inline badges like `[Knowledge Base: ERP Procedures]`
4. **Graceful Degradation**: Voice button shows tooltip when TTS unavailable ("Voice input only - audio responses disabled")

---

## Component Design

### 1. Service Status Display

**Enhanced System Status Card:**

```
┌─────────────────────────────────────────────────────┐
│ System Services                                     │
├─────────────────────────────────────────────────────┤
│ 🟢 LLM (Qwen2.5-14B)           527 tok/s           │
│ 🟢 Embeddings (BGE-M3)          ~60ms              │
│ 🟡 S2S Gateway                  ASR only (CPU)     │
│    └─ TTS: Disabled (audio responses unavailable)  │
│ 🔴 Qdrant                       Connection failed   │
│                                                     │
│ RAM: 18GB / 96GB (19%) ✓ Healthy                  │
└─────────────────────────────────────────────────────┘
```

**Status Indicators:**
- 🟢 Green: Fully operational
- 🟡 Yellow: Degraded (working but limited)
- 🔴 Red: Offline/unavailable
- ⚪ Gray: Not required for current scenario

**Implementation:**
- Poll health endpoints every 10 seconds
- Services monitored: `/health` for LLM (8080), Embeddings (8081), Reranker (8082), S2S (8765), Qdrant (6333)
- Store in React state: `const [serviceHealth, setServiceHealth] = useState<ServiceStatus[]>([])`
- Show tooltips on hover with details (e.g., "ASR running on CPU - slower transcription (~2-3x)")
- Parse S2S health response to show TTS/ASR status separately

**Files:**
- New hook: `frontend/copilot-demo/hooks/useServiceHealth.ts`
- New component: `frontend/copilot-demo/components/ServiceStatusCard.tsx`
- Replace static system info in `app/[locale]/page.tsx`

---

### 2. Voice Input Integration

**Voice Button in Copilot Input:**

```
┌──────────────────────────────────────┐
│ Type your message...        [🎤] [↑] │
│                             voice send│
└──────────────────────────────────────┘
```

**Button States:**
- 🎤 (blue) - Ready to record
- ⏺️ (red, pulsing) - Listening to microphone
- 🔊 (green, pulsing) - Playing audio response
- 🎤 (gray) - Disabled (TTS unavailable)

**Behavior Flow:**

1. **User clicks mic** → Starts recording
   - Input field shows: "🔴 Listening..." with audio level visualization
   - User speaks naturally

2. **User clicks stop** → Sends to S2S
   - Shows: "Transcribing..."
   - When `asr_final` received → Auto-injects as user message in chat
   - S2S response streams as assistant message (same as typed input)

3. **Response Integration:**
   - LLM tokens appear in chat (text streaming)
   - If TTS enabled: Audio plays simultaneously
   - If TTS disabled: Show badge "🔇 Audio disabled - text only"

**Transcript Auto-Send:**
```typescript
onAsrFinal: (text) => {
  // Auto-send (Recommended for seamless UX)
  copilotContext.appendMessage({
    role: 'user',
    content: text
  });
}
```

**Files Modified:**
- `app/[locale]/page.tsx` - Remove floating VoiceButton from bottom-left
- `CopilotSidebar` integration - add voice button to input area
- `hooks/useS2S.ts` - Wire up transcript auto-send via CopilotKit

---

### 3. RAG Transparency & Citations

**Chat Message with RAG:**

```
┌────────────────────────────────────────┐
│ 👤 User                                │
│ How do I approve a purchase order?    │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ 🤖 Assistant                           │
│                                        │
│ 📚 Searched: ERP Knowledge Base        │ ← Badge showing RAG used
│                                        │
│ To approve a purchase order:          │
│ 1. Navigate to ERP > Procurement...   │
│                                        │
│ Sources:                               │
│ • ERP Procedures - Purchase Orders     │ ← Clickable citations
│ • Approval Workflow Guide              │
└────────────────────────────────────────┘
```

**Implementation Approach:**

**Option A: Parse Response Text** (Quick - Recommended for MVP)
- Backend formats results with `[Source: ...]` markers (already implemented in `tools/rag_tools.py`)
- Frontend detects and renders as badges
- Simple regex: `/\[Source: ([^\]]+)\]/g`

**Option B: Structured Metadata** (Better - Future Enhancement)
- Modify agent response to include metadata
- CopilotKit supports custom message annotations
- Cleaner separation of content and citations

**Visual Design:**
- Badge: Light blue background (#EFF6FF), book icon 📚
- Text: "Searched: [Domain] Knowledge Base"
- Sources: Collapsible section (expanded by default)
- Each source: Small chip with hover effect

**Fallback Behavior:**
```
⚠️ No knowledge base articles found - answering from general knowledge
```

**Files:**
- New component: `frontend/copilot-demo/components/ChatMessage.tsx` (or extend CopilotKit's message renderer)
- CSS for citation badges in Tailwind
- Message parsing utility: `utils/parseRagCitations.ts`

---

### 4. Resource Management Strategy

**Service Startup Order & Dependencies:**

```bash
Priority Tiers (with 96GB RAM):
┌─────────────────────────────────────────┐
│ Tier 1 (Critical - Start First)        │
│ • Docker services (Qdrant, Postgres,   │
│   Redis) - lightweight, ~2GB total     │
│ • LLM Server (Qwen2.5-14B) - ~8-10GB   │
└─────────────────────────────────────────┘
         ↓ Wait for health check
┌─────────────────────────────────────────┐
│ Tier 2 (Required - Start Second)       │
│ • Embeddings (BGE-M3) - ~2GB           │
│ • Reranker (BGE-reranker) - ~1GB       │
│ • Agent API - minimal (<500MB)          │
└─────────────────────────────────────────┘
         ↓ Wait for health check
┌─────────────────────────────────────────┐
│ Tier 3 (Optional - Start Last)         │
│ • S2S Gateway (ASR: ~3GB, TTS: ~2GB)   │
│   Launch with TTS disabled by default   │
└─────────────────────────────────────────┘

Total Estimated: ~16-18GB (leaves ~78GB free)
```

**Memory Allocation Recommendations:**

```yaml
# docker-compose.yml memory limits
services:
  qdrant:
    mem_limit: 2g
  postgres:
    mem_limit: 1g
  redis:
    mem_limit: 512m
```

```bash
# LLM context size tuning
llama-server:
  --ctx-size 4096  # Current (suitable for demos)
  # Can reduce to 2048 if memory pressure occurs
```

**UI Reflection of Resource State:**

```
┌──────────────────────────────────────────┐
│ System Resources                         │
│ RAM: 18GB / 96GB (19%) ✓ Healthy       │
│                                          │
│ ⚠️ Running in reduced mode:             │
│ • S2S TTS disabled (save 2GB)           │
│ • ASR on CPU (GPU reserved for LLM)     │
│                                          │
│ [Enable Full S2S] button                │
│ (Requires ~5GB additional memory)        │
└──────────────────────────────────────────┘
```

**Auto-Recovery Strategy:**

```typescript
// Frontend health check logic
if (serviceStatus.qdrant === 'offline') {
  // Show in UI: "⚠️ Knowledge search unavailable"
  // Agents still work, just without knowledge base
}

if (serviceStatus.s2s === 'offline') {
  // Hide/disable voice button
  // Show tooltip: "Voice features unavailable"
}

// Optional: Retry button for each failed service
```

**Files:**
- New script: `scripts/start-all-services.sh` (orchestrated startup)
- Update `docker-compose.yml` with memory limits
- Health check utilities in frontend

---

## Implementation Checklist

### Phase 1: Service Health Monitoring (1-2 hours)

**Task 1.1: Create service health hook**
- File: `frontend/copilot-demo/hooks/useServiceHealth.ts`
- Poll endpoints: `/health` for each service
- Return status map: `{ llm, embeddings, reranker, s2s, qdrant }`
- 10-second polling interval
- Handle offline gracefully (timeout after 2s)

**Task 1.2: Create ServiceStatusCard component**
- File: `frontend/copilot-demo/components/ServiceStatusCard.tsx`
- Replace static system info in `page.tsx`
- Show real-time service indicators
- Color-coded: green/yellow/red/gray
- Tooltips with details (e.g., "ASR: CPU mode, ~2-3x slower")
- Optional: "Enable TTS" button when S2S is degraded

---

### Phase 2: Voice Integration (2-3 hours)

**Task 2.1: Move VoiceButton into CopilotKit input**
- File: `frontend/copilot-demo/app/[locale]/page.tsx`
- Remove floating VoiceButton from bottom-left
- Integrate into CopilotSidebar input area
- Position alongside text input and send button

**Task 2.2: Wire up transcript auto-send**
- File: `frontend/copilot-demo/hooks/useS2S.ts`
- On `asr_final`: inject message into CopilotKit
- Use CopilotKit's `useCopilotChat()` hook
- Call `appendMessage({ role: 'user', content: transcript })`

**Task 2.3: Handle response streaming**
- LLM tokens → appear in chat (already works via backend)
- TTS audio → plays via existing useS2S playback
- Show badge when TTS disabled: "🔇 Text only"
- Ensure audio and text are synchronized

---

### Phase 3: RAG Transparency (1-2 hours)

**Task 3.1: Add RAG detection to chat messages**
- File: `frontend/copilot-demo/components/ChatMessage.tsx` (or custom)
- Parse assistant messages for `[Source: ...]` patterns
- Extract and render as citation badges
- Alternative: Use CopilotKit message annotations if available

**Task 3.2: Style RAG indicators**
- Badge design: light blue bg (`bg-blue-50`), book icon 📚
- Header text: "Searched: ERP Knowledge Base"
- Collapsible sources section (expanded by default)
- Fallback message when RAG finds nothing: "⚠️ No knowledge base articles found"

---

### Phase 4: Backend Health & Startup (1 hour)

**Task 4.1: Fix Qdrant health issue**
- Check Qdrant logs: `docker logs bestbox-qdrant`
- Likely issue: collection not created or misconfigured
- Run: `python scripts/seed_knowledge_base.py`
- Verify: `curl http://localhost:6333/health`

**Task 4.2: Create unified startup script**
- File: `scripts/start-all-services.sh`
- Tier 1: `docker compose up -d`
- Wait for health: `curl localhost:6333/health`
- Tier 2: `start-llm.sh`, `start-embeddings.sh`, `start-agent-api.sh`
- Tier 3: `start-s2s.sh` (with TTS disabled by default)
- Show progress: "✓ LLM ready, ⏳ Embeddings loading..."

---

### Phase 5: Polish & Edge Cases (1-2 hours)

**Task 5.1: Error handling**
- Service offline → show clear message in UI
- Qdrant down → "Knowledge search unavailable"
- S2S down → hide/disable voice button
- LLM down → show critical error banner

**Task 5.2: Loading states**
- Service health: initial state "checking..."
- First health poll takes 1-2 seconds
- Show skeleton/spinner during initial load

**Task 5.3: Responsive design**
- Service status card: stack vertically on mobile
- Voice button: position carefully in mobile input
- Citations: scroll horizontally on small screens
- Test on viewport widths: 375px, 768px, 1024px

---

## Total Estimated Time: 6-9 hours

---

## Success Criteria

### UI/UX Goals

✅ **Service Status Visibility**
- All services show real-time health status
- Users understand what features are available
- Degraded mode clearly communicated

✅ **Seamless Voice Input**
- Voice button integrated into chat input
- Transcripts auto-inject into conversation
- TTS plays simultaneously with text streaming (when enabled)
- Clear feedback when TTS unavailable

✅ **RAG Transparency**
- Users see when knowledge base is searched
- Citations displayed with sources
- Fallback message when no results found

✅ **Graceful Degradation**
- UI adapts when services unavailable
- No broken features or confusing states
- Clear path to recovery (retry buttons, status info)

### Technical Goals

✅ **Resource Efficiency**
- Total memory usage: ~16-18GB (leaves 78GB free)
- Services start in correct order
- No cascading failures

✅ **Health Monitoring**
- All services have `/health` endpoints
- Frontend polls every 10 seconds
- Timeouts prevent UI hangs

✅ **Error Resilience**
- Offline services don't crash UI
- Users can still interact with available features
- Clear error messages guide troubleshooting

---

## Open Questions / Future Enhancements

### Short-term (Next Sprint)
1. **TTS Debug**: Fix Piper TTS loading hang (currently disabled)
2. **ASR GPU**: Build CTranslate2 with ROCm support for faster transcription
3. **Qdrant Health**: Investigate why it's showing "unhealthy"

### Medium-term (Next Month)
1. **RAG Metadata**: Implement structured metadata (Option B) instead of text parsing
2. **Voice Editing**: Allow users to edit transcripts before sending
3. **Memory Monitor**: Add real-time RAM usage graph
4. **Service Auto-restart**: Detect crashes and auto-restart failed services

### Long-term (Future Versions)
1. **Multi-language Voice**: Support language switching in voice input
2. **RAG Source Preview**: Click citation to see full document excerpt
3. **Advanced Audio**: Interrupt detection, barge-in during responses
4. **Resource Profiling**: Track token usage, response times, bottlenecks

---

## Files Modified

### Frontend (Next.js)
- `app/[locale]/page.tsx` - Remove floating voice button, integrate status card
- `hooks/useServiceHealth.ts` - New: Service health monitoring
- `hooks/useS2S.ts` - Update: Auto-send transcripts to CopilotKit
- `components/ServiceStatusCard.tsx` - New: Enhanced status display
- `components/ChatMessage.tsx` - New: RAG citation rendering
- `utils/parseRagCitations.ts` - New: Citation extraction utility

### Backend (Python)
- `scripts/start-all-services.sh` - New: Orchestrated startup
- `docker-compose.yml` - Update: Memory limits
- `scripts/seed_knowledge_base.py` - Fix: Ensure Qdrant collection exists

### Configuration
- `.env` - Add: Health check endpoints
- `CLAUDE.md` - Update: Document new startup procedure

---

## Dependencies

### Existing (Already Installed)
- CopilotKit 1.0+ (frontend integration)
- useS2S hook (voice capture/playback)
- RAG tools (search_knowledge_base in tools/rag_tools.py)
- Service health endpoints (all services have /health)

### New (To Add)
- None - all functionality uses existing dependencies

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CopilotKit doesn't support custom input widgets | High | Use overlay approach or inject into existing input |
| Health polling creates too much network traffic | Low | Use 10s interval, exponential backoff on errors |
| RAG citation parsing breaks on edge cases | Medium | Strict regex patterns, fallback to plain text |
| Voice button conflicts with CopilotKit styling | Medium | Use Tailwind utilities, test in isolation |
| Qdrant stays unhealthy even after fixes | Medium | Implement "RAG unavailable" mode in UI |

---

## Testing Strategy

### Manual Testing
1. Start services in order, verify UI updates correctly
2. Test voice input → transcript → response flow
3. Trigger RAG queries, verify citations appear
4. Simulate service failures (stop containers), verify graceful degradation
5. Test on mobile viewport sizes

### Automated Testing (Future)
1. E2E test: Voice input end-to-end flow (Playwright)
2. Component test: ServiceStatusCard with mocked health data
3. Integration test: RAG citation parsing
4. Load test: Health polling performance with 100+ concurrent users

---

## Documentation Updates

After implementation:
1. Update `README.md` - Add new startup procedure
2. Update `CLAUDE.md` - Document service health monitoring
3. Create `docs/UI_FEATURES.md` - User guide for voice and RAG features
4. Update `docs/PROJECT_STATUS.md` - Mark UI integration complete

---

## References

- Current implementation: `frontend/copilot-demo/app/[locale]/page.tsx:134-141`
- S2S status: `docs/S2S_QUICK_FIX_RESULTS.md`
- RAG tools: `tools/rag_tools.py:165-224`
- Service health: S2S returns `tts_enabled` flag at `:8765/health`

---

**Design Approved:** Pending
**Implementation Start:** TBD
**Target Completion:** 1-2 days (6-9 hours total)
