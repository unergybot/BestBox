#!/usr/bin/env bash
# Monitor vLLM health and performance

while true; do
  clear
  echo "=== vLLM Health Monitor ==="
  echo "Time: $(date)"
  echo ""

  # Container status
  echo "Container Status:"
  docker-compose ps vllm | tail -1
  echo ""

  # Health endpoint
  echo "Health Check:"
  curl -s http://localhost:8001/health 2>/dev/null | jq -r '.status // "UNHEALTHY"' || echo "UNREACHABLE"
  echo ""

  # GPU stats
  echo "GPU Utilization:"
  docker exec vllm-server rocm-smi --showuse 2>/dev/null | grep "GPU\[0\]" || echo "N/A"
  echo ""

  # Memory
  echo "VRAM Usage:"
  docker exec vllm-server rocm-smi --showmeminfo vram 2>/dev/null | grep "GPU\[0\]" || echo "N/A"
  echo ""

  # Request count (from logs)
  echo "Recent Requests (last minute):"
  docker-compose logs --since 1m vllm 2>/dev/null | grep -c "POST /v1/chat/completions" || echo "0"
  echo ""

  # Errors
  echo "Recent Errors:"
  docker-compose logs --since 5m vllm 2>/dev/null | grep -i error | tail -3 || echo "None"

  sleep 5
done
