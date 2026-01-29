#!/usr/bin/env bash
# Real-time monitoring of vLLM performance during inference

set -e

echo "🔍 vLLM Real-time Monitor"
echo "========================="
echo "Press Ctrl+C to stop"
echo ""

# Check if vLLM is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ vLLM server not running on port 8000"
    exit 1
fi

echo "✅ vLLM server detected"
echo ""

# Function to get metrics
get_metrics() {
    while true; do
        clear
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  vLLM + Qwen3-14B Performance Monitor"
        echo "  $(date '+%Y-%m-%d %H:%M:%S')"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""

        # GPU stats
        echo "🎮 GPU Status (ROCm):"
        echo "─────────────────────"
        rocm-smi --showuse --showmeminfo vram 2>/dev/null || echo "  ⚠️  ROCm SMI not available"
        echo ""

        # Docker container stats if running in Docker
        if docker ps --format '{{.Names}}' | grep -q vllm 2>/dev/null; then
            echo "🐳 Docker Stats:"
            echo "─────────────────────"
            docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep vllm
            echo ""
        fi

        # System resources
        echo "💻 System Resources:"
        echo "─────────────────────"
        free -h | grep -E "Mem:|Swap:"
        echo ""

        # CPU usage
        echo "⚙️  CPU Usage:"
        echo "─────────────────────"
        top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "  CPU Busy: " 100 - $1 "%"}'
        echo ""

        # vLLM specific metrics (if exposed)
        echo "📊 vLLM Metrics:"
        echo "─────────────────────"
        METRICS=$(curl -s http://localhost:8000/metrics 2>/dev/null || echo "")
        if [ -n "$METRICS" ]; then
            echo "$METRICS" | grep -E "vllm_(num_requests|queue_size|cache)" || echo "  No vLLM metrics available"
        else
            echo "  ⚠️  Metrics endpoint not available"
        fi
        echo ""

        echo "Press Ctrl+C to stop monitoring"

        sleep 2
    done
}

# Run monitoring
get_metrics
