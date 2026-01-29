#!/usr/bin/env python3
"""
vLLM Performance Benchmark for Qwen3-14B-Instruct on AMD Ryzen AI Max+ 395
Tests throughput, latency, and resource usage
"""

import time
import json
import requests
import subprocess
import statistics
from datetime import datetime
from typing import List, Dict, Any

# Configuration
VLLM_BASE_URL = "http://localhost:8000/v1"
MODEL_NAME = "Qwen/Qwen2.5-14B-Instruct"  # Will auto-detect from server if not found
RESULTS_FILE = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# Test scenarios
PROMPTS = {
    "short": "What is Python?",
    "medium": "Explain the concept of machine learning and provide three real-world examples of its applications.",
    "long": "Write a detailed technical explanation of how transformer neural networks work, including attention mechanisms, positional encoding, and the encoder-decoder architecture. Include code examples in Python.",
    "code": "Write a Python class that implements a binary search tree with insert, search, and delete operations. Include proper error handling and docstrings."
}

MAX_TOKENS = {
    "short": 100,
    "medium": 300,
    "long": 800,
    "code": 500
}


def get_gpu_stats() -> Dict[str, Any]:
    """Get current GPU stats using rocm-smi"""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}
    except Exception as e:
        print(f"Warning: Could not get GPU stats: {e}")
        return {}


def check_vllm_health() -> bool:
    """Check if vLLM server is running"""
    try:
        response = requests.get(f"{VLLM_BASE_URL.replace('/v1', '')}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def run_completion_test(prompt: str, max_tokens: int, temperature: float = 0.7) -> Dict[str, Any]:
    """Run a single completion test and measure metrics"""

    # Get GPU stats before
    gpu_before = get_gpu_stats()

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False
    }

    start_time = time.time()

    try:
        response = requests.post(
            f"{VLLM_BASE_URL}/chat/completions",
            json=payload,
            timeout=120
        )

        end_time = time.time()

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }

        result = response.json()
        total_time = end_time - start_time

        # Extract metrics
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Get GPU stats after
        gpu_after = get_gpu_stats()

        return {
            "success": True,
            "total_time_seconds": total_time,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tokens_per_second": completion_tokens / total_time if total_time > 0 else 0,
            "time_per_token_ms": (total_time * 1000) / completion_tokens if completion_tokens > 0 else 0,
            "response_text": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "gpu_before": gpu_before,
            "gpu_after": gpu_after
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_streaming_test(prompt: str, max_tokens: int) -> Dict[str, Any]:
    """Test streaming performance (TTFT - Time To First Token)"""

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": True
    }

    start_time = time.time()
    first_token_time = None
    tokens_received = 0

    try:
        response = requests.post(
            f"{VLLM_BASE_URL}/chat/completions",
            json=payload,
            stream=True,
            timeout=120
        )

        for line in response.iter_lines():
            if not line:
                continue

            if line.startswith(b"data: "):
                data_str = line[6:].decode('utf-8')

                if data_str.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    if first_token_time is None:
                        first_token_time = time.time()

                    if chunk.get("choices", [{}])[0].get("delta", {}).get("content"):
                        tokens_received += 1

                except json.JSONDecodeError:
                    continue

        end_time = time.time()

        ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
        total_time = end_time - start_time

        return {
            "success": True,
            "ttft_ms": ttft,
            "total_time_seconds": total_time,
            "tokens_received": tokens_received,
            "tokens_per_second": tokens_received / total_time if total_time > 0 else 0
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_benchmark_suite():
    """Run complete benchmark suite"""

    print("=" * 60)
    print("vLLM + Qwen3-14B-Instruct Performance Benchmark")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"Hardware: AMD Ryzen AI Max+ 395 (gfx1151)")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Check if vLLM is running
    if not check_vllm_health():
        print("\n❌ Error: vLLM server is not running on port 8000")
        print("Please start it with: ./scripts/run_vllm_strix.sh")
        return

    print("\n✅ vLLM server is running\n")

    results = {
        "metadata": {
            "model": MODEL_NAME,
            "hardware": "AMD Ryzen AI Max+ 395 (gfx1151)",
            "timestamp": datetime.now().isoformat(),
            "vllm_base_url": VLLM_BASE_URL
        },
        "completion_tests": {},
        "streaming_tests": {},
        "summary": {}
    }

    # Run completion tests
    print("\n📊 Running Completion Tests (Non-streaming)")
    print("-" * 60)

    all_tps = []

    for test_name, prompt in PROMPTS.items():
        print(f"\n🔹 Test: {test_name.upper()}")
        print(f"   Prompt: {prompt[:50]}...")
        print(f"   Max tokens: {MAX_TOKENS[test_name]}")

        test_result = run_completion_test(prompt, MAX_TOKENS[test_name])

        if test_result["success"]:
            print(f"   ✅ Total time: {test_result['total_time_seconds']:.2f}s")
            print(f"   📈 Tokens/sec: {test_result['tokens_per_second']:.2f}")
            print(f"   ⏱️  Time/token: {test_result['time_per_token_ms']:.2f}ms")
            print(f"   📝 Completion tokens: {test_result['completion_tokens']}")

            all_tps.append(test_result['tokens_per_second'])
        else:
            print(f"   ❌ Error: {test_result.get('error', 'Unknown error')}")

        results["completion_tests"][test_name] = test_result
        time.sleep(1)  # Brief pause between tests

    # Run streaming tests (TTFT)
    print("\n\n📊 Running Streaming Tests (TTFT)")
    print("-" * 60)

    all_ttft = []

    for test_name, prompt in PROMPTS.items():
        print(f"\n🔹 Test: {test_name.upper()} (streaming)")

        stream_result = run_streaming_test(prompt, MAX_TOKENS[test_name])

        if stream_result["success"]:
            print(f"   ✅ TTFT: {stream_result['ttft_ms']:.2f}ms")
            print(f"   📈 Tokens/sec: {stream_result['tokens_per_second']:.2f}")

            all_ttft.append(stream_result['ttft_ms'])
        else:
            print(f"   ❌ Error: {stream_result.get('error', 'Unknown error')}")

        results["streaming_tests"][test_name] = stream_result
        time.sleep(1)

    # Calculate summary statistics
    if all_tps:
        results["summary"]["avg_tokens_per_second"] = statistics.mean(all_tps)
        results["summary"]["median_tokens_per_second"] = statistics.median(all_tps)
        results["summary"]["min_tokens_per_second"] = min(all_tps)
        results["summary"]["max_tokens_per_second"] = max(all_tps)

    if all_ttft:
        results["summary"]["avg_ttft_ms"] = statistics.mean(all_ttft)
        results["summary"]["median_ttft_ms"] = statistics.median(all_ttft)
        results["summary"]["min_ttft_ms"] = min(all_ttft)
        results["summary"]["max_ttft_ms"] = max(all_ttft)

    # Print summary
    print("\n\n" + "=" * 60)
    print("📈 BENCHMARK SUMMARY")
    print("=" * 60)

    if all_tps:
        print(f"\n🚀 Throughput (tokens/second):")
        print(f"   Average: {results['summary']['avg_tokens_per_second']:.2f}")
        print(f"   Median:  {results['summary']['median_tokens_per_second']:.2f}")
        print(f"   Range:   {results['summary']['min_tokens_per_second']:.2f} - {results['summary']['max_tokens_per_second']:.2f}")

    if all_ttft:
        print(f"\n⚡ Time To First Token (ms):")
        print(f"   Average: {results['summary']['avg_ttft_ms']:.2f}")
        print(f"   Median:  {results['summary']['median_ttft_ms']:.2f}")
        print(f"   Range:   {results['summary']['min_ttft_ms']:.2f} - {results['summary']['max_ttft_ms']:.2f}")

    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Full results saved to: {RESULTS_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_benchmark_suite()
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
