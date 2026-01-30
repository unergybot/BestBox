# Qwen3-ASR Benchmark Guide

**Purpose:** Test Qwen3-ASR-0.6B compatibility and performance vs faster-whisper on your AMD GPU

## Prerequisites

### 1. Install Required Packages

```bash
# Activate BestBox environment
source ~/BestBox/activate.sh

# Install benchmark dependencies
pip install jiwer soundfile datasets torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

# Install Qwen3-ASR (will test if this works on AMD GPU)
pip install -U qwen-asr

# Optional: Install vLLM backend for faster inference
pip install -U qwen-asr[vllm]
```

### 2. Verify PyTorch ROCm Support

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

**Expected output:**
```
CUDA available: True
Device: AMD Radeon Graphics (or similar)
```

If CUDA is not available, the benchmark will still run on CPU (slower but functional).

## Running the Benchmark

### Quick Test (5 samples, ~5 minutes)

Fast validation to check if Qwen3-ASR works:

```bash
cd ~/BestBox
python scripts/benchmark_asr_models.py --quick
```

### Full Benchmark (20 samples, ~20-30 minutes)

Comprehensive accuracy and performance comparison:

```bash
python scripts/benchmark_asr_models.py
```

### GPU-Only Test

Skip CPU benchmarks (faster if you know GPU works):

```bash
python scripts/benchmark_asr_models.py --gpu-only
```

### CPU-Only Test

Skip GPU benchmarks (if GPU unavailable):

```bash
python scripts/benchmark_asr_models.py --cpu-only
```

## What Gets Tested

### Models
1. **faster-whisper tiny (CPU)** - Your current baseline
2. **Qwen3-ASR-0.6B (GPU)** - New model on AMD GPU with ROCm
3. **Qwen3-ASR-0.6B (CPU)** - Fallback mode

### Datasets
- **AISHELL-1** (Chinese Mandarin): 10-20 test samples
- **Common Voice** (English): 10-20 test samples

### Metrics
- **Accuracy**: CER (Chinese), WER (English)
- **Performance**: Transcription time, Real-Time Factor (RTF)
- **Resources**: RAM, VRAM usage
- **Reliability**: Success rate, error tracking

## Understanding Results

### Output Files

1. **`benchmark_results_asr_TIMESTAMP.json`** - Raw data for analysis
2. **`docs/ASR_BENCHMARK_RESULTS.md`** - Human-readable report with recommendations

### Key Metrics to Look At

**Real-Time Factor (RTF)**
- RTF < 1.0 = Faster than real-time (good for streaming)
- RTF = 1.0 = Processing matches audio duration
- RTF > 1.0 = Slower than real-time (may cause lag)

**Character/Word Error Rate**
- 0% = Perfect transcription
- < 5% = Excellent accuracy
- 5-15% = Good accuracy
- > 15% = Poor accuracy

**Success Rate**
- 100% = All samples transcribed successfully
- < 100% = Compatibility issues or errors

### Example Good Result

```
Qwen3-ASR-0.6B (GPU):
- RTF: 0.45 (faster than real-time)
- Chinese CER: 3.2% (excellent)
- English WER: 5.1% (good)
- Success Rate: 100%
- VRAM: 2.1GB
```

### Example Warning Signs

```
Qwen3-ASR-0.6B (GPU):
- RTF: 2.3 (slower than real-time - not suitable for streaming)
- Success Rate: 40% (compatibility issues!)
- Errors: "ROCm out of memory", "CUDA initialization failed"
```

## Troubleshooting

### Problem: "qwen-asr not found"

```bash
pip install -U qwen-asr
```

If installation fails, Qwen3-ASR may not support your environment yet.

### Problem: "torch.cuda not available"

Check PyTorch ROCm installation:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2
```

Note: You have ROCm 7.2.0 but PyTorch might only support up to ROCm 6.2. This is okay - PyTorch often works across ROCm versions.

### Problem: "Out of memory" errors

Try reducing batch size or use CPU mode:

```bash
python scripts/benchmark_asr_models.py --cpu-only
```

### Problem: "Failed to download datasets"

The script will fall back to dummy samples. Results won't reflect real accuracy, but will still test compatibility and performance.

### Problem: GPU detected but benchmark fails

This means Qwen3-ASR has compatibility issues with AMD GPU. The report will recommend:
- Sticking with faster-whisper
- Or implementing CPU-only Qwen3-ASR with performance trade-offs

## Next Steps After Benchmark

### If Results Look Good (RTF < 1.0, accuracy improved)

1. Review `docs/ASR_BENCHMARK_RESULTS.md` for recommendation
2. Proceed with integration design
3. Test streaming mode separately for LiveKit

### If GPU Has Issues (errors or slow)

1. Check error messages in report
2. Try CPU-only mode for accuracy comparison
3. Consider hybrid approach: Qwen3-ASR (CPU) for accuracy, faster-whisper (CPU) for speed

### If Qwen3-ASR Won't Install

Model may not be compatible with your environment yet. Recommendations:
- Wait for official ROCm 7.x support
- Try in Docker container with compatible PyTorch
- Stick with faster-whisper for now

## Quick Sanity Check

Before running full benchmark, test basic imports:

```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')

try:
    from qwen_asr import Qwen3ASRModel
    print('Qwen3-ASR: Installed ✓')
except ImportError:
    print('Qwen3-ASR: Not installed ✗')

try:
    from faster_whisper import WhisperModel
    print('faster-whisper: Installed ✓')
except ImportError:
    print('faster-whisper: Not installed ✗')
"
```

## Estimated Runtimes

| Mode | Samples | Est. Time | Purpose |
|------|---------|-----------|---------|
| Quick | 5 | 5-10 min | Compatibility check |
| Full | 20 | 20-30 min | Comprehensive comparison |
| GPU-only | 20 | 15-20 min | Skip slow CPU tests |
| CPU-only | 20 | 30-40 min | GPU unavailable |

## Support

If benchmark fails with unclear errors:
1. Save error output: `python scripts/benchmark_asr_models.py 2>&1 | tee benchmark_errors.log`
2. Check `benchmark_errors.log` for details
3. Share error log for troubleshooting
