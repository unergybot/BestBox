# Troubleshooting Service Health Status in UI

## Issue: Services Show Red/Offline in Frontend

If the ServiceStatusCard shows all services as red (offline) even though they're running, it's likely a CORS (Cross-Origin Resource Sharing) issue.

## Root Cause

The frontend (localhost:3000) needs to make HTTP requests to backend services (localhost:8080, 8081, etc.). Browsers block these requests unless the backend services send proper CORS headers.

## Fix Applied

CORS middleware has been added to all FastAPI services:
- `services/embeddings/main.py`
- `services/agent_api.py`
- `services/rag_pipeline/reranker.py`
- S2S Gateway (already had CORS)

## How to Apply the Fix

**Option 1: Restart All Services (Recommended)**

```bash
# Stop all Python services
pkill -9 -f "uvicorn|agent_api|reranker|llama-server"

# Restart everything
./scripts/start-all-services.sh

# Start frontend in separate terminal
cd frontend/copilot-demo
npm run dev
```

**Option 2: Restart Individual Services**

```bash
# Stop services
pkill -9 -f "services.embeddings.main"
pkill -9 -f "services.agent_api"
pkill -9 -f "reranker.py"

# Restart
./scripts/start-embeddings.sh &
sleep 10
./scripts/start-agent-api.sh &
sleep 5
./scripts/start-reranker.sh &
```

## Verification

1. **Check services are running:**
   ```bash
   curl http://localhost:8080/health  # LLM
   curl http://localhost:8081/health  # Embeddings
   curl http://localhost:8082/health  # Reranker
   curl http://localhost:8000/health  # Agent API
   curl http://localhost:8765/health  # S2S
   curl http://localhost:6333/healthz # Qdrant
   ```

2. **Check CORS headers:**
   ```bash
   curl -v -H "Origin: http://localhost:3000" http://localhost:8081/health 2>&1 | grep "access-control-allow-origin"
   # Should show: access-control-allow-origin: *
   ```

3. **Check frontend:**
   - Open browser to `http://localhost:3000`
   - ServiceStatusCard should show 🟢 for running services
   - Open browser DevTools → Console
   - Should NOT see CORS errors

## Common Issues

### Services Started Before CORS Changes

**Problem:** You started services before pulling/applying CORS changes.

**Solution:** Kill and restart services using commands above.

### LLM Server CORS

**Note:** llama-server (port 8080) already has basic CORS support. If it shows red:
- Check if it's actually running: `pgrep -f llama-server`
- Check health: `curl http://localhost:8080/health`
- Restart if needed: `./scripts/start-llm.sh`

### Qdrant Health Check

**Note:** Qdrant uses `/healthz` endpoint (not `/health`).

The frontend hooks already use the correct endpoint.

### PostgreSQL/Redis Warnings

These are **expected** and **harmless**. PostgreSQL and Redis don't have HTTP health endpoints, so the startup script shows warnings. They're actually running fine (check with `docker ps`).

## Browser DevTools Debugging

1. Open browser DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Look for requests to localhost:8080, 8081, etc.
5. Check if they:
   - Return 200 OK (good)
   - Return CORS errors (need to restart services)
   - Time out (service not running)

## Technical Details

### CORS Middleware Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Production Considerations

For production deployment, change `allow_origins=["*"]` to specific origins:

```python
allow_origins=[
    "http://localhost:3000",
    "https://your-production-domain.com",
],
```

## Service Health Polling

The frontend polls service health endpoints every 10 seconds:
- Timeout: 2 seconds per request
- Status: healthy (🟢), degraded (🟡), offline (🔴), checking (⚪)

If a service takes >2s to respond, it's marked offline temporarily.
