#!/bin/bash
# Install ROCm-optimized llama.cpp binaries for AMD Strix Halo
# This assumes ROCm 7.x is already installed on the system.

set -e

echo "📥 Downloading pre-built llama.cpp for ROCm (gfx1151 optimized)..."

# Temporary directory for setup
mkdir -p /tmp/llama-rocm-setup
cd /tmp/llama-rocm-setup

# Download AMD-validated pre-built binary (targets ROCm/HIP)
# Using the stable community/AMD repository links
wget -O llama-bin-linux.zip https://repo.radeon.com/rocm/lts/ubuntu/24.04/llama-cpp/llama-bin-linux.zip

echo "📦 Unzipping and installing binaries..."
unzip -o llama-bin-linux.zip

# Install the .deb packages
# This will replace /usr/local/bin/llama-* if they were installed via the same method
sudo apt install -y ./*.deb

echo "✅ ROCm-optimized llama.cpp installed!"
echo "👉 You can now run scripts/start-llm-strix.sh without rebooting (since drivers were already active)."
