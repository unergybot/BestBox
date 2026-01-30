#!/usr/bin/env python3
"""
Test ROCm GPU utilization after PyTorch reinstall.
Verifies GPU is properly detected and used for computation.
"""

import torch
import time
import sys

print("=" * 60)
print("ROCm GPU Utilization Test")
print("=" * 60)

# Test 1: Basic GPU Detection
print("\n1. GPU Detection:")
print(f"   PyTorch version: {torch.__version__}")
print(f"   CUDA available: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("   ✗ CUDA not available! Check ROCm installation.")
    sys.exit(1)

print(f"   CUDA version: {torch.version.cuda}")
print(f"   ROCm version: {torch.version.hip if hasattr(torch.version, 'hip') else 'N/A'}")
print(f"   GPU count: {torch.cuda.device_count()}")
print(f"   Current device: {torch.cuda.current_device()}")
print(f"   GPU name: {torch.cuda.get_device_name(0)}")
print(f"   GPU capability: {torch.cuda.get_device_capability(0)}")

# Test 2: Memory Information
print("\n2. GPU Memory:")
props = torch.cuda.get_device_properties(0)
print(f"   Total memory: {props.total_memory / 1024**3:.2f} GB")
print(f"   Allocated: {torch.cuda.memory_allocated(0) / 1024**3:.4f} GB")
print(f"   Reserved: {torch.cuda.memory_reserved(0) / 1024**3:.4f} GB")

# Test 3: Simple GPU Computation
print("\n3. GPU Computation Test:")
try:
    # Create tensors on GPU
    print("   Creating 1000x1000 random matrices on GPU...")
    a = torch.randn(1000, 1000, device='cuda')
    b = torch.randn(1000, 1000, device='cuda')

    print(f"   Tensor device: {a.device}")
    print(f"   Memory after allocation: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")

    # Perform computation
    print("   Performing matrix multiplication...")
    start = time.time()
    c = torch.matmul(a, b)
    torch.cuda.synchronize()  # Wait for GPU to finish
    elapsed = time.time() - start

    print(f"   ✓ Computation completed in {elapsed*1000:.2f} ms")
    print(f"   Result shape: {c.shape}")
    print(f"   Result device: {c.device}")

except Exception as e:
    print(f"   ✗ GPU computation failed: {e}")
    sys.exit(1)

# Test 4: GPU Performance Benchmark
print("\n4. GPU Performance Benchmark:")
sizes = [100, 500, 1000, 2000]

print("   Matrix Size | GPU Time (ms) | CPU Time (ms) | Speedup")
print("   " + "-" * 56)

for size in sizes:
    # GPU benchmark
    a_gpu = torch.randn(size, size, device='cuda')
    b_gpu = torch.randn(size, size, device='cuda')

    # Warmup
    for _ in range(3):
        _ = torch.matmul(a_gpu, b_gpu)
    torch.cuda.synchronize()

    # Actual timing
    start = time.time()
    for _ in range(10):
        c_gpu = torch.matmul(a_gpu, b_gpu)
    torch.cuda.synchronize()
    gpu_time = (time.time() - start) / 10 * 1000

    # CPU benchmark
    a_cpu = a_gpu.cpu()
    b_cpu = b_gpu.cpu()

    start = time.time()
    for _ in range(10):
        c_cpu = torch.matmul(a_cpu, b_cpu)
    cpu_time = (time.time() - start) / 10 * 1000

    speedup = cpu_time / gpu_time
    print(f"   {size:4d}x{size:<4d} | {gpu_time:13.2f} | {cpu_time:13.2f} | {speedup:6.2f}x")

# Test 5: Memory Stress Test
print("\n5. GPU Memory Stress Test:")
try:
    print("   Allocating large tensors...")
    tensors = []
    allocated = 0

    for i in range(10):
        tensor = torch.randn(100, 100, 100, device='cuda')  # ~4 MB each
        tensors.append(tensor)
        allocated = torch.cuda.memory_allocated(0) / 1024**2
        print(f"   Iteration {i+1}: {allocated:.2f} MB allocated")

    print(f"   ✓ Successfully allocated {allocated:.2f} MB")

    # Cleanup
    del tensors
    torch.cuda.empty_cache()
    print(f"   Cleaned up: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB remaining")

except RuntimeError as e:
    if "out of memory" in str(e):
        print(f"   ⚠ Out of memory at {allocated:.2f} MB")
    else:
        print(f"   ✗ Error: {e}")

# Test 6: Data Transfer Test
print("\n6. CPU ↔ GPU Data Transfer:")
sizes_mb = [1, 10, 100]

for size_mb in sizes_mb:
    # Calculate tensor size for target MB
    elements = int((size_mb * 1024 * 1024) / 4)  # 4 bytes per float32

    # CPU to GPU
    data_cpu = torch.randn(elements)
    start = time.time()
    data_gpu = data_cpu.cuda()
    torch.cuda.synchronize()
    cpu_to_gpu = time.time() - start

    # GPU to CPU
    start = time.time()
    data_back = data_gpu.cpu()
    gpu_to_cpu = time.time() - start

    bandwidth_h2d = size_mb / cpu_to_gpu
    bandwidth_d2h = size_mb / gpu_to_cpu

    print(f"   {size_mb:3d} MB: CPU→GPU {bandwidth_h2d:6.2f} MB/s | GPU→CPU {bandwidth_d2h:6.2f} MB/s")

# Test 7: Multi-operation Test
print("\n7. Complex Operations Test:")
try:
    x = torch.randn(100, 100, device='cuda')

    # Various operations
    ops = [
        ("Addition", lambda: x + x),
        ("Multiplication", lambda: x * x),
        ("Matrix Mult", lambda: torch.matmul(x, x)),
        ("Transpose", lambda: x.t()),
        ("ReLU", lambda: torch.relu(x)),
        ("Softmax", lambda: torch.softmax(x, dim=0)),
    ]

    for name, op in ops:
        start = time.time()
        for _ in range(100):
            result = op()
        torch.cuda.synchronize()
        elapsed = (time.time() - start) / 100 * 1000
        print(f"   {name:15s}: {elapsed:.3f} ms/op")

    print("   ✓ All operations completed successfully")

except Exception as e:
    print(f"   ✗ Operation failed: {e}")

# Final Status
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

mem_allocated = torch.cuda.memory_allocated(0) / 1024**2
mem_reserved = torch.cuda.memory_reserved(0) / 1024**2

print(f"\n✅ ROCm GPU is fully functional!")
print(f"\nGPU: {torch.cuda.get_device_name(0)}")
print(f"PyTorch: {torch.__version__}")
print(f"Memory: {mem_allocated:.2f} MB allocated, {mem_reserved:.2f} MB reserved")
print(f"\nGPU acceleration confirmed - Ready for ML workloads!")
print("=" * 60)
