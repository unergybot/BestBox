#!/usr/bin/env python3
"""vLLM Benchmark Script

Makes HTTP API calls to a running vLLM OpenAI-compatible server and reports
basic throughput/latency metrics.
"""

import requests
import time
import json
import concurrent.futures
import statistics
import sys
from collections import Counter
from typing import List, Dict, Any, Optional, Sequence
import argparse
import itertools
from datetime import datetime, timezone

class VLLMBenchmark:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "qwen3-30b",
        request_timeout_s: float = 600.0,
    ):
        self.base_url = base_url
        self.model = model
        self.results = []
        self.request_timeout_s = request_timeout_s
        self.session = requests.Session()

    def probe_server(self) -> Dict[str, Any]:
        """Probe server and list available model IDs from /v1/models."""
        try:
            response = self.session.get(f"{self.base_url}/v1/models", timeout=15)
        except Exception as e:
            return {
                "ok": False,
                "error": f"probe_error: {type(e).__name__}: {e}",
                "available_models": [],
            }

        if response.status_code != 200:
            return {
                "ok": False,
                "error": f"probe_http_{response.status_code}: {response.text}",
                "available_models": [],
            }

        try:
            payload = response.json()
            available = [item.get("id") for item in payload.get("data", []) if item.get("id")]
        except Exception as e:
            return {
                "ok": False,
                "error": f"probe_json_error: {type(e).__name__}: {e}",
                "available_models": [],
            }

        return {
            "ok": True,
            "available_models": available,
            "model_found": self.model in available,
        }

    @staticmethod
    def _failure_summary(failed: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        if not failed:
            return []
        counter = Counter((entry.get("error") or "unknown_error") for entry in failed)
        return [{"error": error, "count": count} for error, count in counter.most_common(limit)]

    @staticmethod
    def _percentile(values: List[float], p: float) -> float:
        if not values:
            raise ValueError("percentile() requires a non-empty list")
        if p <= 0:
            return min(values)
        if p >= 1:
            return max(values)
        values_sorted = sorted(values)
        idx = int(round(p * (len(values_sorted) - 1)))
        idx = max(0, min(idx, len(values_sorted) - 1))
        return values_sorted[idx]

    def warmup(self, num_requests: int, input_len: int, output_len: int) -> None:
        """Run warmup requests to stabilize compile/cache behavior"""
        if num_requests <= 0:
            return

        prompt = self.generate_prompt(input_len)
        for _ in range(num_requests):
            self.send_request(prompt, output_len)
    
    def generate_prompt(self, length: int) -> str:
        """Generate a prompt of approximately specified token length"""
        # Try to approximate tokens with 1 word ~= 1 token.
        # The server-reported usage tokens are the source of truth.
        if length <= 0:
            return ""
        return " ".join(["hello"] * length)
    
    def send_request(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Send a single request to vLLM server"""
        start_time = time.time()

        try:
            response = self.session.post(
                f"{self.base_url}/v1/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                    "stream": False,
                },
                timeout=self.request_timeout_s,
            )
        except Exception as e:
            end_time = time.time()
            return {
                "latency": end_time - start_time,
                "success": False,
                "error": f"request_error: {type(e).__name__}: {e}",
            }
        
        end_time = time.time()
        latency = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "latency": latency,
                "prompt_tokens": data["usage"]["prompt_tokens"],
                "completion_tokens": data["usage"]["completion_tokens"],
                "total_tokens": data["usage"]["total_tokens"],
                "success": True
            }
        else:
            error_text = response.text
            if len(error_text) > 400:
                error_text = error_text[:400] + "..."
            return {
                "latency": latency,
                "success": False,
                "error": f"http_{response.status_code}: {error_text}",
            }
    
    def benchmark_throughput(self, num_prompts: int, input_len: int, output_len: int,
                           max_concurrency: int = 32) -> Dict:
        """Benchmark throughput with multiple concurrent requests"""
        print(f"\n{'='*60}")
        print(f"Throughput Benchmark")
        print(f"{'='*60}")
        print(f"Configuration:")
        print(f"  - Number of prompts: {num_prompts}")
        print(f"  - Input length: {input_len} tokens")
        print(f"  - Output length: {output_len} tokens")
        print(f"  - Max concurrency: {max_concurrency}")
        print(f"  - Model: {self.model}")
        print(f"\nRunning benchmark...")
        
        prompts = [self.generate_prompt(input_len) for _ in range(num_prompts)]
        
        start_time = time.time()
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_prompt = {
                executor.submit(self.send_request, prompt, output_len): prompt 
                for prompt in prompts
            }
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_prompt)):
                result = future.result()
                results.append(result)
                if (i + 1) % 10 == 0:
                    print(f"  Completed {i + 1}/{num_prompts} requests...")
        
        total_time = time.time() - start_time
        
        # Calculate metrics
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        if not successful:
            print("ERROR: All requests failed!")
            return {
                "error": "All requests failed",
                "failure_summary": self._failure_summary(failed),
            }
        
        total_tokens = sum(r["total_tokens"] for r in successful)
        total_completion_tokens = sum(r["completion_tokens"] for r in successful)
        
        latencies = [r["latency"] for r in successful]

        metrics: Dict[str, Any] = {
            "total_requests": num_prompts,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "total_time_seconds": total_time,
            # Keep both: attempted (all) and achieved (successful)
            "attempted_requests_per_second": (num_prompts / total_time) if total_time > 0 else 0.0,
            "requests_per_second": (len(successful) / total_time) if total_time > 0 else 0.0,
            "tokens_per_second": (total_tokens / total_time) if total_time > 0 else 0.0,
            "output_tokens_per_second": (total_completion_tokens / total_time) if total_time > 0 else 0.0,
            "avg_latency_seconds": statistics.mean(latencies),
            "p50_latency": statistics.median(latencies),
            "p90_latency": self._percentile(latencies, 0.90),
            "p99_latency": self._percentile(latencies, 0.99),
            "total_prompt_tokens": sum(r["prompt_tokens"] for r in successful),
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "failure_summary": self._failure_summary(failed),
        }

        if failed:
            print("  Failure summary:")
            for item in metrics["failure_summary"]:
                print(f"    - {item['count']}x {item['error']}")
        
        return metrics
    
    def benchmark_latency(self, num_requests: int = 100, input_len: int = 512,
                         output_len: int = 128) -> Dict:
        """Benchmark latency with sequential requests"""
        print(f"\n{'='*60}")
        print(f"Latency Benchmark")
        print(f"{'='*60}")
        print(f"Configuration:")
        print(f"  - Number of requests: {num_requests}")
        print(f"  - Input length: {input_len} tokens")
        print(f"  - Output length: {output_len} tokens")
        print(f"  - Model: {self.model}")
        print(f"\nRunning benchmark...")
        
        prompt = self.generate_prompt(input_len)
        latencies: List[float] = []
        failed: List[Dict[str, Any]] = []
        
        for i in range(num_requests):
            result = self.send_request(prompt, output_len)
            if result["success"]:
                latencies.append(result["latency"])
            else:
                failed.append(result)
            if (i + 1) % 20 == 0:
                print(f"  Completed {i + 1}/{num_requests} requests...")
        
        if not latencies:
            print("ERROR: All requests failed!")
            return {
                "error": "All requests failed",
                "failure_summary": self._failure_summary(failed),
            }
        
        metrics = {
            "num_requests": num_requests,
            "input_length": input_len,
            "output_length": output_len,
            "successful_requests": len(latencies),
            "failed_requests": len(failed),
            "avg_latency_ms": statistics.mean(latencies) * 1000,
            "p50_latency_ms": statistics.median(latencies) * 1000,
            "p90_latency_ms": self._percentile(latencies, 0.90) * 1000,
            "p99_latency_ms": self._percentile(latencies, 0.99) * 1000,
            "min_latency_ms": min(latencies) * 1000,
            "max_latency_ms": max(latencies) * 1000,
            "failure_summary": self._failure_summary(failed),
        }

        if failed:
            print("  Failure summary:")
            for item in metrics["failure_summary"]:
                print(f"    - {item['count']}x {item['error']}")
        
        return metrics

    def sweep(
        self,
        input_lens: Sequence[int],
        output_lens: Sequence[int],
        concurrencies: Sequence[int],
        num_prompts: int,
        warmup_requests: int,
        run_latency: bool,
        latency_requests: int,
    ) -> Dict[str, Any]:
        """Run a grid of benchmarks and return a summary including best config."""
        started_at = datetime.now(timezone.utc).isoformat()
        experiments: List[Dict[str, Any]] = []

        for input_len, output_len, concurrency in itertools.product(input_lens, output_lens, concurrencies):
            config = {
                "input_len": int(input_len),
                "output_len": int(output_len),
                "concurrency": int(concurrency),
                "num_prompts": int(num_prompts),
                "warmup_requests": int(warmup_requests),
            }

            self.warmup(warmup_requests, int(input_len), min(int(output_len), 256))
            throughput = self.benchmark_throughput(
                num_prompts=num_prompts,
                input_len=int(input_len),
                output_len=int(output_len),
                max_concurrency=int(concurrency),
            )
            entry: Dict[str, Any] = {"config": config, "throughput": throughput}

            if run_latency:
                latency = self.benchmark_latency(
                    num_requests=int(latency_requests),
                    input_len=int(input_len),
                    output_len=min(int(output_len), 256),
                )
                entry["latency"] = latency

            experiments.append(entry)

        def score(item: Dict[str, Any]) -> float:
            tp = item.get("throughput") or {}
            if "output_tokens_per_second" in tp and isinstance(tp["output_tokens_per_second"], (int, float)):
                return float(tp["output_tokens_per_second"])
            return -1.0

        best = max(experiments, key=score) if experiments else None

        return {
            "started_at": started_at,
            "base_url": self.base_url,
            "model": self.model,
            "request_timeout_s": self.request_timeout_s,
            "experiments": experiments,
            "best": best,
        }
    
    def print_results(self, metrics: Dict, title: str = "Benchmark Results"):
        """Print formatted benchmark results"""
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="vLLM Benchmark Tool")
    parser.add_argument("--url", default="http://localhost:8000", help="vLLM server URL")
    parser.add_argument("--model", default="qwen3-30b", help="Model name")
    parser.add_argument("--benchmark", choices=["throughput", "latency", "all"], 
                       default="all", help="Benchmark type")
    parser.add_argument("--num-prompts", type=int, default=32, help="Number of prompts for throughput")
    parser.add_argument("--input-len", type=int, default=512, help="Input token length")
    parser.add_argument("--output-len", type=int, default=512, help="Output token length")
    parser.add_argument("--concurrency", type=int, default=32, help="Max concurrent requests")
    parser.add_argument("--warmup-requests", type=int, default=10, help="Warmup requests before benchmarking")
    parser.add_argument("--timeout", type=float, default=600.0, help="Per-request timeout (seconds)")
    parser.add_argument("--sweep", action="store_true", help="Run a parameter sweep instead of a single benchmark")
    parser.add_argument("--sweep-input-lens", default="128,256,512", help="Comma-separated input lengths")
    parser.add_argument("--sweep-output-lens", default="128,256,512", help="Comma-separated output lengths")
    parser.add_argument("--sweep-concurrency", default="1,2,4,8,16", help="Comma-separated concurrencies")
    parser.add_argument("--sweep-latency", action="store_true", help="Also run sequential latency for each sweep point")
    parser.add_argument("--sweep-latency-requests", type=int, default=6, help="Sequential requests per sweep point")
    parser.add_argument("--out", default="/tmp/vllm_benchmark_results.json", help="Path to write JSON results")
    
    args = parser.parse_args()
    
    benchmark = VLLMBenchmark(base_url=args.url, model=args.model, request_timeout_s=args.timeout)

    probe = benchmark.probe_server()
    if not probe.get("ok"):
        print(f"ERROR: Unable to query {args.url}/v1/models")
        print(f"Details: {probe.get('error', 'unknown error')}")
        sys.exit(2)

    available_models = probe.get("available_models", [])
    print(f"Discovered models: {available_models}")
    if args.model not in available_models:
        print(f"ERROR: requested model '{args.model}' not found on server.")
        print("Use --model with one of the discovered IDs above.")
        sys.exit(2)
    
    results: Dict[str, Any] = {}

    if args.sweep:
        def parse_int_list(s: str) -> List[int]:
            return [int(x.strip()) for x in s.split(",") if x.strip()]

        sweep_results = benchmark.sweep(
            input_lens=parse_int_list(args.sweep_input_lens),
            output_lens=parse_int_list(args.sweep_output_lens),
            concurrencies=parse_int_list(args.sweep_concurrency),
            num_prompts=int(args.num_prompts),
            warmup_requests=int(args.warmup_requests),
            run_latency=bool(args.sweep_latency),
            latency_requests=int(args.sweep_latency_requests),
        )
        results["sweep"] = sweep_results
    else:
        benchmark.warmup(args.warmup_requests, args.input_len, min(args.output_len, 256))
    
        if args.benchmark in ["throughput", "all"]:
            throughput_metrics = benchmark.benchmark_throughput(
                num_prompts=args.num_prompts,
                input_len=args.input_len,
                output_len=args.output_len,
                max_concurrency=args.concurrency,
            )
            benchmark.print_results(throughput_metrics, "Throughput Benchmark Results")
            results["throughput"] = throughput_metrics
        
        if args.benchmark in ["latency", "all"]:
            latency_metrics = benchmark.benchmark_latency(
                num_requests=min(args.num_prompts, 100),
                input_len=args.input_len,
                output_len=min(args.output_len, 256),
            )
            benchmark.print_results(latency_metrics, "Latency Benchmark Results")
            results["latency"] = latency_metrics
    
    # Save results to file
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {args.out}")


if __name__ == "__main__":
    main()
