#!/bin/bash
# Setup ROCm 7.x and llama.cpp for AMD Ryzen AI Max+ 395 (gfx1151)
# Based on docs/llm-setup-plan.md

set -e

echo "🛠️  Starting ROCm & llama.cpp setup for Strix Halo..."

# 1. Prerequisites
echo "📦 Installing prerequisites..."
sudo apt update
sudo apt install -y wget gnupg2 software-properties-common unzip cmake build-essential git

# 2. Install ROCm (Using 7.2 as requested)
echo "🚀 Adding ROCm 7.2 repository..."
wget -qO- https://repo.radeon.com/rocm/rocm.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/rocm.gpg.key
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg.key] https://repo.radeon.com/rocm/7.2/ubuntu noble main" | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update
sudo apt install -y rocm-hip-libraries rocm-dev

# Add user to groups
sudo usermod -aG video $USER
sudo usermod -aG render $USER

# 4. Optional: Instructions for building llama.cpp from source specifically for gfx1151
# cmake -S . -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1151 -DLLAMA_CURL=ON
# 3. llama.cpp installation (Pre-built binary preferred)
echo "📥 Downloading pre-built llama.cpp for ROCm..."
mkdir -p /tmp/llama-setup
cd /tmp/llama-setup
wget -O llama-bin-linux.zip https://repo.radeon.com/rocm/lts/ubuntu/24.04/llama-cpp/llama-bin-linux.zip
unzip llama-bin-linux.zip
sudo apt install -y ./*.deb

# 4. Model Directory Setup
echo "📁 Setting up model directories..."
mkdir -p ~/models/{14b,30b,32b,70b,embeddings,rerankers}

echo ""
echo "✅ Setup attempt complete!"
echo "⚠️  Note: You may need to REBOOT for group changes and ROCm drivers to take effect."
echo "👉 Next steps: Download models and use scripts/start-llm-strix.sh"
