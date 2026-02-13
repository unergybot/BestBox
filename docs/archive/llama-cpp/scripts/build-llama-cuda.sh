#!/bin/bash
# Build llama.cpp with CUDA support for NVIDIA GPUs
# Tested with RTX 3080, RTX 4090, Tesla P100, etc.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LLAMA_DIR="${PROJECT_DIR}/third_party/llama.cpp"

echo "🔧 Building llama.cpp with CUDA support"
echo ""

# Check for CUDA
if ! command -v nvcc &> /dev/null; then
    echo "❌ nvcc not found. Please install CUDA toolkit first."
    echo "   Ubuntu: sudo apt install nvidia-cuda-toolkit"
    echo "   Or download from: https://developer.nvidia.com/cuda-downloads"
    exit 1
fi

echo "✅ CUDA found: $(nvcc --version | grep release)"
echo ""

# Clone or update llama.cpp
if [ -d "$LLAMA_DIR" ]; then
    echo "📁 Found existing llama.cpp, updating..."
    cd "$LLAMA_DIR"
    git fetch origin
    git checkout master
    git pull origin master
else
    echo "📥 Cloning llama.cpp..."
    mkdir -p "$(dirname "$LLAMA_DIR")"
    git clone https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR"
    cd "$LLAMA_DIR"
fi

# Clean previous build
echo "🧹 Cleaning previous build..."
rm -rf build

# Configure with CUDA
echo "⚙️  Configuring with CUDA..."
cmake -S . -B build \
    -DGGML_CUDA=ON \
    -DLLAMA_CURL=ON \
    -DCMAKE_BUILD_TYPE=Release

# Build
echo "🔨 Building (this may take a few minutes)..."
cmake --build build --config Release -j$(nproc)

# Verify build
if [ -f "build/bin/llama-server" ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "📍 Binaries installed to:"
    echo "   llama-server: ${LLAMA_DIR}/build/bin/llama-server"
    echo "   llama-cli:    ${LLAMA_DIR}/build/bin/llama-cli"
    echo "   llama-bench:  ${LLAMA_DIR}/build/bin/llama-bench"
    echo ""
    echo "🚀 To start the LLM server with CUDA:"
    echo "   export LLM_MODEL_PATH=~/models/4b/Qwen3-4B-Instruct-Q4_K_M.gguf"
    echo "   ./scripts/start-llm-cuda.sh"
else
    echo "❌ Build failed. Check the output above for errors."
    exit 1
fi
