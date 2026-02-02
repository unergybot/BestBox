#!/bin/bash
# Start the BestBox Speech-to-Speech Gateway
#
# This script starts the S2S WebSocket server that provides:
# - ASR (faster-whisper) for speech recognition
# - TTS (XTTS v2) for speech synthesis
# - WebSocket endpoint for real-time streaming
#
# Prerequisites:
#   - Python 3.10+
#   - CUDA/ROCm for GPU acceleration
#   - faster-whisper, TTS, webrtcvad installed
#
# Usage:
#   ./scripts/start-s2s.sh [--port PORT] [--host HOST]
#
# Environment variables:
#   S2S_HOST        - Bind address (default: 0.0.0.0)
#   S2S_PORT        - Server port (default: 8765)
#   ASR_MODEL       - Whisper model size (default: large-v3)
#   ASR_DEVICE      - Device for ASR (default: cuda)
#   ASR_LANGUAGE    - Recognition language (default: zh)
#   TTS_MODEL       - TTS model (default: xtts_v2)
#   TTS_GPU         - Use GPU for TTS (default: true)
#   S2S_ENABLE_TTS  - Enable TTS synthesis (default: false, set to 'true' to enable)

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Default configuration
export S2S_HOST="${S2S_HOST:-0.0.0.0}"

# IMPORTANT:
# The frontend defaults to ws://localhost:8765/ws/s2s.
# Avoid accidental port drift from inherited shell env vars by using BESTBOX_S2S_PORT.
export S2S_PORT="${BESTBOX_S2S_PORT:-8765}"
export ASR_MODEL="${ASR_MODEL:-Systran/faster-distil-whisper-large-v3}"
export ASR_DEVICE="cpu"
export ASR_LANGUAGE="${ASR_LANGUAGE:-zh}"
export TTS_MODEL="${TTS_MODEL:-piper}"
export TTS_GPU="${TTS_GPU:-false}"
export TTS_LANGUAGE="${TTS_LANGUAGE:-zh-cn}"
export S2S_ENABLE_TTS="${S2S_ENABLE_TTS:-true}"  # Enabled by default

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            export S2S_PORT="$2"
            shift 2
            ;;
        --host)
            export S2S_HOST="$2"
            shift 2
            ;;
        --model)
            export ASR_MODEL="$2"
            shift 2
            ;;
        --language)
            export ASR_LANGUAGE="$2"
            shift 2
            ;;
        --cpu)
            export ASR_DEVICE="cpu"
            export TTS_GPU="false"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT      Server port (default: 8765)"
            echo "  --host HOST      Bind address (default: 0.0.0.0)"
            echo "  --model MODEL    Whisper model (default: large-v3)"
            echo "  --language LANG  Recognition language (default: zh)"
            echo "  --cpu            Run on CPU (slower)"
            echo "  --help           Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}  BestBox S2S Gateway Launcher${NC}"
echo -e "${GREEN}=======================================${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check virtual environment
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo -e "${GREEN}Using virtual environment: $VIRTUAL_ENV${NC}"
elif [[ -f "venv/bin/activate" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
elif [[ -f ".venv/bin/activate" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

check_package() {
    python3 -c "import $1" 2>/dev/null && return 0 || return 1
}

# Get Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

MISSING=""
check_package "whisper" || MISSING="$MISSING openai-whisper"
check_package "webrtcvad" || MISSING="$MISSING webrtcvad"

check_package "fastapi" || MISSING="$MISSING fastapi"
check_package "uvicorn" || MISSING="$MISSING uvicorn"
check_package "numpy" || MISSING="$MISSING numpy"

if [[ -n "$MISSING" ]]; then
    echo -e "${YELLOW}Missing packages:$MISSING${NC}"
    echo -e "${YELLOW}Installing...${NC}"
    pip install $MISSING
fi

# Print configuration
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Host:         $S2S_HOST"
echo "  Port:         $S2S_PORT"
echo "  ASR Model:    $ASR_MODEL"
echo "  ASR Device:   $ASR_DEVICE"
echo "  ASR Language: $ASR_LANGUAGE"
echo "  TTS Model:    $TTS_MODEL"
echo "  TTS GPU:      $TTS_GPU"
echo "  TTS Enabled:  $S2S_ENABLE_TTS"
echo ""

# Check GPU availability and compatibility
if [[ "$ASR_DEVICE" == "cuda" ]]; then
    # First check torch availability (startup check)
    if python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        GPU_NAME=$(python3 -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null || echo "Unknown")
        echo -e "${GREEN}GPU detected: $GPU_NAME${NC}"
        echo -e "${GREEN}Using openai-whisper on GPU.${NC}"
    else
        echo -e "${YELLOW}Warning: CUDA requested but not available. Falling back to CPU.${NC}"
        export ASR_DEVICE="cpu"
        export TTS_GPU="false"
    fi
fi

echo ""
echo -e "${GREEN}Starting S2S Gateway on ws://${S2S_HOST}:${S2S_PORT}/ws/s2s${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Set Python path
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Unset proxy variables for local service communication
# The S2S gateway talks to local services (LLM on :8080, Agent API on :8000)
# which should not go through proxy
unset ALL_PROXY all_proxy HTTP_PROXY http_proxy HTTPS_PROXY https_proxy

# Start the server
python3 -m services.speech.s2s_server
