# CopilotKit Integration Issue - January 23, 2026

## Problem Summary

The CopilotKit demo is experiencing an API connectivity issue where it attempts to reach OpenAI's cloud API (`https://api.openai.com/v1/responses`) instead of the local llama-server (`http://127.0.0.1:8080/v1`).

## Error Details

```
Error [AI_APICallError]: Incorrect API key provided: not-needed. 
You can find your API key at https://platform.openai.com/account/api-keys.
    at ignore-listed frames {
  cause: undefined,
  url: 'https://api.openai.com/v1/responses',
  requestBodyValues: [Object],
  statusCode: 401,
  ...
}
```

## Root Cause Analysis

1. **Endpoint Mismatch**: The error shows CopilotKit is trying to access `/v1/responses`, which is OpenAI's Realtime API endpoint (for speech/audio streaming), not the standard `/v1/chat/completions` endpoint.

2. **CopilotKit Version**: Running v1.51.2 which may have added Realtime API support for certain features.

3. **Configuration**: Despite setting `baseURL: "http://127.0.0.1:8080/v1"` in the OpenAI client, CopilotKit appears to bypass this for specific features.

## Verification Tests

### llama-server is working correctly:
```bash
$ curl http://127.0.0.1:8080/health
{"status":"ok"}

$ curl http://127.0.0.1:8080/v1/models | jq '.data[0].id'
"Qwen2.5-14B-Instruct-Q4_K_M.gguf"

$ curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen2.5-14B-Instruct-Q4_K_M.gguf","messages":[{"role":"user","content":"Say hello"}],"max_tokens":10}'
{"choices":[{"message":{"content":"Hello! How can I assist you today?"}}]}
```

All local API endpoints are functioning properly.

## Attempted Solutions

1. ✅ Changed API key from `"not-needed"` to `"sk-no-key-required"` (OpenAI SDK format validation)
2. ✅ Verified model name matches llama-server: `"Qwen2.5-14B-Instruct-Q4_K_M.gguf"`
3. ✅ Confirmed baseURL is set to local server
4. ❌ Issue persists - CopilotKit still tries to reach OpenAI cloud

## Possible Solutions

### Option 1: Use LangChain Adapter (Recommended)

CopilotKit supports LangChain, which has better support for custom OpenAI-compatible endpoints:

```typescript
import { LangChainAdapter } from "@copilotkit/runtime";
import { ChatOpenAI } from "@langchain/openai";

const model = new ChatOpenAI({
  modelName: "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
  configuration: {
    baseURL: "http://127.0.0.1:8080/v1",
    apiKey: "not-needed",
  },
});

const serviceAdapter = new LangChainAdapter({ chainOrLLM: model });
```

### Option 2: Downgrade CopilotKit

Try version 1.40.x or earlier that may not use Realtime API:

```bash
npm install @copilotkit/react-core@1.40.0 @copilotkit/react-ui@1.40.0 @copilotkit/runtime@1.40.0
```

### Option 3: Use CopilotKit Cloud (Workaround)

Use CopilotKit's cloud runtime as a proxy (requires account):

```typescript
<CopilotKit publicApiKey="your-copilotkit-cloud-key">
```

### Option 4: Custom Adapter Implementation

Create a custom LLM adapter that directly calls llama-server:

```typescript
import { CopilotServiceAdapter } from "@copilotkit/runtime";

class LlamaServerAdapter implements CopilotServiceAdapter {
  async process(request) {
    const response = await fetch("http://127.0.0.1:8080/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        messages: request.messages,
        stream: true,
      }),
    });
    return response;
  }
}
```

### Option 5: Proxy/Intercept Requests

Set up a local proxy that intercepts OpenAI API calls and redirects to llama-server:

```typescript
// In next.config.ts
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/openai/:path*',
        destination: 'http://127.0.0.1:8080/v1/:path*',
      },
    ];
  },
};
```

## Recommended Next Steps

1. **Try LangChain Adapter First** (Option 1)
   - Most compatible with custom endpoints
   - Well-documented and maintained
   - Should respect baseURL configuration

2. **If LangChain doesn't work, downgrade CopilotKit** (Option 2)
   - Older versions use standard chat completions
   - No Realtime API dependencies

3. **Last resort: Custom Adapter** (Option 4)
   - Full control over API calls
   - More maintenance overhead
   - Requires implementing streaming logic

## Status

- llama-server: ✅ Operational (localhost:8080)
- Frontend: ✅ Running (localhost:3000)
- API Integration: ❌ **BLOCKED** - Cannot connect to local LLM

## Files Affected

- `/home/unergy/BestBox/frontend/copilot-demo/app/api/copilotkit/route.ts` - API route configuration
- Current CopilotKit version: 1.51.2

## Next Action

Implement LangChain adapter solution to bypass OpenAI SDK limitations.
