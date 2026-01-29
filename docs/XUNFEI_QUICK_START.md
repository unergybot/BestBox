# Xunfei Integration Quick Start Guide

## Overview

This guide shows how to use the Xunfei speech integration with BestBox LiveKit agent.

---

## Configuration

### Option 1: Use Local Speech (Default)

No configuration needed. The system uses on-premise models by default.

```bash
# .env (default)
SPEECH_PROVIDER=local
```

### Option 2: Use Xunfei Cloud Speech

Add Xunfei credentials to `.env`:

```bash
# Speech provider selection
SPEECH_PROVIDER=xunfei

# Xunfei credentials (get from https://console.xfyun.cn/)
XUNFEI_APP_ID=your_app_id_here
XUNFEI_API_KEY=your_api_key_here
XUNFEI_API_SECRET=your_api_secret_here

# Optional settings (defaults shown)
XUNFEI_LANGUAGE=zh_cn           # or en_us
XUNFEI_TTS_VOICE=xiaoyan        # or xiaofeng, xiaoyan_emo, etc.
```

---

## Usage

### Starting the LiveKit Agent

```bash
# With environment-based configuration
python services/livekit_agent.py dev

# Or with explicit provider selection
SPEECH_PROVIDER=xunfei python services/livekit_agent.py dev
```

### Testing

```bash
# Run unit tests
pytest tests/test_xunfei_adapters.py -v

# Run E2E tests
pytest tests/test_voice_pipeline_e2e.py -v

# Run all tests
./scripts/run_voice_e2e_tests.sh
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Speech Provider Factory           │
│         (services/speech_providers.py)      │
└─────────────────┬───────────────────────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
       ▼                     ▼
┌─────────────┐      ┌──────────────┐
│ Local Speech│      │Xunfei Speech │
│ (On-premise)│      │   (Cloud)    │
└──────┬──────┘      └──────┬───────┘
       │                    │
       │  LocalSTT          │  XunfeiSTT
       │  LocalTTS          │  XunfeiTTS
       │                    │
       └────────┬───────────┘
                │
                ▼
        ┌──────────────┐
        │ LiveKit Agent│
        └──────────────┘
```

---

## Provider Comparison

| Feature | Local | Xunfei |
|---------|-------|--------|
| **Latency** | Lower (on-device) | Higher (network) |
| **Cost** | Free | Pay-per-use |
| **Privacy** | Full (on-premise) | Cloud-based |
| **Languages** | Multi-language | Optimized for Chinese |
| **Quality** | Good | Excellent |
| **Setup** | None | Requires API credentials |
| **Offline** | ✅ Yes | ❌ No |

---

## Switching Providers

You can switch providers without code changes by updating the environment variable:

```bash
# Switch to Xunfei
export SPEECH_PROVIDER=xunfei
python services/livekit_agent.py dev

# Switch back to local
export SPEECH_PROVIDER=local
python services/livekit_agent.py dev
```

Or update `.env` file permanently.

---

## Troubleshooting

### Issue: "Missing Xunfei credentials"

**Solution:** Set all required environment variables:
```bash
XUNFEI_APP_ID=...
XUNFEI_API_KEY=...
XUNFEI_API_SECRET=...
```

### Issue: WebSocket connection failed

**Possible causes:**
1. Invalid credentials
2. Network firewall blocking Xunfei endpoints
3. API rate limits exceeded

**Solution:** Check credentials and network connectivity:
```bash
curl -v https://iat-api.xfyun.cn/v2/iat
```

### Issue: TTS audio quality poor

**Solution:** Adjust TTS parameters in `xunfei_adapters.py`:
```python
"business": {
    "speed": 50,   # 0-100 (50=normal)
    "volume": 50,  # 0-100
    "pitch": 50,   # 0-100
}
```

### Issue: STT not recognizing speech

**Possible causes:**
1. Wrong language setting
2. Poor audio quality
3. Unsupported audio format

**Solution:** Verify settings:
```bash
XUNFEI_LANGUAGE=zh_cn  # or en_us for English
```

---

## API Limits

Xunfei free tier limits (as of 2026):
- STT: 500 calls/day
- TTS: 500 calls/day

For production use, upgrade to paid plan at https://console.xfyun.cn/

---

## Security Best Practices

1. **Never commit credentials**
   - Keep `.env` in `.gitignore`
   - Use environment variables in production

2. **Use secret management**
   - For production: AWS Secrets Manager, HashiCorp Vault, etc.
   - Rotate API keys regularly

3. **Monitor usage**
   - Track API calls to avoid unexpected charges
   - Set up alerts for quota limits

---

## Advanced Configuration

### Custom Endpoints (China regions)

```bash
# Default China endpoints (built-in)
XUNFEI_STT_ENDPOINT=wss://iat-api.xfyun.cn/v2/iat
XUNFEI_TTS_ENDPOINT=wss://tts-api.xfyun.cn/v2/tts
```

### Different TTS Voices

Available voices:
- `xiaoyan` - Female (default)
- `xiaofeng` - Male
- `xiaoyan_emo` - Female with emotion
- More voices: https://www.xfyun.cn/doc/tts/online_tts/API.html

```bash
XUNFEI_TTS_VOICE=xiaofeng
```

### Language Support

```bash
# Chinese (Mandarin)
XUNFEI_LANGUAGE=zh_cn

# English
XUNFEI_LANGUAGE=en_us
```

---

## Performance Tuning

### Reduce Latency

1. **Use regional endpoints** (if available)
2. **Optimize network path** (CDN, dedicated line)
3. **Enable connection pooling** (already implemented)

### Improve Audio Quality

1. **Use higher quality resampling**:
   ```bash
   pip install scipy
   # scipy-based resampling is used automatically if available
   ```

2. **Adjust TTS parameters** (speed, pitch, volume)

3. **Use better audio format** (currently using PCM16)

---

## Integration Testing

### Test with real audio

```python
import asyncio
from services.speech_providers import create_stt, create_tts

async def test_speech():
    # Create providers
    stt = await create_stt()
    tts = await create_tts()

    # Test STT stream
    stt_stream = stt.stream()
    # ... push audio frames ...

    # Test TTS stream
    tts_stream = tts.stream()
    # ... receive synthesized audio ...

asyncio.run(test_speech())
```

### Monitor metrics

```python
from livekit.agents import metrics

# Metrics are automatically collected
# View in logs or export to Prometheus
```

---

## References

- **Xunfei Console:** https://console.xfyun.cn/
- **API Documentation:** https://www.xfyun.cn/doc/
- **Voice List:** https://www.xfyun.cn/doc/tts/online_tts/API.html
- **LiveKit Agents:** https://docs.livekit.io/agents/

---

## Support

For issues:
1. Check test results: `./scripts/run_voice_e2e_tests.sh`
2. Review logs: `tail -f agent_debug.log`
3. File bug report with logs and configuration
