# OpenClaw BestBox ASR/TTS Testing Strategy

**Date:** 2026-02-14  
**Status:** Draft  
**Coverage Target:** > 80%  

## Overview

This document outlines the comprehensive testing strategy for the OpenClaw BestBox ASR/TTS integration, ensuring reliability, performance, and correctness across all components.

## Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E Tests │  10%  (User scenarios)
                    │   (Slow)    │
                    ├─────────────┤
                    │ Integration │  20%  (Component interaction)
                    │    Tests    │
                    ├─────────────┤
                    │   Unit Tests│  70%  (Individual functions)
                    │   (Fast)    │
                    └─────────────┘
```

## Test Categories

### 1. Unit Tests

**Purpose:** Test individual functions and classes in isolation.

**Location:** `extensions/bestbox/test/*.test.ts`

#### 1.1 ASR Client Tests

**File:** `test/asr-client.test.ts`

**Test Cases:**

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| ASR-001 | Transcribe valid audio | WAV file buffer | TranscriptionResult with text |
| ASR-002 | Transcribe MP3 audio | MP3 file buffer | TranscriptionResult with text |
| ASR-003 | Transcribe with language hint | audio + "en" | Result with language="en" |
| ASR-004 | Handle empty audio | Empty buffer | Error: "No audio data" |
| ASR-005 | Handle invalid format | PDF file | Error: "Invalid audio format" |
| ASR-006 | Handle service unavailable | No server | Error: "Connection refused" |
| ASR-007 | Handle timeout | Slow server | Error: "Request timeout" |
| ASR-008 | Health check success | Server running | { status: "ok" } |
| ASR-009 | Health check failure | Server down | { status: "error" } |
| ASR-010 | Retry on transient error | 503 error then success | Success after retry |

**Mock Strategy:**
```typescript
// Mock HTTP client
const mockAxios = new MockAdapter(axios);

// Mock successful transcription
mockAxios.onPost("http://localhost:8003/v1/audio/transcriptions")
  .reply(200, {
    text: "Hello world",
    language: "en",
    confidence: 0.95
  });

// Mock service unavailable
mockAxios.onPost("http://localhost:8003/v1/audio/transcriptions")
  .reply(503, { error: "Model not loaded" });
```

#### 1.2 TTS Client Tests

**File:** `test/tts-client.test.ts`

**Test Cases:**

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| TTS-001 | Synthesize simple text | "Hello" | Audio buffer (WAV) |
| TTS-002 | Synthesize long text | 1000 chars | Audio buffer (WAV) |
| TTS-003 | Synthesize with voice cloning | text + ref audio | Cloned voice audio |
| TTS-004 | Synthesize with speed | text + speed: 1.5 | Faster audio |
| TTS-005 | Handle empty text | "" | Error: "Empty text" |
| TTS-006 | Handle invalid language | "Klingon" | Error: "Unsupported language" |
| TTS-007 | Handle missing ref audio | text + missing file | Error: "Reference audio not found" |
| TTS-008 | Handle service error | Server error | Error with details |
| TTS-009 | Stream synthesis | Long text | Audio chunks iterable |
| TTS-010 | Cancel synthesis | AbortController | Request cancelled |

#### 1.3 S2S Client Tests

**File:** `test/s2s-client.test.ts`

**Test Cases:**

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| S2S-001 | Connect successfully | Valid URL | Connection established |
| S2S-002 | Connect with auth | URL + token | Connection with auth |
| S2S-003 | Reconnect on disconnect | Disconnect event | Auto-reconnect |
| S2S-004 | Send audio chunk | Buffer | Chunk sent |
| S2S-005 | Receive transcript | Server message | Event emitted |
| S2S-006 | Receive partial transcript | Server message | Partial event emitted |
| S2S-007 | Receive audio response | Server message | Audio event emitted |
| S2S-008 | Handle speech start | Server message | Speech start event |
| S2S-009 | Handle speech end | Server message | Speech end event |
| S2S-010 | Handle server error | Error message | Error event emitted |
| S2S-011 | Handle connection timeout | Slow server | Timeout error |
| S2S-012 | Handle max reconnect | 5 failures | Final error |
| S2S-013 | Send ping | Ping message | Pong received |
| S2S-014 | Disconnect gracefully | Close message | Clean disconnect |
| S2S-015 | Handle binary audio | Binary message | Correctly parsed |

**Mock Strategy:**
```typescript
// Mock WebSocket
const mockServer = new WS("ws://localhost:8765/ws");

// Mock connection
mockServer.on("connection", (socket) => {
  socket.send(JSON.stringify({ type: "ready", session_id: "test-123" }));
});

// Mock transcript
mockServer.on("message", (data) => {
  const msg = JSON.parse(data as string);
  if (msg.type === "audio") {
    mockServer.send(JSON.stringify({
      type: "transcript",
      text: "Hello",
      language: "en"
    }));
  }
});
```

#### 1.4 Voice Conversation Tests

**File:** `test/voice-conversation.test.ts`

**Test Cases:**

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| VC-001 | Start conversation | start() | State: "connecting" → "listening" |
| VC-002 | Send audio | Buffer | Audio sent to S2S |
| VC-003 | Receive transcript | Mock transcript | Event emitted |
| VC-004 | Receive response | Mock response | Response event emitted |
| VC-005 | Stop conversation | stop() | State: "closed" |
| VC-006 | Handle connection error | Connection fails | Error event, state: "error" |
| VC-007 | Barge-in | Audio during AI speech | AI interrupted |
| VC-008 | Silence timeout | No audio for 30s | Session ended |
| VC-009 | Max duration | 10 minutes | Session ended |
| VC-010 | State transitions | Various actions | Correct state sequence |

**State Machine Tests:**
```typescript
// Test state transitions
expect(conversation.getState()).toBe("idle");
await conversation.start();
expect(conversation.getState()).toBe("listening");
conversation.sendAudio(buffer);
expect(conversation.getState()).toBe("processing");
// ... etc
```

#### 1.5 Configuration Tests

**File:** `test/config.test.ts`

**Test Cases:**

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| CFG-001 | Valid minimal config | { enabled: true } | Validated config |
| CFG-002 | Valid full config | All options | Validated config |
| CFG-003 | Invalid URL | "not-a-url" | Validation error |
| CFG-004 | Invalid timeout | -1 | Validation error |
| CFG-005 | Missing required | Partial config | Default values applied |
| CFG-006 | Type coercion | String number | Number parsed |
| CFG-007 | Nested validation | Invalid nested | Detailed error path |

### 2. Integration Tests

**Purpose:** Test component interactions and API contracts.

**Location:** `test/*.integration.test.ts`

#### 2.1 ASR Provider Integration

**File:** `test/asr-provider.integration.test.ts`

**Test Cases:**

| Test ID | Description | Setup | Verification |
|---------|-------------|-------|--------------|
| ASR-INT-001 | Provider registered | Load extension | Provider in registry |
| ASR-INT-002 | Transcribe via provider | Provider.transcribe() | Result returned |
| ASR-INT-003 | Language detection | Auto-detect | Correct language |
| ASR-INT-004 | OpenClaw media pipeline | Voice message | Transcribed automatically |
| ASR-INT-005 | Fallback to cloud | Local fails | Cloud provider used |

**Test Setup:**
```typescript
// Start BestBox ASR service (or mock)
const asrService = await startASRService();

// Register provider
const registry = buildMediaUnderstandingRegistry();
const provider = registry.get("bestbox-asr");

// Run tests
const result = await provider.transcribe(audioBuffer);
expect(result.text).toBeTruthy();

// Cleanup
await asrService.stop();
```

#### 2.2 TTS Provider Integration

**File:** `test/tts-provider.integration.test.ts`

**Test Cases:**

| Test ID | Description | Setup | Verification |
|---------|-------------|-------|--------------|
| TTS-INT-001 | Provider integration | TTS provider | Audio generated |
| TTS-INT-002 | Reply with voice | AI response | Audio attached |
| TTS-INT-003 | Voice cloning | Reference audio | Cloned voice |
| TTS-INT-004 | Provider fallback | BestBox fails | Fallback to OpenAI |
| TTS-INT-005 | Audio format conversion | Different formats | Correct output |

#### 2.3 End-to-End Voice Conversation

**File:** `test/voice-conversation.e2e.test.ts`

**Test Cases:**

| Test ID | Description | Setup | Verification |
|---------|-------------|-------|--------------|
| E2E-001 | Full conversation | All services | Complete flow |
| E2E-002 | Multi-turn conversation | 5 exchanges | All turns processed |
| E2E-003 | Voice cloning conversation | Cloned voice | Consistent voice |
| E2E-004 | Error recovery | Service restart | Auto-recovery |
| E2E-005 | Concurrent conversations | 4 sessions | All work correctly |

**Test Scenario (E2E-001):**
```typescript
it("completes full voice conversation", async () => {
  // Setup
  const conversation = new VoiceConversation({
    s2sUrl: "ws://localhost:8765"
  });
  
  const transcripts: string[] = [];
  const responses: string[] = [];
  
  conversation.onTranscript((e) => transcripts.push(e.text));
  conversation.onResponse((e) => responses.push(e.text));
  
  // Execute
  await conversation.start();
  
  // Simulate user speaking
  const userAudio = await loadAudio("hello.wav");
  conversation.sendAudio(userAudio);
  
  // Wait for response
  await waitFor(() => responses.length > 0, { timeout: 10000 });
  
  // Verify
  expect(transcripts).toContain("Hello");
  expect(responses[0]).toBeTruthy();
  
  // Cleanup
  await conversation.stop();
});
```

### 3. Performance Tests

**Purpose:** Verify performance meets targets.

**Location:** `test/*.perf.test.ts`

#### 3.1 ASR Performance

**Metrics:**
- End-to-end latency: < 500ms
- Throughput: > 10 transcriptions/second
- Memory usage: < 500MB

**Tests:**
```typescript
it("transcribes within latency target", async () => {
  const audio = await loadAudio("test.wav");
  
  const start = performance.now();
  const result = await client.transcribe(audio);
  const latency = performance.now() - start;
  
  expect(latency).toBeLessThan(500);
  expect(result.text).toBeTruthy();
});

it("handles concurrent requests", async () => {
  const audio = await loadAudio("test.wav");
  const requests = Array(10).fill(audio);
  
  const start = performance.now();
  const results = await Promise.all(
    requests.map(a => client.transcribe(a))
  );
  const totalTime = performance.now() - start;
  
  expect(results).toHaveLength(10);
  expect(totalTime / 10).toBeLessThan(500);
});
```

#### 3.2 TTS Performance

**Metrics:**
- Time to first byte: < 1s
- Throughput: > 5 syntheses/second
- Audio quality: PESQ > 3.0

#### 3.3 S2S Performance

**Metrics:**
- Round-trip latency: < 200ms
- Audio streaming latency: < 50ms
- Connection stability: 0 disconnects/hour

### 4. Contract Tests

**Purpose:** Verify API contracts with BestBox services.

**Location:** `test/contracts/`

**Files:**
- `asr-contract.test.ts`
- `tts-contract.test.ts`
- `s2s-contract.test.ts`

**Example:**
```typescript
describe("ASR API Contract", () => {
  it("matches expected response schema", async () => {
    const response = await fetch("http://localhost:8003/v1/audio/transcriptions", {
      method: "POST",
      body: formData
    });
    
    const data = await response.json();
    
    // Validate schema
    expect(data).toMatchSchema({
      type: "object",
      required: ["text", "language"],
      properties: {
        text: { type: "string" },
        language: { type: "string" },
        confidence: { type: "number" }
      }
    });
  });
});
```

### 5. Error Scenario Tests

**Purpose:** Test error handling and recovery.

**Location:** `test/error-scenarios.test.ts`

#### 5.1 Network Errors

| Scenario | Expected Behavior |
|----------|-------------------|
| Connection refused | Retry with backoff, then fail |
| Connection timeout | Retry immediately |
| Connection reset | Reconnect and resume |
| DNS failure | Fail fast with clear error |

#### 5.2 Service Errors

| Scenario | Expected Behavior |
|----------|-------------------|
| Model loading | Wait and retry |
| Out of memory | Fail with resource error |
| GPU error | Fall back to CPU or cloud |
| Invalid request | Return validation error |

#### 5.3 Client Errors

| Scenario | Expected Behavior |
|----------|-------------------|
| Invalid audio format | Return format error |
| Text too long | Return length error |
| Missing reference audio | Return file error |
| Invalid configuration | Return config error |

### 6. Compatibility Tests

**Purpose:** Test compatibility with different environments.

**Location:** `test/compatibility.test.ts`

**Test Matrix:**

| Node Version | OS | Status |
|--------------|-----|--------|
| 18.x | Linux | Required |
| 20.x | Linux | Required |
| 18.x | macOS | Required |
| 20.x | macOS | Required |
| 18.x | Windows | Optional |

**BestBox Versions:**

| BestBox Version | Compatibility |
|-----------------|---------------|
| 1.0.0 | Required |
| 1.1.0 | Required |
| 2.0.0 | Optional |

### 7. Security Tests

**Purpose:** Verify security measures.

**Location:** `test/security.test.ts`

**Tests:**
- [ ] Input sanitization
- [ ] No sensitive data in logs
- [ ] No credential leakage
- [ ] Rate limiting enforced
- [ ] CORS headers correct
- [ ] File upload limits

### 8. Accessibility Tests

**Purpose:** Ensure voice features are accessible.

**Tests:**
- [ ] Works with screen readers
- [ ] Keyboard navigation
- [ ] Visual indicators for audio state
- [ ] Error messages are descriptive

## Test Data

### Audio Samples

**Location:** `test/fixtures/audio/`

**Files:**
- `hello.wav` - Simple greeting (2s, 16kHz)
- `long-text.wav` - Long sentence (10s)
- `noise.wav` - Background noise only
- `mixed.wav` - Speech with noise
- `empty.wav` - Silence

### Reference Audio

**Location:** `test/fixtures/voices/`

**Files:**
- `reference-male.wav` - Male voice sample
- `reference-female.wav` - Female voice sample
- `reference-accent.wav` - Accent sample

### Mock Responses

**Location:** `test/fixtures/responses/`

**Files:**
- `asr-success.json` - Successful transcription
- `asr-error.json` - ASR error
- `tts-success.bin` - TTS audio data
- `tts-error.json` - TTS error

## Test Environment

### Local Development

```bash
# Install dependencies
npm install

# Run unit tests
npm test

# Run integration tests (requires BestBox services)
npm run test:integration

# Run E2E tests
npm run test:e2e

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- asr-client.test.ts
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 20
      - run: npm ci
      - run: npm run lint
      - run: npm test -- --coverage
      - run: npm run test:integration
        if: github.event_name == 'pull_request'
```

### Docker Test Environment

```dockerfile
# Dockerfile.test
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm", "test"]
```

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  bestbox-asr:
    image: bestbox/asr:latest
    ports:
      - "8003:8003"
  
  bestbox-tts:
    image: bestbox/tts:latest
    ports:
      - "8004:8004"
  
  bestbox-s2s:
    image: bestbox/s2s:latest
    ports:
      - "8765:8765"
  
  tests:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      - bestbox-asr
      - bestbox-tts
      - bestbox-s2s
    environment:
      ASR_URL: http://bestbox-asr:8003
      TTS_URL: http://bestbox-tts:8004
      S2S_URL: ws://bestbox-s2s:8765
```

## Coverage Requirements

### Minimum Coverage

| Component | Lines | Branches | Functions |
|-----------|-------|----------|-----------|
| ASR Client | 90% | 85% | 90% |
| TTS Client | 90% | 85% | 90% |
| S2S Client | 85% | 80% | 85% |
| Voice Conversation | 85% | 80% | 85% |
| Configuration | 95% | 90% | 95% |
| **Overall** | **85%** | **80%** | **85%** |

### Coverage Exclusions

- Test files (`*.test.ts`)
- Type definitions (`*.d.ts`)
- Generated code
- External dependencies

## Test Reporting

### Coverage Report

```bash
# Generate HTML report
npm run test:coverage -- --reporter=html

# Generate JSON report
npm run test:coverage -- --reporter=json

# Generate LCOV report
npm run test:coverage -- --reporter=lcov
```

### Test Results

```bash
# JUnit XML format
npm test -- --reporter=junit --outputFile=./test-results.xml
```

## Debugging Tests

### VS Code Configuration

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Tests",
      "type": "node",
      "request": "launch",
      "program": "${workspaceFolder}/node_modules/.bin/vitest",
      "args": ["run", "${relativeFile}"],
      "console": "integratedTerminal",
      "internalConsoleOptions": "neverOpen"
    }
  ]
}
```

### Debugging Tips

1. **Use `--inspect-brk`:**
   ```bash
   node --inspect-brk node_modules/.bin/vitest run
   ```

2. **Add debug logs:**
   ```typescript
   console.log("Debug:", variable);
   ```

3. **Use test.only:**
   ```typescript
   it.only("debug this test", () => {
     // Test code
   });
   ```

4. **Check mock setup:**
   ```typescript
   console.log("Mock calls:", mockFn.mock.calls);
   ```

## Continuous Testing

### Pre-commit Hooks

```json
// .husky/pre-commit
{
  "hooks": {
    "pre-commit": "lint-staged && npm test -- --changedSince HEAD"
  }
}
```

### Nightly Tests

```yaml
# .github/workflows/nightly.yml
name: Nightly Tests
on:
  schedule:
    - cron: '0 0 * * *'
jobs:
  full-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm ci
      - run: npm run test:all
      - run: npm run test:e2e
      - run: npm run test:performance
```

## Test Maintenance

### Updating Tests

1. When adding features, add corresponding tests
2. When fixing bugs, add regression tests
3. When refactoring, ensure tests still pass
4. Update mocks when API changes

### Flaky Tests

**Handling Strategy:**
1. Identify flaky tests via CI metrics
2. Add retries for transient failures
3. Fix root cause if possible
4. Quarantine if unfixable

```typescript
it("sometimes flaky test", { retries: 3 }, async () => {
  // Test code
});
```

## Appendix A: Test Utilities

### Helper Functions

```typescript
// test/helpers/index.ts

export async function loadAudio(path: string): Promise<Buffer> {
  return fs.readFile(path);
}

export async function waitFor(
  condition: () => boolean,
  options: { timeout?: number; interval?: number } = {}
): Promise<void> {
  const { timeout = 5000, interval = 100 } = options;
  const start = Date.now();
  
  while (Date.now() - start < timeout) {
    if (condition()) return;
    await new Promise(r => setTimeout(r, interval));
  }
  
  throw new Error("Timeout waiting for condition");
}

export function mockASRResponse(text: string): object {
  return {
    text,
    language: "en",
    confidence: 0.95
  };
}

export function createMockAudio(durationMs: number): Buffer {
  // Generate mock PCM audio
  const sampleRate = 16000;
  const samples = (durationMs / 1000) * sampleRate;
  return Buffer.alloc(samples * 2); // 16-bit samples
}
```

### Test Fixtures

```typescript
// test/fixtures/index.ts

export const FIXTURES = {
  audio: {
    hello: path.join(__dirname, "audio/hello.wav"),
    silence: path.join(__dirname, "audio/silence.wav"),
    noise: path.join(__dirname, "audio/noise.wav")
  },
  voices: {
    male: path.join(__dirname, "voices/reference-male.wav"),
    female: path.join(__dirname, "voices/reference-female.wav")
  },
  responses: {
    asrSuccess: JSON.parse(
      fs.readFileSync(path.join(__dirname, "responses/asr-success.json"), "utf-8")
    )
  }
};
```

## Appendix B: Common Test Patterns

### Mocking HTTP

```typescript
import MockAdapter from "axios-mock-adapter";

const mock = new MockAdapter(axios);

beforeEach(() => {
  mock.reset();
});

it("handles API error", async () => {
  mock.onPost("/transcribe").reply(500, { error: "Server error" });
  
  await expect(client.transcribe(audio))
    .rejects.toThrow("Server error");
});
```

### Mocking WebSocket

```typescript
import WS from "jest-websocket-mock";

let server: WS;

beforeEach(() => {
  server = new WS("ws://localhost:8765/ws");
});

afterEach(() => {
  WS.clean();
});

it("receives message", async () => {
  const client = new S2SClient({ url: "ws://localhost:8765/ws" });
  await client.connect();
  await server.connected;
  
  server.send(JSON.stringify({ type: "transcript", text: "Hello" }));
  
  const message = await waitForMessage(client);
  expect(message.text).toBe("Hello");
});
```

### Testing Async Operations

```typescript
it("completes async operation", async () => {
  const results: string[] = [];
  
  client.onTranscript((msg) => results.push(msg.text));
  
  // Trigger async operation
  client.sendAudio(audio);
  
  // Wait for result
  await waitFor(() => results.length > 0, { timeout: 5000 });
  
  expect(results[0]).toBe("Hello");
});
```

## Appendix C: Troubleshooting

### Common Issues

**Issue:** Tests fail with "Connection refused"
**Solution:** Ensure BestBox services are running or use mocks

**Issue:** WebSocket tests timeout
**Solution:** Increase timeout or check mock server setup

**Issue:** Coverage not reported
**Solution:** Check `coverage/` directory exists and is writable

**Issue:** Tests pass locally but fail in CI
**Solution:** Check environment differences, add debugging

### Debug Mode

```bash
# Verbose output
DEBUG=bestbox* npm test

# Specific test
DEBUG=bestbox:asr npm test -- asr-client

# Save debug logs
DEBUG=bestbox* npm test 2>&1 | tee test-debug.log
```
