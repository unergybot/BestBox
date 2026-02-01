# Startup Fixes Analysis

## Issues Identified

### Issue 1: LLM Server Using llama-server Instead of vLLM

**Current Behavior:**
- `start-all-services.sh` detects NVIDIA GPU and calls `start-llm-cuda.sh`
- `start-llm-cuda.sh` uses `llama-server` (llama.cpp binary)
- User expects vLLM to be used instead

**Root Cause:**
- The existing vLLM scripts (`start_vllm_*.sh`) are designed for AMD ROCm/Strix Halo
- There is NO vLLM startup script for NVIDIA/CUDA
- The `start-all-services.sh` logic defaults to llama-server for NVIDIA GPUs

**Required Fix:**
1. Create `scripts/start-vllm-cuda.sh` - A vLLM startup script for NVIDIA GPUs
2. Modify `start-all-services.sh` to call the vLLM script instead of llama-server when NVIDIA is detected

### Issue 2: Frontend (localhost:3000) Not Available

**Current Behavior:**
- `start-demo-complete.sh` tries to start frontend with `npm run dev`
- Frontend is not accessible on port 3000
- No Node.js processes running

**Root Cause:**
- The frontend startup in `start-demo-complete.sh` may have issues:
  - Directory navigation: `cd frontend/copilot-demo` then `cd ../..`
  - Background process (`nohup`) may not be working correctly
  - No verification that frontend actually started
  - The frontend.log shows CopilotKit 400 errors

**Required Fix:**
1. Improve frontend startup logic in `start-demo-complete.sh`
2. Add proper error handling and verification
3. Ensure npm dependencies are installed
4. Add port conflict detection

## Files to Modify

1. **Create:** `scripts/start-vllm-cuda.sh` - New vLLM startup script for NVIDIA
2. **Modify:** `scripts/start-all-services.sh` - Change LLM startup logic (lines 106-122)
3. **Modify:** `scripts/start-demo-complete.sh` - Fix frontend startup (lines 36-46)

## Configuration Requirements

### vLLM CUDA Script Requirements:
- Use official vLLM Docker image for CUDA: `vllm/vllm-openai:latest`
- Port: 8080 (to match existing expectations)
- Model: Qwen3-4B-Instruct (as per user setup)
- Health check endpoint: `/health`
- API endpoint: `/v1/chat/completions`

### Frontend Fix Requirements:
- Check if npm modules exist before starting
- Verify port 3000 is not in use
- Add proper logging
- Add health check after startup
- Handle CopilotKit configuration issues

## Verification Steps

1. After fixes, running `./scripts/start-demo-complete.sh` should:
   - Start vLLM server on port 8080 (not llama-server)
   - Start frontend on port 3000
   - Both should be accessible via curl

## References

- Existing vLLM scripts for ROCm: `scripts/start_vllm_optimized.sh`, `scripts/run_vllm_strix.sh`
- Current NVIDIA script: `scripts/start-llm-cuda.sh`
- Frontend package.json: `frontend/copilot-demo/package.json`

## Implementation Complete: start-vllm-cuda.sh

### Created: scripts/start-vllm-cuda.sh

**Features Implemented:**
- ✅ Uses official vLLM Docker image for CUDA: `vllm/vllm-openai:latest`
- ✅ Runs on port 8080 (matches existing LLM server expectations)
- ✅ Configurable model via `LLM_MODEL` env var (default: Qwen3-4B-Instruct)
- ✅ Configurable CUDA device via `LLM_CUDA_DEVICE` (default: 0)
- ✅ Health check endpoint verification (/health) with 120s timeout
- ✅ Executable permissions set (chmod +x)
- ✅ Colored output for better UX
- ✅ Docker runtime checks and error handling
- ✅ Graceful container cleanup (removes old containers)
- ✅ Comprehensive logging and troubleshooting commands

**Configuration Options (Environment Variables):**
```bash
LLM_MODEL              # HuggingFace model name (default: Qwen/Qwen3-4B-Instruct)
LLM_MODEL_PATH         # Local model path (optional)
LLM_PORT               # Server port (default: 8080)
LLM_CUDA_DEVICE        # CUDA device index (default: 0)
```

**Usage:**
```bash
./scripts/start-vllm-cuda.sh                    # Start with defaults
LLM_CUDA_DEVICE=1 ./scripts/start-vllm-cuda.sh  # Use GPU 1
LLM_MODEL="Qwen/Qwen3-14B-Instruct" ./scripts/start-vllm-cuda.sh  # Different model
```

**Docker Configuration:**
- Runtime: NVIDIA (`--runtime nvidia`)
- GPU support: `--gpus device=0` (configurable)
- Memory utilization: 0.9 (90%)
- Max model length: 8192 tokens
- GPU memory optimization: float16 dtype
- Port mapping: 8080 (host) → 8000 (container)

**Next Steps:**
- Modify `scripts/start-all-services.sh` to use this script for NVIDIA detection
- Test on actual NVIDIA GPU with vLLM
- Update documentation to include vLLM CUDA startup instructions

## Frontend Startup Fix - Completed

### Changes Made to `scripts/start-demo-complete.sh` (Lines 35-79)

**Issue 1: Directory Navigation Problem**
- **Old Code:** `cd frontend/copilot-demo` then `cd ../..` 
- **Problem:** cd operations in subshells can fail silently, process detaches from correct directory
- **Fix:** Use absolute path with `$(pwd)` in nohup command

**Issue 2: No Dependency Check**
- **Old Code:** Assumed npm modules already installed
- **Problem:** Missing node_modules causes npm install to run, process hangs waiting for dependencies
- **Fix:** Check `frontend/copilot-demo/node_modules` exists before startup, run npm install if needed

**Issue 3: No Port Conflict Detection**
- **Old Code:** No check if port 3000 already in use
- **Problem:** Multiple startups could cause conflicts, silent failures
- **Fix:** Use `lsof -i :3000` to detect port conflicts early

**Issue 4: No Process Verification**
- **Old Code:** Assumed process started successfully after nohup
- **Problem:** Process may fail immediately with no feedback
- **Fix:** Capture PID, verify process still running after 3s delay

**Issue 5: No Health Check**
- **Old Code:** No verification frontend is responding
- **Problem:** Process running but HTTP server not ready = user sees dead connection
- **Fix:** Attempt curl to localhost:3000, provide graceful degradation message if still starting

### Verification Status
✅ Shell syntax validated (bash -n)
✅ All prerequisites confirmed:
   - Port 3000 available
   - node_modules exist (747 directories)
   - Frontend directory structure valid
   - Absolute path construction works

### Improvements Summary
| Check | Type | Benefit |
|-------|------|---------|
| Port conflict | Early exit | Prevents silent failures |
| Dependencies | Auto-install | Handles fresh installs |
| Process PID | Verification | Confirms startup |
| Health check | User feedback | Shows when ready vs. starting |
| Absolute paths | Reliability | Works from any pwd |

### Expected Behavior After Fix
1. Script detects if frontend already running
2. Checks port 3000 is available
3. Installs npm deps if missing
4. Starts frontend with absolute path
5. Waits 3s for startup
6. Verifies process is running
7. Attempts health check (curl)
8. Provides clear status feedback

### Testing Notes
- Tested on Ubuntu 24.04 with Node.js installed
- All prerequisite checks passed
- Path construction verified with absolute paths
- No external dependencies added beyond existing tools (lsof, curl, ps)
