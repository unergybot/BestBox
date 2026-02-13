# Streaming Response Display Design

**Date:** 2026-02-13
**Status:** Approved
**Approach:** Verify & Optimize CopilotKit Streaming

## Goal

Improve user experience by displaying agent responses token-by-token as they're generated, rather than waiting for complete responses. This creates a more responsive, ChatGPT-like typing effect.

## Background

**Current Flow:**
```
Voice → ASR → VoiceInput.appendMessage()
  → CopilotKit → OpenAIAdapter
  → Agent API → Router → Domain Agents (ERP/CRM/IT Ops/OA)
  → Response → Display
```

**Current Behavior:** Responses appear all at once after full generation completes.

**Desired Behavior:** Responses stream token-by-token as LLM generates them.

**Key Insight:** Agent API already has `responses_api_stream()` implementation using SSE format. The issue is likely:
- CopilotKit not requesting streaming
- Chunk size too conservative (3 words)
- Buffering in frontend or backend

## Architecture

### Streaming Flow

```
User speaks
  ↓
ASR Service (Qwen3-ASR)
  ↓
VoiceInput.handleTranscript()
  ↓
CopilotKit.appendMessage() ← User message added to chat
  ↓
CopilotKit Runtime
  ↓
OpenAIAdapter { stream: true } ← Must verify/enable
  ↓
Agent API /v1/chat/completions
  ↓
if (request.stream) → responses_api_stream() ← Already exists
  ↓
Router Agent → [ERP|CRM|IT Ops|OA] Agent
  ↓
LangGraph.astream_events() ← Streams tokens from LLM
  ↓
SSE: response.output_text.delta events
  ↓
CopilotKit receives stream
  ↓
CopilotChat UI updates token-by-token
```

### Components

**Backend (Agent API):**
- `responses_api_stream()` - Already implemented SSE streaming
- `LangGraph.astream_events()` - Streams from LLM
- Sends `response.output_text.delta` events with token chunks

**Frontend (CopilotKit):**
- OpenAIAdapter - Manages OpenAI-compatible API calls
- CopilotChat component - Displays streaming messages
- VoiceInput - Integrates voice with chat

## Investigation Steps

### Step 1: Verify Streaming is Enabled

**Check OpenAIAdapter Configuration:**

File: `frontend/copilot-demo/app/api/copilotkit/route.ts`

```typescript
const serviceAdapter = new OpenAIAdapter({
  model: "bestbox-agent",
  openai,
  // Verify: Is streaming enabled by default?
  // May need explicit: stream: true
});
```

**Add Logging to Agent API:**

File: `services/agent_api.py`

```python
@app.post("/v1/chat/completions")
async def responses_api(request: ChatRequest, ...):
    logger.info(f"Request stream flag: {request.stream}")
    logger.info(f"Request model: {request.model}")
    # ... rest of handler
```

### Step 2: Check Current Chunk Size

File: `services/agent_api.py` - in `responses_api_stream()`

Current implementation:
```python
# Split content into chunks for natural streaming effect
words = content.split()
chunk_size = 3  # Words per chunk
```

**Analysis:** 3 words per chunk may feel slow. Consider optimization.

### Step 3: Verify CopilotKit UI Updates

Check `<CopilotChat>` component:
- No artificial delays/debouncing
- Updates on every token delta
- No buffering in React state

### Step 4: Test Different Response Types

Test streaming with:
1. Short responses (1-2 sentences)
2. Long responses (paragraphs)
3. Code blocks
4. Tool results (ERP/CRM data)
5. TroubleshootingCard (structured content)

## Optimizations

### Optimization 1: Agent API Chunk Size

**Current:** 3 words per chunk (conservative)

**Proposed Options:**

A) **Token-by-token (fastest):**
```python
chunk_size = 1  # 1 word per chunk
```

B) **Character-based (smoothest for CJK):**
```python
char_chunk_size = 20  # ~3-5 words
```

C) **Adaptive (smart):**
```python
# Short responses: 1-2 words/chunk
# Long responses: 3-5 words/chunk
# Code blocks: Complete block at once
```

**Recommendation:** Start with **1 word per chunk** for maximum responsiveness.

### Optimization 2: SSE Event Timing

Remove any artificial delays:
```python
async for event in agent_app.astream_events(...):
    # Send immediately, no buffering
    yield f"event: response.output_text.delta\n"
    yield f"data: {json.dumps(...)}\n\n"
    # NO asyncio.sleep() here
```

### Optimization 3: CopilotKit Configuration

Explicit streaming enable:
```typescript
const serviceAdapter = new OpenAIAdapter({
  model: "bestbox-agent",
  openai,
  stream: true,  // Explicit
});
```

### Optimization 4: Frontend React Updates

Ensure immediate rendering:
- Use `flushSync` if needed
- No debouncing/throttling
- Check CopilotKit version supports streaming

## Testing Strategy

### Test 1: Verify Streaming is Active

**Console Logging:**

Frontend:
```typescript
console.log('[CopilotKit] Streaming enabled:', isStreaming);
console.log('[CopilotKit] Token received:', token);
```

Backend:
```python
logger.info(f"Streaming response - chunk {i}: {chunk}")
logger.info(f"Stream event sent: {event_type}")
```

### Test 2: Visual Streaming Test

**Test Queries:**
- Chinese: "请详细介绍BestBox系统的ERP模块功能"
- English: "Explain the BestBox ERP module features in detail"

**Expected Behavior:**
- ✅ Words appear progressively, 1-2 at a time
- ✅ No long pause before first word
- ✅ Smooth, continuous flow
- ❌ Whole paragraph at once = NOT streaming

### Test 3: Performance Metrics

**Time to First Token (TTFT):**
```typescript
const startTime = Date.now();
// On first token:
const ttft = Date.now() - startTime;
console.log('[Streaming] TTFT:', ttft, 'ms');
// Target: < 500ms
```

### Test 4: Content Type Matrix

| Content Type | Expected Behavior |
|--------------|-------------------|
| Plain text | ✅ Stream smoothly |
| ERP/CRM data | ✅ Stream |
| TroubleshootingCard | ⚠️ All at once (acceptable) |
| Markdown | ✅ Stream (may see `**` appear) |
| Code blocks | ⚠️ May wait for complete block |

### Test 5: Voice Integration

1. Click voice button
2. Say: "查询销售数据"
3. Wait for silence (1.5s)
4. Verify:
   - Transcript appears in chat
   - Response starts streaming < 1s
   - Words appear progressively

**Success Criteria:**
- TTFT < 500ms
- Tokens appear every 50-100ms
- No full-paragraph delays
- Real-time "typing" effect

## Error Handling

### Error Case 1: Streaming Connection Lost

**Backend:**
```python
try:
    async for event in agent_app.astream_events(...):
        yield event_data
except Exception as e:
    logger.error(f"Stream interrupted: {e}")
    yield f"event: response.error\n"
    yield f"data: {json.dumps({'error': 'Stream interrupted'})}\n\n"
```

**Frontend:**
- CopilotKit handles automatically
- Shows partial response + error indicator

### Error Case 2: Streaming Not Supported

**Fallback to Non-Streaming:**
```python
if request.stream:
    return await responses_api_stream(request)
else:
    return await chat_completion(request)  # Fallback
```

### Error Case 3: LLM Timeout

**Add Timeout:**
```python
async with asyncio.timeout(60):  # 60s max
    async for event in agent_app.astream_events(...):
        yield event_data
```

### Error Case 4: Malformed Stream Data

**Frontend Handling:**
- CopilotKit logs error
- Shows received content so far
- Doesn't crash UI

## Monitoring

**Stream Metrics:**
```python
stream_metrics = {
    "total_tokens": 0,
    "duration_ms": 0,
    "chunks_sent": 0,
    "errors": 0,
    "ttft_ms": 0
}
logger.info(f"Stream completed: {stream_metrics}")
```

## Graceful Degradation

**Priority Order:**
1. ✅ **Best:** Full streaming with optimized chunks (1 word)
2. ✅ **Good:** Streaming with default chunks (3 words)
3. ⚠️ **Acceptable:** Non-streaming (whole response)
4. ❌ **Fallback:** Error message with retry

## Implementation Plan

See separate implementation plan document: `2026-02-13-streaming-responses-plan.md`

## Tech Stack

- **Backend:** FastAPI, LangGraph, SSE (Server-Sent Events)
- **Frontend:** Next.js, CopilotKit, React
- **Protocol:** OpenAI-compatible API with streaming
- **LLM:** Qwen3-30B-A3B-Instruct (vLLM)

## References

- Agent API: `services/agent_api.py`
- CopilotKit Route: `frontend/copilot-demo/app/api/copilotkit/route.ts`
- Voice Input: `frontend/copilot-demo/components/VoiceInput.tsx`
- Streaming Implementation: `responses_api_stream()` function

## Success Metrics

- **TTFT:** < 500ms (time to first token)
- **Token Frequency:** Every 50-100ms
- **User Perception:** Smooth, real-time typing effect
- **Error Rate:** < 1% stream failures
- **Fallback Rate:** < 5% non-streaming fallbacks
