#!/bin/bash
set -e

# Find existing vLLM process
VLLM_PID=$(pgrep -f "python3 -m vllm")

if [ -n "$VLLM_PID" ]; then
    echo "Stopping existing vLLM process (PID: $VLLM_PID)..."
    kill $VLLM_PID
    
    # Wait for it to exit
    while kill -0 $VLLM_PID 2>/dev/null; do
        echo "Waiting for process to exit..."
        sleep 1
    done
    echo "Process stopped."
fi

echo "Starting vLLM with tool support..."
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-4B-Instruct-2507 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 8192 \
    --dtype float16 \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --port 8001 > vllm.log 2>&1 &

echo "vLLM started in background. Logs: vllm.log"
echo "Monitoring logs for readiness..."
timeout 60 tail -f vllm.log | grep -m 1 "Application startup complete" || echo "Startup continuing in background..."
