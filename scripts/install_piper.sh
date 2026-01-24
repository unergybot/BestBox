#!/bin/bash
# Install Piper TTS and Voice Models
# Usage: ./scripts/install_piper.sh

set -e

# Configuration
PIPER_VERSION="2023.11.14-2"
PLATFORM="linux_x86_64" # Corrected from linux_amd64
INSTALL_DIR="third_party/piper"
MODEL_DIR="models/piper"

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$MODEL_DIR"

# 1. Download Piper Binary
echo "⬇️ Downloading Piper..."
PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_${PLATFORM}.tar.gz"
wget -qO piper.tar.gz "$PIPER_URL"
tar -xzf piper.tar.gz -C third_party/
rm piper.tar.gz
# Move contents if nested, or just verify structure. 
# Usually extracts to 'piper/' directory. 
# We want: third_party/piper/piper

if [[ -f "third_party/piper/piper" ]]; then
    echo "✅ Piper binary installed."
else
    echo "❌ Piper binary not found after extraction."
    exit 1
fi

# 2. Download Voice Models
# We need an English model and a Chinese model (if available/requested)
# Best generic English: en_US-libritts_r-medium.onnx
# Chinese: zh_CN-huayan-medium.onnx

download_model() {
    local LANG=$1
    local NAME=$2
    local URL_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/${LANG}/${NAME}/medium"
    
    echo "⬇️ Downloading Voice: ${NAME}..."
    wget -qO "${MODEL_DIR}/${NAME}.onnx" "${URL_BASE}/${NAME}.onnx"
    wget -qO "${MODEL_DIR}/${NAME}.onnx.json" "${URL_BASE}/${NAME}.onnx.json"
}

# English (Libritts R - very clean)
download_model "en/en_US" "en_US-libritts_r"

# Chinese (Huayan - standard mandarin)
download_model "zh/zh_CN" "zh_CN-huayan"

echo "✅ Installation Complete!"
echo "Piper is ready at: ${INSTALL_DIR}/piper"
echo "Models are in: ${MODEL_DIR}"
