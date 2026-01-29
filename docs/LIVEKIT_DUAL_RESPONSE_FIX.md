# LiveKit Dual Response Format - Bug Fixes

**Date:** 2026-01-29
**Status:** Fixed, ready for testing

## Issues Identified

### Issue 1: TTS Speaking Format Tags
**Symptom:** Voice output was `"['[VOICE]We have..."` instead of `"We have..."`

**Root Cause:**
- Agent was using direct LLM instead of graph_wrapper
- TTS received raw LLM response with [VOICE]/[TEXT] tags
- Content was wrapped as stringified list `['...']` from LiveKit's internal representation

### Issue 2: Content Extraction in conversation_item_added
**Symptom:** Agent response content not properly extracted for chat display

**Root Cause:**
- `item.content` could be a list of chunks, not just a string
- Simple `str(content)` converted list to string representation
- No handling for chunk objects with `.text` attribute

### Issue 3: Consecutive Assistant Messages
**Symptom:** Error `"Cannot have 2 or more assistant messages at the end of the list"`

**Root Cause:**
- Agent attempting to prompt user when silent ("I didn't catch that...")
- Multiple prompts without user input created consecutive assistant messages
- OpenAI API rejects conversation with consecutive assistant messages

## Fixes Applied

### Fix 1: Use LangGraph with graph_wrapper for LLM

**Location:** `services/livekit_agent.py` lines 856-896

**Changes:**
```python
# NEW: Use LangGraph integration for dual response format
if LANGGRAPH_INTEGRATION and bestbox_graph:
    from livekit.plugins import langchain as lk_langchain
    from langchain_core.runnables import RunnableLambda

    # Wrap graph_wrapper as LangChain Runnable
    wrapped_graph = RunnableLambda(graph_wrapper)
    llm_instance = lk_langchain.LLM(llm=wrapped_graph)
    session_config["llm"] = llm_instance
    logger.info("✅ LangGraph integration configured (dual response format)")
```

**Effect:**
- All LLM responses now go through graph_wrapper
- graph_wrapper parses [VOICE]/[TEXT] and returns only VOICE for TTS
- TTS speaks clean text without tags ✅

### Fix 2: Improved Content Extraction

**Location:** `services/livekit_agent.py` lines 986-1022

**Changes:**
```python
# Extract content - handle different formats
if hasattr(item, 'content'):
    raw_content = item.content

    # Handle list of content chunks
    if isinstance(raw_content, list):
        content_parts = []
        for chunk in raw_content:
            if hasattr(chunk, 'text'):
                content_parts.append(chunk.text)
            elif isinstance(chunk, str):
                content_parts.append(chunk)
            else:
                content_parts.append(str(chunk))
        content = ''.join(content_parts)
    elif hasattr(raw_content, 'text'):
        # Single chunk with text attribute
        content = raw_content.text
    else:
        # Direct string or other
        content = str(raw_content)
```

**Effect:**
- Properly extracts text from list chunks
- Handles different content formats (list, chunk object, string)
- parse_dual_response receives clean content for TEXT extraction ✅

### Fix 3: parse_dual_response List Wrapper Handling

**Location:** `services/livekit_agent.py` lines 252-295 (already implemented earlier)

**Changes:**
```python
# Remove list wrapper if present
if cleaned_content.startswith("['") and cleaned_content.endswith("']"):
    cleaned_content = cleaned_content[2:-2]
elif cleaned_content.startswith('["') and cleaned_content.endswith('"]'):
    cleaned_content = cleaned_content[2:-2]

# Unescape any escaped quotes
cleaned_content = cleaned_content.replace("\\'", "'").replace('\\"', '"')
```

**Effect:**
- Handles stringified list wrappers `['...']`
- Unescapes quotes for clean parsing
- Fallback to first sentence if no tags found

## Data Flow (After Fixes)

```
1. User speaks
   ↓
2. LiveKit STT transcribes → sends to agent LLM
   ↓
3. LLM generates: "[VOICE]brief answer[/VOICE][TEXT]detailed info[/TEXT]"
   ↓
4. Response goes through graph_wrapper:
   - Parses dual format
   - Extracts VOICE: "brief answer"
   - Returns AIMessage(content="brief answer")
   ↓
5. Agent TTS speaks: "brief answer" (clean, no tags) ✅
   ↓
6. conversation_item_added fires:
   - Receives original full content with tags
   - Extracts content from chunks (improved handler)
   - Parses dual format to get TEXT
   - Sends TEXT via data channel to chat ✅
   ↓
7. Frontend displays:
   - User hears: "brief answer"
   - Chat shows: "detailed info"
```

## Remaining Issue

### Consecutive Assistant Messages

**Status:** Not fully addressed in this fix

**Description:**
When user stays silent, agent may generate multiple prompts ("I didn't catch that...") without user input, causing consecutive assistant messages error.

**Potential Solutions:**
1. Disable automatic prompting in agent configuration
2. Add conversation history check before generating prompts
3. Insert dummy user message before prompt

**Priority:** Medium (doesn't affect core dual response functionality)

## Testing Checklist

- [ ] User speaks → Agent responds → Voice is brief and clean (no tags)
- [ ] Chat displays detailed TEXT portion
- [ ] Voice and text are different (voice shorter)
- [ ] Multiple interactions work without consecutive message errors
- [ ] Content extraction handles different formats correctly
- [ ] TTS doesn't speak `['[VOICE]...` or tags

## Files Modified

1. **services/livekit_agent.py**
   - Lines 856-896: LLM configuration to use graph_wrapper via langchain adapter
   - Lines 986-1022: Improved content extraction in conversation_item_added handler
   - Lines 252-295: Enhanced parse_dual_response with list wrapper handling (from previous fix)

## Rollback

If issues occur:
```bash
git diff HEAD -- services/livekit_agent.py > /tmp/livekit_dual_fix.patch
git checkout HEAD -- services/livekit_agent.py
```

## Next Steps

1. Restart LiveKit agent service
2. Test voice interaction with inventory query
3. Verify TTS speaks clean text
4. Verify chat shows detailed response
5. Monitor logs for consecutive message errors
6. If consecutive messages still occur, implement agent timeout configuration
