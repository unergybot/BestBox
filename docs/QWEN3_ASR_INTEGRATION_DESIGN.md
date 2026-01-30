# Qwen3-ASR Integration Design

**Date:** 2026-01-29
**Status:** Design Complete, Ready for Testing

## Executive Summary

Proposal to integrate Qwen3-ASR-0.6B as an alternative ASR provider for BestBox, targeting **improved accuracy for Chinese/multilingual content** while maintaining system stability through a **hybrid provider architecture**.

### Current System
- **Model:** faster-whisper tiny
- **Device:** CPU (due to ROCm stability issues)
- **Languages:** English, basic Chinese
- **Accuracy:** Limited by tiny model size

### Proposed Enhancement
- **New Provider:** Qwen3-ASR-0.6B
- **Target Device:** AMD Radeon 8060S GPU (ROCm 7.2.0)
- **Fallback:** CPU mode or faster-whisper
- **Languages:** 52 languages + 22 Chinese dialects

## Design Goals

1. **Better Accuracy:** Improve Chinese and multilingual transcription quality
2. **Maintain Stability:** Robust fallbacks if GPU/compatibility issues arise
3. **Test First:** Validate compatibility before full integration
4. **Zero Disruption:** Existing faster-whisper remains available

## Architecture: Hybrid Provider Pattern

### Provider Selection Logic

```python
if SPEECH_PROVIDER == "qwen3":
    try:
        # Attempt Qwen3-ASR on GPU
        return Qwen3ASRProvider(device="cuda")
    except GPUError:
        # Fall back to CPU
        return Qwen3ASRProvider(device="cpu")
    except ModelError:
        # Fall back to faster-whisper
        return FasterWhisperProvider()

elif SPEECH_PROVIDER == "local":
    # Current default
    return FasterWhisperProvider()

elif SPEECH_PROVIDER == "xunfei":
    return XunfeiProvider()
```

### File Structure

```
services/
├── speech_providers.py         # Extended with Qwen3 support
├── livekit_local.py            # Add Qwen3STT class
└── speech/
    └── asr_qwen3.py            # New: Qwen3-ASR wrapper (similar to asr.py)

.env
├── SPEECH_PROVIDER=qwen3       # New option
├── QWEN3_DEVICE=cuda           # GPU/CPU selection
└── QWEN3_MODEL=Qwen/Qwen3-ASR-0.6B
```

## Qwen3-ASR Capabilities

### Strengths
- **52 languages** including 30 major languages + 22 Chinese dialects
- **State-of-art accuracy** for open-source ASR on Chinese
- **Streaming support** via vLLM backend (critical for LiveKit)
- **Forced alignment** available for word-level timestamps

### Requirements
- **GPU:** Recommended for real-time performance (RTF < 1.0)
- **VRAM:** ~2-3GB for 0.6B model
- **PyTorch + ROCm:** Must verify compatibility with AMD Radeon 8060S

### Limitations
- **ROCm Compatibility:** Uncertain if PyTorch works on gfx1151 with ROCm 7.2.0
- **CPU Performance:** Likely slower than GPU, may not be real-time
- **Model Size:** 0.6B larger than Whisper tiny (~100MB vs ~40MB)

## Testing Strategy

### Phase 1: Compatibility Validation ✅ READY

**Script:** `scripts/test_qwen3_asr_compatibility.py`

**Purpose:** Quick smoke test (5 minutes) to verify:
1. PyTorch + ROCm/CUDA available
2. qwen-asr package loads
3. Model can be downloaded and initialized
4. Basic transcription works

**Run:**
```bash
python scripts/test_qwen3_asr_compatibility.py
```

**Expected Outcomes:**
- ✅ All tests pass → Proceed to Phase 2
- ⚠️ GPU fails, CPU works → Evaluate CPU performance
- ❌ Model won't load → Compatibility issues, document findings

### Phase 2: Performance Benchmark ✅ READY

**Script:** `scripts/benchmark_asr_models.py`

**Purpose:** Data-driven comparison (20-30 minutes) measuring:
- **Accuracy:** CER (Chinese), WER (English)
- **Performance:** Transcription time, Real-Time Factor
- **Resources:** RAM, VRAM usage
- **Reliability:** Success rate across 20 test samples

**Run:**
```bash
# Quick test (5 samples, 5-10 min)
python scripts/benchmark_asr_models.py --quick

# Full benchmark (20 samples, 20-30 min)
python scripts/benchmark_asr_models.py
```

**Datasets:**
- AISHELL-1 (Chinese Mandarin)
- Common Voice (English)

**Output:**
- `benchmark_results_asr_TIMESTAMP.json` - Raw metrics
- `docs/ASR_BENCHMARK_RESULTS.md` - Comparison report + recommendation

### Phase 3: Integration Design (Conditional)

**Only proceed if Phase 2 shows:**
- ✅ RTF < 1.0 (real-time capable)
- ✅ Accuracy improvement over faster-whisper
- ✅ Reasonable resource usage (<4GB VRAM)

**Tasks:**
1. Implement `services/speech/asr_qwen3.py` wrapper
2. Extend `SpeechProvider` enum with `QWEN3`
3. Add `Qwen3STT` class to `livekit_local.py`
4. Update `create_stt()` with Qwen3 path
5. Test streaming mode with LiveKit
6. Document configuration in CLAUDE.md

## Decision Tree

```
Start: Test Qwen3-ASR compatibility
│
├─ ✅ GPU works, RTF < 1.0, accuracy better
│   → IMPLEMENT: Use Qwen3-ASR as default with faster-whisper fallback
│
├─ ⚠️ GPU works, RTF > 1.0 (slow)
│   → EVALUATE: Is accuracy gain worth latency increase?
│   │  Yes → Use Qwen3 for offline/batch, faster-whisper for real-time
│   │  No  → Skip Qwen3, wait for model optimization
│
├─ ⚠️ CPU works, GPU fails
│   → PARTIAL: Offer Qwen3-CPU as accuracy mode, warn about performance
│
└─ ❌ Won't load or transcribe
    → DOCUMENT: Compatibility issues with ROCm 7.2 / gfx1151
    → WAIT: For official AMD GPU support or PyTorch updates
```

## Risk Mitigation

### Risk 1: ROCm Compatibility Issues
**Mitigation:** Test first approach (Phase 1 smoke test)
**Fallback:** CPU mode or stay with faster-whisper

### Risk 2: Insufficient Performance
**Mitigation:** Benchmark before integration (Phase 2)
**Fallback:** Keep faster-whisper for real-time, use Qwen3 for accuracy-critical scenarios

### Risk 3: Memory Constraints
**Mitigation:** Monitor VRAM in benchmark
**Fallback:** Share GPU with LLM via memory management, or use CPU

### Risk 4: Streaming Limitations
**Mitigation:** Explicitly test vLLM streaming mode
**Fallback:** Use batch mode for non-real-time scenarios

## Success Criteria

**Go/No-Go Decision:**
- [ ] Qwen3-ASR loads successfully on GPU
- [ ] RTF < 1.0 for real-time capability
- [ ] CER/WER improves by >20% over faster-whisper
- [ ] No critical compatibility errors
- [ ] VRAM usage <4GB (sharing with LLM feasible)

**If all criteria met:** Proceed with integration
**If 3-4 criteria met:** Conditional integration with limitations documented
**If <3 criteria met:** Document findings, revisit when Qwen3-ASR matures

## Next Steps

### Immediate (User Action Required)

1. **Install Dependencies:**
   ```bash
   source ~/BestBox/activate.sh
   pip install jiwer soundfile datasets
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2
   pip install -U qwen-asr
   ```

2. **Run Smoke Test:**
   ```bash
   python scripts/test_qwen3_asr_compatibility.py
   ```

3. **If smoke test passes, run benchmark:**
   ```bash
   python scripts/benchmark_asr_models.py --quick  # 5 min
   # or
   python scripts/benchmark_asr_models.py          # 30 min
   ```

4. **Review Results:**
   - Check `docs/ASR_BENCHMARK_RESULTS.md`
   - Follow recommendation (integrate, partial, or wait)

### Follow-Up (If Tests Pass)

1. **Streaming Test:** Verify vLLM streaming mode works with LiveKit
2. **Integration:** Implement Qwen3 provider
3. **Testing:** E2E voice tests with real queries
4. **Documentation:** Update CLAUDE.md with Qwen3 configuration
5. **Deployment:** Roll out with feature flag (SPEECH_PROVIDER=qwen3)

### Follow-Up (If Tests Fail)

1. **Document Issues:** Save error logs and findings
2. **Report Compatibility:** Consider filing issue with Qwen3-ASR team
3. **Alternative:** Evaluate Whisper large-v3 or other models
4. **Revisit:** Check back when Qwen3-ASR adds official AMD GPU support

## References

- **Qwen3-ASR GitHub:** https://github.com/QwenLM/Qwen3-ASR
- **Model Weights:** https://huggingface.co/Qwen/Qwen3-ASR-0.6B
- **Benchmark Guide:** `docs/ASR_BENCHMARK_GUIDE.md`
- **Current ASR:** `services/speech/asr.py` (faster-whisper)

## Timeline Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Design | 1 hour | ✅ Complete |
| Smoke Test | 5-10 min | ⏳ Ready to run |
| Benchmark | 20-30 min | ⏳ Ready to run |
| Decision | 15 min | ⏳ After benchmark |
| Integration | 2-4 hours | ⏳ Conditional |
| Testing | 1 hour | ⏳ Conditional |

**Total:** 4-6 hours from start to production (if tests pass)

## Open Questions

1. **PyTorch ROCm Compatibility:** Will PyTorch 2.x with ROCm 6.2 wheels work on ROCm 7.2.0?
   - **Answer via:** Smoke test Phase 1

2. **Real-Time Performance:** Can Qwen3-ASR-0.6B achieve RTF < 1.0 on AMD Radeon 8060S?
   - **Answer via:** Benchmark Phase 2

3. **Streaming Quality:** Does vLLM streaming produce good interim transcripts?
   - **Answer via:** Phase 3 if tests pass

4. **Memory Sharing:** Can LLM (Qwen3-30B via llama.cpp/Vulkan) and Qwen3-ASR (PyTorch/ROCm) coexist?
   - **Answer via:** Integration testing

## Conclusion

This design provides a **low-risk, data-driven approach** to evaluating Qwen3-ASR:

1. ✅ **Test-first methodology** catches issues early
2. ✅ **Hybrid architecture** maintains system stability
3. ✅ **Clear decision criteria** based on benchmark data
4. ✅ **Gradual rollout** via provider selection

**Recommendation:** Proceed with compatibility test and benchmark. Integration decision after reviewing concrete performance data.
