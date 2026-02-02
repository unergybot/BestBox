#!/bin/bash
# Start the BestBox Speech-to-Speech Gateway
#
# This script starts the S2S WebSocket server that provides:
# - ASR (FunASR or faster-whisper) for speech recognition
# - TTS (MeloTTS or Piper) for speech synthesis
# - WebSocket endpoint for real-time streaming
#
# Prerequisites:
#   - Python 3.10+
#   - CUDA for GPU acceleration
#   - FunASR/MeloTTS or faster-whisper/Piper installed
#
# Usage:
#   ./scripts/start-s2s.sh [--port PORT] [--host HOST]
#
# Environment variables:
#   S2S_HOST        - Bind address (default: 0.0.0.0)
#   S2S_PORT        - Server port (default: 8765)
#   ASR_ENGINE      - ASR engine: funasr or whisper (default: funasr)
#   ASR_MODEL       - Whisper model size (default: large-v3, only for whisper engine)
#   ASR_DEVICE      - Device for ASR (default: cuda:1 for P100)
#   ASR_LANGUAGE    - Recognition language (default: zh)
#   TTS_ENGINE      - TTS engine: melo or piper (default: melo)
#   TTS_MODEL       - TTS model (default: piper, only for piper engine)
#   TTS_DEVICE      - Device for TTS (default: cuda:1 for P100)
#   TTS_GPU         - Use GPU for TTS (default: true)
#   S2S_ENABLE_TTS  - Enable TTS synthesis (default: true)

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

# Engine selection (funasr/whisper for ASR, melo/piper for TTS)
export ASR_ENGINE="${ASR_ENGINE:-funasr}"  # funasr (default) or whisper
export TTS_ENGINE="${TTS_ENGINE:-melo}"    # melo (default) or piper

# ASR configuration
export ASR_MODEL="${ASR_MODEL:-Systran/faster-distil-whisper-large-v3}"  # Only for whisper engine
export ASR_DEVICE="${ASR_DEVICE:-cuda:1}"  # P100 for speech
export ASR_LANGUAGE="${ASR_LANGUAGE:-zh}"

# TTS configuration
export TTS_MODEL="${TTS_MODEL:-piper}"     # Only for piper engine
export TTS_DEVICE="${TTS_DEVICE:-cuda:1}"  # P100 for speech
export TTS_GPU="${TTS_GPU:-true}"
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

# Core dependencies
check_package "fastapi" || MISSING="$MISSING fastapi"
check_package "uvicorn" || MISSING="$MISSING uvicorn"
check_package "numpy" || MISSING="$MISSING numpy"
check_package "webrtcvad" || MISSING="$MISSING webrtcvad"

# ASR engine dependencies
if [[ "$ASR_ENGINE" == "funasr" ]]; then
    check_package "funasr" || MISSING="$MISSING funasr modelscope"
else
    check_package "whisper" || MISSING="$MISSING openai-whisper"
fi

# TTS engine dependencies
if [[ "$TTS_ENGINE" == "melo" ]]; then
    check_package "melo" || MISSING="$MISSING melo-tts"
fi

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
echo "  ASR Engine:   $ASR_ENGINE"
echo "  ASR Device:   $ASR_DEVICE"
echo "  ASR Language: $ASR_LANGUAGE"
if [[ "$ASR_ENGINE" == "whisper" ]]; then
    echo "  ASR Model:    $ASR_MODEL"
fi
echo "  TTS Engine:   $TTS_ENGINE"
echo "  TTS Device:   $TTS_DEVICE"
echo "  TTS Enabled:  $S2S_ENABLE_TTS"
if [[ "$TTS_ENGINE" == "piper" ]]; then
    echo "  TTS Model:    $TTS_MODEL"
fi
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
