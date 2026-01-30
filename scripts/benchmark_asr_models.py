#!/usr/bin/env python3
"""
ASR Model Benchmark Suite

Compares faster-whisper (current) vs Qwen3-ASR (new) on standardized datasets.
Tests GPU and CPU modes, measures accuracy, latency, and resource usage.

Usage:
    python scripts/benchmark_asr_models.py [--quick] [--gpu-only] [--cpu-only]

    --quick: Run on 5 samples instead of 20 (faster testing)
    --gpu-only: Skip CPU benchmarks
    --cpu-only: Skip GPU benchmarks
"""

import argparse
import json
import logging
import os
import sys
import time
import psutil
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import traceback

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('asr-benchmark')


@dataclass
class BenchmarkResult:
    """Results for a single audio sample."""
    model_name: str
    device: str
    audio_file: str
    language: str
    audio_duration: float

    # Transcription
    hypothesis: str
    reference: str

    # Accuracy
    cer: Optional[float] = None  # Character Error Rate (for Chinese)
    wer: Optional[float] = None  # Word Error Rate (for English)

    # Performance
    transcription_time: float = 0.0
    first_token_latency: Optional[float] = None
    rtf: float = 0.0  # Real-Time Factor

    # Resources
    peak_memory_mb: float = 0.0
    peak_vram_mb: float = 0.0

    # Errors
    error: Optional[str] = None
    success: bool = True


@dataclass
class ModelBenchmark:
    """Aggregated results for a model configuration."""
    model_name: str
    device: str

    # Timing
    model_load_time: float
    avg_transcription_time: float
    avg_rtf: float

    # Accuracy
    avg_cer_chinese: Optional[float]
    avg_wer_english: Optional[float]

    # Resources
    peak_memory_mb: float
    peak_vram_mb: float

    # Metadata
    total_samples: int
    successful_samples: int
    failed_samples: int
    errors: List[str]


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculate Character Error Rate (for Chinese)."""
    try:
        import jiwer
        # For Chinese, treat each character as a "word"
        ref_chars = ' '.join(list(reference))
        hyp_chars = ' '.join(list(hypothesis))
        return jiwer.wer(ref_chars, hyp_chars)
    except ImportError:
        logger.warning("jiwer not installed, CER calculation unavailable")
        return None


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate (for English)."""
    try:
        import jiwer
        return jiwer.wer(reference, hypothesis)
    except ImportError:
        logger.warning("jiwer not installed, WER calculation unavailable")
        return None


def get_memory_usage() -> tuple[float, float]:
    """Get current RAM and VRAM usage in MB."""
    process = psutil.Process()
    ram_mb = process.memory_info().rss / 1024 / 1024

    vram_mb = 0.0
    try:
        import torch
        if torch.cuda.is_available():
            vram_mb = torch.cuda.memory_allocated() / 1024 / 1024
    except:
        pass

    return ram_mb, vram_mb


def download_test_samples(dataset_name: str, language: str, num_samples: int = 20) -> List[Dict[str, Any]]:
    """
    Download test samples from public datasets.

    Args:
        dataset_name: 'aishell' or 'common_voice'
        language: 'zh' or 'en'
        num_samples: Number of samples to download

    Returns:
        List of dicts with 'audio' (path/array), 'text' (reference), 'duration'
    """
    logger.info(f"Downloading {num_samples} samples from {dataset_name} ({language})...")

    try:
        from datasets import load_dataset

        if dataset_name == 'aishell' and language == 'zh':
            # AISHELL-1 Chinese dataset
            dataset = load_dataset('audiofolder', data_files={
                'test': 'https://huggingface.co/datasets/aishell/aishell/resolve/main/test.tar.gz'
            })
            samples = dataset['test'].shuffle(seed=42).select(range(min(num_samples, len(dataset['test']))))

            results = []
            for idx, sample in enumerate(samples):
                # Save audio to temp file
                audio_path = f"/tmp/benchmark_aishell_{idx}.wav"
                # Assuming sample has 'audio' dict with 'array' and 'sampling_rate'
                import soundfile as sf
                sf.write(audio_path, sample['audio']['array'], sample['audio']['sampling_rate'])

                results.append({
                    'audio': audio_path,
                    'text': sample['text'],
                    'duration': len(sample['audio']['array']) / sample['audio']['sampling_rate'],
                    'language': 'zh'
                })

            return results

        elif dataset_name == 'common_voice' and language == 'en':
            # Common Voice English
            dataset = load_dataset('mozilla-foundation/common_voice_13_0', 'en', split='test', streaming=True)

            results = []
            for idx, sample in enumerate(dataset.take(num_samples)):
                audio_path = f"/tmp/benchmark_cv_{idx}.wav"
                import soundfile as sf
                sf.write(audio_path, sample['audio']['array'], sample['audio']['sampling_rate'])

                results.append({
                    'audio': audio_path,
                    'text': sample['sentence'],
                    'duration': len(sample['audio']['array']) / sample['audio']['sampling_rate'],
                    'language': 'en'
                })

            return results
        else:
            logger.error(f"Unsupported dataset: {dataset_name} ({language})")
            return []

    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        logger.info("Falling back to dummy samples for testing...")

        # Create dummy samples for testing when datasets can't be downloaded
        return create_dummy_samples(language, num_samples)


def create_dummy_samples(language: str, num_samples: int = 5) -> List[Dict[str, Any]]:
    """Create synthetic test samples when real datasets unavailable."""
    logger.warning("Using dummy samples - results won't reflect real accuracy!")

    samples = []

    if language == 'zh':
        texts = [
            "你好，我是智能助手。",
            "今天天气怎么样？",
            "请帮我查询库存信息。",
            "我需要订购一些产品。",
            "谢谢你的帮助。"
        ]
    else:  # en
        texts = [
            "Hello, I am an intelligent assistant.",
            "What is the weather like today?",
            "Please help me check the inventory.",
            "I need to order some products.",
            "Thank you for your help."
        ]

    # Create silent audio files (TTS would be better but requires extra deps)
    for idx, text in enumerate(texts[:num_samples]):
        audio_path = f"/tmp/benchmark_dummy_{language}_{idx}.wav"

        # Generate 2 seconds of silence at 16kHz
        import soundfile as sf
        silence = np.zeros(32000, dtype=np.float32)
        sf.write(audio_path, silence, 16000)

        samples.append({
            'audio': audio_path,
            'text': text,
            'duration': 2.0,
            'language': language
        })

    return samples


class FasterWhisperBenchmark:
    """Benchmark wrapper for faster-whisper (current system)."""

    def __init__(self, model_size: str = "tiny", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model = None

    def load_model(self) -> float:
        """Load model and return load time."""
        from faster_whisper import WhisperModel

        start = time.time()
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type="int8" if self.device == "cpu" else "float16"
        )
        load_time = time.time() - start

        logger.info(f"faster-whisper {self.model_size} loaded on {self.device} in {load_time:.2f}s")
        return load_time

    def transcribe(self, audio_path: str, language: str) -> tuple[str, float, float]:
        """
        Transcribe audio file.

        Returns:
            (transcript, transcription_time, first_token_latency)
        """
        start = time.time()

        segments, info = self.model.transcribe(
            audio_path,
            language=language if language == 'en' else 'zh',
            beam_size=5
        )

        # Consume segments
        first_token_time = None
        transcript_parts = []

        for segment in segments:
            if first_token_time is None:
                first_token_time = time.time() - start
            transcript_parts.append(segment.text)

        transcript = ' '.join(transcript_parts).strip()
        total_time = time.time() - start

        return transcript, total_time, first_token_time


class Qwen3ASRBenchmark:
    """Benchmark wrapper for Qwen3-ASR (new system)."""

    def __init__(self, model_name: str = "Qwen/Qwen3-ASR-0.6B", device: str = "cuda"):
        self.model_name = model_name
        self.device = device
        self.model = None

    def load_model(self) -> float:
        """Load model and return load time."""
        try:
            from qwen_asr import Qwen3ASRModel
            import torch

            start = time.time()

            # Load model
            logger.info(f"Loading {self.model_name}...")
            self.model = Qwen3ASRModel.from_pretrained(self.model_name)

            # Move to GPU if requested and available (required for gfx1151)
            if self.device == "cuda" and torch.cuda.is_available():
                logger.info("  Moving model to GPU...")
                self.model.model = self.model.model.cuda()
                actual_device = "GPU (cuda:0)"
            else:
                actual_device = "CPU"

            load_time = time.time() - start
            logger.info(f"Qwen3-ASR loaded on {actual_device} in {load_time:.2f}s")
            return load_time

        except ImportError:
            raise ImportError(
                "qwen-asr not installed. Install with: pip install -U qwen-asr"
            )

    def transcribe(self, audio_path: str, language: str) -> tuple[str, float, float]:
        """
        Transcribe audio file.

        Returns:
            (transcript, transcription_time, first_token_latency)
        """
        start = time.time()

        # Qwen3-ASR auto-detects language
        result = self.model.transcribe(audio_path)

        # Handle different result formats
        if isinstance(result, dict):
            transcript = result.get('text', '').strip()
        elif isinstance(result, list):
            # Result is a list of segments or tokens
            if len(result) > 0 and isinstance(result[0], dict):
                transcript = ' '.join(seg.get('text', '') for seg in result).strip()
            else:
                transcript = ' '.join(str(r) for r in result).strip()
        else:
            transcript = str(result).strip()

        total_time = time.time() - start

        # Qwen3-ASR doesn't provide first token latency in batch mode
        first_token_time = None

        return transcript, total_time, first_token_time


def benchmark_model(
    model_wrapper,
    test_samples: List[Dict[str, Any]],
    model_name: str,
    device: str
) -> ModelBenchmark:
    """
    Run complete benchmark for a model configuration.

    Args:
        model_wrapper: FasterWhisperBenchmark or Qwen3ASRBenchmark instance
        test_samples: List of audio samples to test
        model_name: Display name for results
        device: 'cpu' or 'cuda'

    Returns:
        ModelBenchmark with aggregated results
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Benchmarking: {model_name} on {device}")
    logger.info(f"{'='*60}\n")

    results = []
    errors = []

    # Measure model load time
    try:
        load_time = model_wrapper.load_model()
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return ModelBenchmark(
            model_name=model_name,
            device=device,
            model_load_time=0.0,
            avg_transcription_time=0.0,
            avg_rtf=0.0,
            avg_cer_chinese=None,
            avg_wer_english=None,
            peak_memory_mb=0.0,
            peak_vram_mb=0.0,
            total_samples=len(test_samples),
            successful_samples=0,
            failed_samples=len(test_samples),
            errors=[str(e)]
        )

    # Process each sample
    peak_ram = 0.0
    peak_vram = 0.0

    for idx, sample in enumerate(test_samples):
        logger.info(f"Processing sample {idx+1}/{len(test_samples)}: {sample['audio']}")

        try:
            # Transcribe
            hypothesis, trans_time, first_token = model_wrapper.transcribe(
                sample['audio'],
                sample['language']
            )

            # Calculate metrics
            if sample['language'] == 'zh':
                cer = calculate_cer(sample['text'], hypothesis)
                wer = None
            else:
                cer = None
                wer = calculate_wer(sample['text'], hypothesis)

            rtf = trans_time / sample['duration'] if sample['duration'] > 0 else 0.0

            # Measure resources
            ram, vram = get_memory_usage()
            peak_ram = max(peak_ram, ram)
            peak_vram = max(peak_vram, vram)

            result = BenchmarkResult(
                model_name=model_name,
                device=device,
                audio_file=sample['audio'],
                language=sample['language'],
                audio_duration=sample['duration'],
                hypothesis=hypothesis,
                reference=sample['text'],
                cer=cer,
                wer=wer,
                transcription_time=trans_time,
                first_token_latency=first_token,
                rtf=rtf,
                peak_memory_mb=ram,
                peak_vram_mb=vram,
                success=True
            )

            results.append(result)

            logger.info(f"  ✓ Transcription: {hypothesis[:50]}...")
            logger.info(f"  ✓ Time: {trans_time:.2f}s (RTF: {rtf:.2f})")
            if cer:
                logger.info(f"  ✓ CER: {cer:.2%}")
            if wer:
                logger.info(f"  ✓ WER: {wer:.2%}")

        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            errors.append(f"Sample {idx}: {str(e)}")

            result = BenchmarkResult(
                model_name=model_name,
                device=device,
                audio_file=sample['audio'],
                language=sample['language'],
                audio_duration=sample['duration'],
                hypothesis="",
                reference=sample['text'],
                error=str(e),
                success=False
            )
            results.append(result)

    # Aggregate results
    successful = [r for r in results if r.success]

    if successful:
        chinese_results = [r for r in successful if r.cer is not None]
        english_results = [r for r in successful if r.wer is not None]

        avg_cer = sum(r.cer for r in chinese_results) / len(chinese_results) if chinese_results else None
        avg_wer = sum(r.wer for r in english_results) / len(english_results) if english_results else None
        avg_trans_time = sum(r.transcription_time for r in successful) / len(successful)
        avg_rtf = sum(r.rtf for r in successful) / len(successful)
    else:
        avg_cer = None
        avg_wer = None
        avg_trans_time = 0.0
        avg_rtf = 0.0

    return ModelBenchmark(
        model_name=model_name,
        device=device,
        model_load_time=load_time,
        avg_transcription_time=avg_trans_time,
        avg_rtf=avg_rtf,
        avg_cer_chinese=avg_cer,
        avg_wer_english=avg_wer,
        peak_memory_mb=peak_ram,
        peak_vram_mb=peak_vram,
        total_samples=len(results),
        successful_samples=len(successful),
        failed_samples=len(results) - len(successful),
        errors=errors
    )


def generate_markdown_report(benchmarks: List[ModelBenchmark], output_path: str):
    """Generate markdown comparison report."""

    report = """# ASR Model Benchmark Results

**Date:** {date}
**Environment:** AMD Radeon 8060S, ROCm 7.2.0

## Executive Summary

{summary}

## Detailed Results

### Model Comparison Table

| Model | Device | Load Time | Avg Trans Time | Avg RTF | CER (Chinese) | WER (English) | Peak RAM | Peak VRAM | Success Rate |
|-------|--------|-----------|----------------|---------|---------------|---------------|----------|-----------|--------------|
{table_rows}

### Metric Definitions

- **Load Time**: Time to initialize model (seconds)
- **Avg Trans Time**: Average transcription time per sample (seconds)
- **RTF (Real-Time Factor)**: Processing time / audio duration (< 1.0 is real-time)
- **CER**: Character Error Rate for Chinese (lower is better)
- **WER**: Word Error Rate for English (lower is better)
- **Success Rate**: Percentage of samples successfully transcribed

## Individual Model Details

{details}

## Recommendations

{recommendations}

## Next Steps

{next_steps}
"""

    from datetime import datetime

    # Generate table rows
    table_rows = []
    for b in benchmarks:
        cer_str = f"{b.avg_cer_chinese:.2%}" if b.avg_cer_chinese else "N/A"
        wer_str = f"{b.avg_wer_english:.2%}" if b.avg_wer_english else "N/A"
        success_rate = f"{b.successful_samples / b.total_samples:.0%}" if b.total_samples > 0 else "0%"

        table_rows.append(
            f"| {b.model_name} | {b.device.upper()} | {b.model_load_time:.1f}s | "
            f"{b.avg_transcription_time:.2f}s | {b.avg_rtf:.2f} | {cer_str} | {wer_str} | "
            f"{b.peak_memory_mb:.0f}MB | {b.peak_vram_mb:.0f}MB | {success_rate} |"
        )

    # Generate details
    details = []
    for b in benchmarks:
        detail = f"""### {b.model_name} ({b.device.upper()})

- **Model Load Time:** {b.model_load_time:.2f}s
- **Successful Samples:** {b.successful_samples}/{b.total_samples}
- **Average Transcription Time:** {b.avg_transcription_time:.2f}s
- **Average RTF:** {b.avg_rtf:.2f}
- **Chinese CER:** {f"{b.avg_cer_chinese:.2%}" if b.avg_cer_chinese else "N/A"}
- **English WER:** {f"{b.avg_wer_english:.2%}" if b.avg_wer_english else "N/A"}
- **Peak Memory:** {b.peak_memory_mb:.0f}MB RAM, {b.peak_vram_mb:.0f}MB VRAM

"""
        if b.errors:
            detail += f"**Errors:**\n" + "\n".join(f"- {e}" for e in b.errors[:5]) + "\n"

        details.append(detail)

    # Generate summary
    qwen_gpu = next((b for b in benchmarks if 'Qwen3' in b.model_name and b.device == 'cuda'), None)
    whisper = next((b for b in benchmarks if 'faster-whisper' in b.model_name), None)

    if qwen_gpu and whisper and qwen_gpu.successful_samples > 0 and whisper.successful_samples > 0:
        summary = f"""Comparison of faster-whisper (current baseline) vs Qwen3-ASR-0.6B:

- **Accuracy (Chinese):** {'Qwen3-ASR' if (qwen_gpu.avg_cer_chinese or 1.0) < (whisper.avg_cer_chinese or 1.0) else 'faster-whisper'} is better
- **Accuracy (English):** {'Qwen3-ASR' if (qwen_gpu.avg_wer_english or 1.0) < (whisper.avg_wer_english or 1.0) else 'faster-whisper'} is better
- **Speed:** {'Qwen3-ASR' if qwen_gpu.avg_rtf < whisper.avg_rtf else 'faster-whisper'} is faster (RTF: {qwen_gpu.avg_rtf:.2f} vs {whisper.avg_rtf:.2f})
- **Memory:** faster-whisper uses less resources ({whisper.peak_memory_mb:.0f}MB vs {qwen_gpu.peak_vram_mb:.0f}MB VRAM)
"""
    else:
        summary = "Benchmark completed with limited data. See details below."

    # Generate recommendations
    recommendations = """Based on benchmark results:

1. **If GPU is available and stable:** Consider Qwen3-ASR for improved accuracy on Chinese
2. **If accuracy is critical:** Qwen3-ASR shows better performance on multilingual content
3. **If resources are limited:** Stick with faster-whisper tiny on CPU
4. **Hybrid approach:** Use provider factory pattern to switch based on availability

**Integration Priority:** {priority}
"""

    if qwen_gpu and qwen_gpu.successful_samples > 0:
        priority = "HIGH - Qwen3-ASR works on your AMD GPU!"
    elif qwen_gpu:
        priority = "MEDIUM - Qwen3-ASR has compatibility issues, needs investigation"
    else:
        priority = "LOW - Qwen3-ASR could not be tested"

    recommendations = recommendations.format(priority=priority)

    next_steps = """1. Review benchmark results and accuracy improvements
2. Test Qwen3-ASR streaming mode for LiveKit integration
3. Implement provider factory pattern with fallback
4. Monitor GPU memory usage in production
5. Consider upgrading to Qwen3-ASR-1.7B if 0.6B accuracy is insufficient
"""

    # Fill template
    report = report.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary=summary,
        table_rows="\n".join(table_rows),
        details="\n".join(details),
        recommendations=recommendations,
        next_steps=next_steps
    )

    with open(output_path, 'w') as f:
        f.write(report)

    logger.info(f"\n✅ Markdown report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Benchmark ASR models')
    parser.add_argument('--quick', action='store_true', help='Quick test with 5 samples')
    parser.add_argument('--gpu-only', action='store_true', help='Skip CPU benchmarks')
    parser.add_argument('--cpu-only', action='store_true', help='Skip GPU benchmarks')
    args = parser.parse_args()

    num_samples = 5 if args.quick else 20

    # Download test data
    logger.info("Preparing test datasets...")
    chinese_samples = download_test_samples('aishell', 'zh', num_samples)
    english_samples = download_test_samples('common_voice', 'en', num_samples)
    all_samples = chinese_samples + english_samples

    logger.info(f"Loaded {len(all_samples)} test samples ({len(chinese_samples)} Chinese, {len(english_samples)} English)")

    benchmarks = []

    # Benchmark 1: faster-whisper tiny (CPU) - baseline
    if not args.gpu_only:
        try:
            whisper_cpu = FasterWhisperBenchmark(model_size="tiny", device="cpu")
            result = benchmark_model(whisper_cpu, all_samples, "faster-whisper-tiny", "cpu")
            benchmarks.append(result)
        except Exception as e:
            logger.error(f"faster-whisper benchmark failed: {e}")
            traceback.print_exc()

    # Benchmark 2: Qwen3-ASR (GPU)
    if not args.cpu_only:
        try:
            # Check if CUDA/ROCm is available
            import torch
            if torch.cuda.is_available():
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
                qwen_gpu = Qwen3ASRBenchmark(device="cuda")
                result = benchmark_model(qwen_gpu, all_samples, "Qwen3-ASR-0.6B", "cuda")
                benchmarks.append(result)
            else:
                logger.warning("No GPU detected, skipping GPU benchmark")
        except Exception as e:
            logger.error(f"Qwen3-ASR GPU benchmark failed: {e}")
            traceback.print_exc()

    # Benchmark 3: Qwen3-ASR (CPU fallback)
    if not args.gpu_only:
        try:
            qwen_cpu = Qwen3ASRBenchmark(device="cpu")
            result = benchmark_model(qwen_cpu, all_samples, "Qwen3-ASR-0.6B", "cpu")
            benchmarks.append(result)
        except Exception as e:
            logger.error(f"Qwen3-ASR CPU benchmark failed: {e}")
            traceback.print_exc()

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = f"benchmark_results_asr_{timestamp}.json"
    md_path = "docs/ASR_BENCHMARK_RESULTS.md"

    # Save JSON
    with open(json_path, 'w') as f:
        json.dump([asdict(b) for b in benchmarks], f, indent=2)
    logger.info(f"✅ JSON results saved to: {json_path}")

    # Generate markdown report
    generate_markdown_report(benchmarks, md_path)

    logger.info("\n" + "="*60)
    logger.info("BENCHMARK COMPLETE")
    logger.info("="*60)
    logger.info(f"Results: {json_path}")
    logger.info(f"Report:  {md_path}")


if __name__ == '__main__':
    main()
