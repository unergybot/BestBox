# vLLM on ROCm (Strix Halo/gfx1151) - Issue Report

## Context
We are attempting to build and run vLLM on an AMD Strix Halo (gfx1151) device using Docker.

**Environment:**
- **Base Image:** `rocm/pytorch:latest` (Ubuntu 24.04, Python 3.12, PyTorch 2.9.1+rocm7.2)
- **Codebase:** vLLM 0.14.0rc2 (Local source provided in `third_party/vllm`)
- **GPU:** AMD Strix Halo (gfx1151)
- **Model:** `Qwen2.5-14B-Instruct-Q4_K_M.gguf` (GGUF format)

## Successful Steps (Fixes Applied)
1.  **Toolchain Fix**: Switched to `rocm/pytorch:latest` to resolve "Broken toolchain" errors present in older images.
2.  **Device Detection Patch**: The container lacks `amdsmi`. We patched `vllm/platforms/__init__.py` to use `torch.version.hip` for detection:
    ```python
    if hasattr(torch.version, "hip") and torch.version.hip:
        return "vllm.platforms.rocm.RocmPlatform"
    ```
3.  **GGUF Configuration**: 
    - Added `--dtype float16` (GGUF + bfloat16 is unsupported/unstable).
    - Added `--tokenizer "Qwen/Qwen2.5-14B-Instruct"` to resolve safetensor repo lookup errors.

## Current Critical Issue
The server starts, validates configs, and begins initialization. However, it crashes with `RuntimeError: Engine core initialization failed` when launching the engine core.

**Traceback:**
```text
(APIServer pid=1) INFO 01-24 15:14:11 [vllm.py:618] Asynchronous scheduling is enabled.
(EngineCore_DP0 pid=180) INFO 01-24 15:14:23 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://172.17.0.2:34343 backend=nccl
(EngineCore_DP0 pid=180) INFO 01-24 15:14:23 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
(APIServer pid=1) Traceback (most recent call last):
...
(APIServer pid=1)   File "/opt/venv/lib/python3.12/site-packages/vllm.../vllm/v1/engine/core_client.py", line 479, in __init__
(APIServer pid=1)     with launch_core_engines(vllm_config, executor_class, log_stats) as (
...
(APIServer pid=1)   File "/opt/venv/lib/python3.12/site-packages/vllm.../vllm/v1/engine/utils.py", line 977, in wait_for_engine_startup
(APIServer pid=1)     raise RuntimeError(
(APIServer pid=1) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
```

## Suspected Causes
1.  **Version Mismatch**: Running vLLM `0.14.0` (older RC) on `ROCm 7.2` / `PyTorch 2.9` (bleeding edge) might have kernel incompatibilities, especially with the `EngineCore` multiprocessing launch.
2.  **Source vs Installed Package**: We are compiling from source (`setup.py install`) but running on a very new OS/Python version combination.
3.  **GGUF Support**: GGUF support in vLLM 0.14 might be experimental or broken on ROCm backends.

## Request for Help
- Is vLLM 0.14 compatible with ROCm 7.x/PyTorch 2.9?
- Are there known issues with `EngineCore` initialization on single-GPU ROCm setups using `nccl` backend?
- Should we try a newer vLLM version or a specific branch for Strix Halo?
