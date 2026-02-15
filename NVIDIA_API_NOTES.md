# NVIDIA API Connection Issue - Troubleshooting

## Issue
When testing connection to NVIDIA API, getting "404 Not Found" error.

## API Logs Show:
```
INFO:httpx:HTTP Request: POST https://integrate.api.nvidia.com/v1/chat/completions "HTTP/1.1 404 Not Found"
```

## Possible Causes:

### 1. **Incorrect Base URL**
NVIDIA API might have changed. Try these alternatives:
- `https://integrate.api.nvidia.com/v1` (current)
- `https://api.nvidia.com/v1`
- `https://ai.api.nvidia.com/v1`

### 2. **Model Format Incorrect**
The models you mentioned might need a different format:
- Current: `moonshotai/kimi-k2.5`
- Might need: `nvidia/kimi-k2.5` or just `kimi-k2.5`

### 3. **API Key Required for Model Discovery**
NVIDIA API might require a valid API key to test connections, even for basic requests.

## How to Fix:

### Option 1: Test with Valid API Key
If you have a valid NVIDIA API key:
1. Set it in `.env`: `NVIDIA_API_KEY=nvapi-your-actual-key`
2. Restart Agent API
3. The environment override will use the real key
4. Test connection should work

### Option 2: Update Base URL
Try the NVIDIA NIM endpoint structure:
```
Base URL: https://integrate.api.nvidia.com/v1
Model format: use exact model names from NVIDIA catalog
```

### Option 3: Skip Test for Now
The test connection is optional - you can:
1. Configure the provider settings
2. Save without testing
3. The actual chat will work if credentials are correct

## Current Workaround:

**For testing without real API key:**
- Switch to "Local vLLM" provider
- Test connection should work if vLLM is running on port 8001
- Switch back to NVIDIA for actual use with real API key

**For production use:**
- Add real `NVIDIA_API_KEY` to `.env`
- Environment variable override will use the real key
- Save configuration with NVIDIA provider
- Chat will use NVIDIA API automatically
