# LLM Inference Setup for AMD Ryzen AI Max+ 395

## System Profile

| Component | Specification |
|-----------|---------------|
| APU | AMD Ryzen AI Max+ 395 (Strix Halo) |
| iGPU | Radeon 8060S (RDNA 3.5, gfx1151 architecture) |
| RAM | 30GB system RAM (up to ~75GB shared with iGPU via VGM) |
| OS | Linux (Ubuntu 24.04), ROCm 7.2 (Detected) |
| Use Case | Development/Debugging, Large Models (70B+) |

---

## Phase 1: ROCm Installation

### 1.1 Prerequisites

```bash
# Check kernel version (ROCm 7.x requires 6.10.x or newer)
uname -r

# Verify iGPU detection
lspci | grep -i "AMD*Radeon*8060"

# Install required packages
sudo apt update
sudo apt install wget gnupg2 software-properties-common
```

### 1.2 Install ROCm 7.x (Strix Halo Compatible)

```bash
# Add ROCm repository
wget https://repo.radeon.com/rocm/rocm.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/rocm.gpg.key
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg.key] https://repo.radeon.com/rocm/7.1.1/ubuntu noble main" | sudo tee /etc/apt/sources.list.d/rocm.list

# Install ROCm
sudo apt update
sudo apt install rocm-hip-libraries rocm-dev

# Add user to video group
sudo usermod -aG video $USER
sudo usermod -aG render $USER
```

### 1.3 Verify Installation

```bash
# Check ROCm installation
rocm-smi
hipconfig --platform
clinfo | grep "Device Name"
```

---

## Phase 2: llama.cpp Setup

### 2.1 Install Pre-built ROCm Binary (Recommended)

```bash
# Download AMD-validated pre-built binary
wget -O llama-bin-linux.zip https://repo.radeon.com/rocm/lts/ubuntu/24.04/llama-cpp/llama-bin-linux.zip
unzip llama-bin-linux.zip
cd llama-bin-linux

# Install dependencies
sudo apt install ./llama-cli_*.deb ./llama-server_*.deb ./llama-bench_*.deb
```

### 2.2 Build from Source (Alternative, for Latest Features)

```bash
# Clone ROCm/llama.cpp fork
git clone https://github.com/ROCm/llama.cpp
cd llama.cpp

# Build with ROCm support
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
cmake -S. -Bbuild -DGGML_HIP=ON \
-DAMDGPU_TARGETS=gfx1151 \
-DCMAKE_BUILD_TYPE=Release \
-DLLAMA_CURL=ON \
&& cmake --build build --config Release -j$(nproc)

# Install binaries
sudo cp build/bin/llama-* /usr/local/bin/
```

---

## Phase 3: Memory Configuration for 70B+ Models

### 3.1 Enable Unified Memory (Critical for Large Models)

```bash
# Runtime environment variable for unified memory
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
export GGML_CUDA_FORCE_MMQ=1

# For systems with >32GB RAM, consider:
export GGML_CUDA_VMM_MAX_PINNED_SIZE=0
```

### 3.2 Model Loading Strategy

For 70B models with your setup:

| Memory Type | Allocation |
|-------------|------------|
| VRAM | ~16GB dedicated |
| System RAM | Up to ~59GB available for shared memory |
| **Total** | **~75GB addressable memory** |

---

## Phase 4: Development Tools Setup

### 4.1 HTTP Server for API Development

```bash
# Start llama-server
./llama-server \
  -m models/Llama-2-70B-Chat-Q4_K_M.gguf \
  --port 8080 \
  --host 0.0.0.0 \
  -c 8192 \
  --temp 0.7 \
  --n-gpu-layers 999

# Environment for production
export LLAMA_SERVER_PORT=8080
export LLAMA_SERVER_HOST=0.0.0.0
export LLAMA_N_GPU_LAYERS=999
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
```

### 4.2 Benchmarking Setup

```bash
# Install llama-bench
./llama-bench \
  -m models/Llama-2-70B-Q4_K_M.gguf \
  -p 512 \
  -n 128 \
  --batch 512

# Create benchmark script
cat > ~/bench_llm.sh << 'EOF'
#!/bin/bash
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
./llama-bench -m $1 -p $2 -n $3 --batch $4
EOF
chmod +x ~/bench_llm.sh
```

### 4.3 Model Management

```bash
# Create model directory
mkdir -p ~/models/{7b,13b,30b,70b}

# Download script example
cat > ~/download_model.sh << 'EOF'
#!/bin/bash
MODEL_SIZE=$1
huggingface-cli download \
  meta-llama/Llama-2-${MODEL_SIZE}-Chat-GGUF \
  --local-dir ~/models/${MODEL_SIZE} \
  --include "*Q4_K_M*"
EOF
```

---

## Phase 5: Recommended Models & Configurations

### 5.1 Model Size Guidelines

| Model Size | Example Models | Memory (Q4_K_M) | Expected TPS | Notes |
|------------|---------------|-----------------|--------------|-------|
| 7B | Qwen3-8B, Llama 3.1 7B | ~5GB | 50-80 | Fast, great for development |
| 13B | Qwen3-14B, Llama 2 13B | ~9GB | 35-50 | Balanced capability/speed |
| 30B | Qwen3-30B-A3B, Llama 2 30B | ~20GB | 20-35 | MoE efficient, 3B active |
| 70B | Qwen3-32B, Llama 2 70B | ~45GB | 10-20 | High capability |
| 235B | Qwen3-235B-A22B | ~150GB+ | 2-5 | Flagship, needs VGM |

### 5.2 Recommended Qwen3 Models (Latest 2026)

**Qwen3-30B-A3B-Instruct-2507** (Recommended for your hardware)
```bash
# URL: Qwen/Qwen3-30B-A3B-Instruct-2507
# Architecture: MoE (128 experts, 8 active)
# Active Parameters: ~3B per token
# Memory: ~20GB (Q4_K_M)
# Features: Thinking mode, 128K context
```

**Qwen3-32B-Instruct**
```bash
# URL: Qwen/Qwen3-32B-Instruct
# Architecture: Dense
# Memory: ~21GB (Q4_K_M)
# Features: Consistent performance, no MoE overhead
```

**Qwen3-14B-Instruct**
```bash
# URL: Qwen/Qwen3-14B-Instruct
# Memory: ~9GB (Q4_K_M)
# TPS: 50-80
# Great for quick testing and development iterations
```

### 5.3 Download Commands

```bash
# 30B MoE (Recommended)
huggingface-cli download Qwen/Qwen3-30B-A3B-Instruct-2507-GGUF \
  --local-dir ~/models/30b \
  --include "*Q4_K_M*"

# 32B Dense
huggingface-cli download Qwen/Qwen3-32B-Instruct-GGUF \
  --local-dir ~/models/32b

# 14B (Development)
huggingface-cli download Qwen/Qwen3-14B-Instruct-GGUF \
  --local-dir ~/models/14b
```

### 5.4 Example Configurations

```bash
# Qwen3-30B-A3B Model (Recommended for your use case)
./llama-server \
  -m models/30b/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf \
  --port 8080 \
  -c 8192 \
  --n-gpu-layers 999 \
  --temp 0.6 \
  --repeat-penalty 1.1

# Qwen3-32B Model (Dense alternative)
./llama-server \
  -m models/32b/Qwen3-32B-Instruct-Q4_K_M.gguf \
  --port 8081 \
  -c 8192 \
  --n-gpu-layers 999

# 7B Model (Quick testing)
./llama-cli -m models/14b/Qwen3-14B-Instruct-Q4_K_M.gguf -p "Hello world" -c 2048
```

---

## Phase 6: RAG Setup (Embedding & Reranker Models)

### 6.1 Overview

A complete RAG pipeline requires:
1. **Embedding Model**: Converts text to vectors for storage/retrieval
2. **Reranker Model**: Re-ranks initial retrieval results for better relevance
3. **LLM**: Generates final response (from Phase 5)

### 6.2 Recommended Embedding Models

| Model | Size | Dimensions | Memory | Use Case |
|-------|------|------------|--------|----------|
| **BGE-m3** | 2.4B | 1024 | ~3GB | General purpose, multilingual |
| **Qwen3-Embedding-0.6B** | 0.6B | 1024 | ~1GB | Efficient, Qwen ecosystem |
| **EmbeddingGemma-308M** | 308M | 768 | ~500MB | On-device, mobile RAG |
| **all-MiniLM-L12-v2** | 33M | 384 | ~150MB | Fast, lightweight |
| **E5-small-v2** | 33M | 384 | ~150MB | Fast, good quality |

### 6.3 Embedding Model Setup

```bash
# Create embeddings directory
mkdir -p ~/models/embeddings

# Install sentence-transformers
pip install sentence-transformers

# Download and test embedding model
cat > ~/test_embedding.py << 'EOF'
from sentence_transformers import SentenceTransformer

# Load model (auto-downloads on first run)
model = SentenceTransformer("BAAI/bge-m3")

# Generate embeddings
sentences = ["Hello world", "RAG is useful"]
embeddings = model.encode(sentences, normalize_embeddings=True)

print(f"Embedding shape: {embeddings.shape}")
print(f"Dimensions: {model.get_sentence_embedding_dimension()}")
EOF

python ~/test_embedding.py
```

### 6.4 Recommended Reranker Models

| Model | Size | Memory | Improvement | Notes |
|-------|------|--------|-------------|-------|
| **BGE-Reranker-v2.5-3B** | 3B | ~4GB | +40% | Best quality |
| **BAAI/bge-reranker-base** | 278M | ~500MB | +30% | Lightweight |
| **ms-marco-MiniLM-L-6-v2** | 22M | ~100MB | +25% | Very fast |
| **Qwen3-Reranker-1.5B** | 1.5B | ~2GB | +35% | Qwen ecosystem |

### 6.5 Reranker Model Setup

```bash
# Install cross-encoder
pip install sentence-transformers

# Test reranker
cat > ~/test_reranker.py << 'EOF'
from sentence_transformers import CrossEncoder

# Load reranker model
model = CrossEncoder("BAAI/bge-reranker-base")

# Score query-document pairs
query = "What is RAG?"
documents = [
    "Retrieval-Augmented Generation combines retrieval and generation",
    "The weather is sunny today",
    "RAG improves LLM responses with context"
]

scores = model.predict([(query, doc) for doc in documents])
print("Scores:", scores)

# Sort by score
ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
print("\nRanked results:")
for doc, score in ranked:
    print(f"  {score:.4f}: {doc[:50]}...")
EOF

python ~/test_reranker.py
```

### 6.6 Complete RAG Pipeline Example

```bash
cat > ~/rag_pipeline.py << 'EOF'
"""
Complete RAG Pipeline for AMD Strix Halo
"""
from sentence_transformers import SentenceTransformer, CrossEncoder
from sentence_transformers import SentenceTransformer
import numpy as np

class RAGPipeline:
    def __init__(self, embedding_model="BAAI/bge-m3", reranker_model="BAAI/bge-reranker-base"):
        print(f"Loading embedding model: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)
        
        print(f"Loading reranker model: {reranker_model}")
        self.reranker = CrossEncoder(reranker_model)
        
        self.corpus = []
        self.corpus_embeddings = None
    
    def index_documents(self, documents):
        """Index documents for retrieval"""
        self.corpus = documents
        self.corpus_embeddings = self.embedder.encode(
            documents, normalize_embeddings=True, show_progress_bar=True
        )
        print(f"Indexed {len(documents)} documents")
    
    def retrieve(self, query, top_k=10):
        """Initial retrieval using embeddings"""
        query_embedding = self.embedder.encode(query, normalize_embeddings=True)
        similarities = np.dot(self.corpus_embeddings, query_embedding)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [(i, self.corpus[i], similarities[i]) for i in top_indices]
    
    def rerank(self, query, retrieval_results, top_k=3):
        """Rerank initial retrieval results"""
        pairs = [(query, doc) for _, doc, _ in retrieval_results]
        scores = self.reranker.predict(pairs)
        
        reranked = sorted(zip(retrieval_results, scores), key=lambda x: x[1], reverse=True)
        return reranked[:top_k]
    
    def query(self, query, top_k=5):
        """Complete RAG query"""
        # Step 1: Retrieve
        retrieved = self.retrieve(query, top_k=20)
        
        # Step 2: Rerank
        reranked = self.rerank(query, retrieved, top_k=top_k)
        
        # Step 3: Return context
        context = "\n\n".join([doc for (_, doc, _), _ in reranked])
        return context, reranked

# Example usage
if __name__ == "__main__":
    rag = RAGPipeline()
    
    # Index documents
    docs = [
        "RAG combines retrieval and generation for better AI responses",
        "AMD Ryzen AI Max+ 395 supports local LLM inference",
        "ROCm enables GPU acceleration on AMD hardware",
        "Embedding models convert text to vectors",
        "Cross-encoders improve search relevance"
    ]
    rag.index_documents(docs)
    
    # Query
    query = "What hardware supports local LLM inference?"
    context, results = rag.query(query)
    
    print(f"\nQuery: {query}")
    print(f"\nTop results:")
    for (idx, doc, score), rerank_score in results:
        print(f"  Score: {rerank_score:.4f} | {doc}")
EOF

python ~/rag_pipeline.py
```

### 6.7 RAG Model Memory Requirements

| Component | Model | Memory | Total System Impact |
|-----------|-------|--------|---------------------|
| Embedding | BGE-m3 | ~3GB | Low |
| Embedding | MiniLM | ~150MB | Minimal |
| Reranker | BGE-Reranker-v2.5 | ~4GB | Medium |
| Reranker | ms-marco-MiniLM | ~100MB | Minimal |
| LLM | Qwen3-30B-A3B | ~20GB | High |
| **Total (Full Stack)** | | **~27GB** | Within 30GB limit |

---

## Phase 7: Testing & Validation

### 7.1 GPU Detection Test

```bash
./llama-bench -m any_7b_model.gguf -p 1 -n 1 --batch 1 2>&1 | grep -E "ROCm|backend|gfx"
```

### 7.2 Memory Test

```bash
# Verify unified memory is being used
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
./llama-cli -m 70b_model.gguf -p "test" -c 256 2>&1 | grep -i memory
```

### 7.3 Performance Baseline

```bash
# Run standard benchmark
./llama-bench -m models/7B/Llama-3.1-8B-Q4_K_M.gguf -p 512 -n 128 --batch 512
```

---

## Phase 8: Troubleshooting Common Issues

### 8.1 GPU Not Detected

```bash
# Check HIP device enumeration
hipconfig --platform
clinfo | grep "Device Name"

# Verify /dev/kfd access
ls -la /dev/kfd
sudo chmod +rwx /dev/kfd
```

### 8.2 Out of Memory Errors

```bash
# Reduce context size
-c 2048 (instead of 8192)

# Enable fallback to CPU
--n-gpu-layers 999 (loads all layers to GPU, adjust down if needed)

# Enable unified memory
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
```

### 8.3 Low Performance

```bash
# Enable Flash Attention
--fa

# Optimize batch size
--batch 512

# Check GPU utilization
rocm-smi
```

---

## Phase 9: Estimated Timeline

| Phase | Time |
|-------|------|
| Phase 1 | 15-30 minutes |
| Phase 2 | 10-20 minutes (pre-built) or 30-60 minutes (build from source) |
| Phase 3 | 5 minutes |
| Phase 4 | 15 minutes |
| Phase 5 | 30-60 minutes (downloading models, testing) |
| Phase 6-7 (RAG) | 30 minutes |

**Total Setup Time**: ~3-4 hours (including model downloads)

---

## Key Files & Locations

| Path | Description |
|------|-------------|
| `/opt/rocm/` | ROCm installation directory |
| `/usr/local/bin/llama-*` | llama.cpp binaries |
| `~/models/` | Model storage directory |
| `~/.llama/` | Logs and cache |
| `http://localhost:8080` | Server API endpoint |

---

## Quick Reference Commands

```bash
# Check GPU
rocm-smi

# Download Qwen3 model
huggingface-cli download Qwen/Qwen3-30B-A3B-Instruct-2507-GGUF --local-dir ~/models/30b

# Run server with Qwen3
./llama-server -m ~/models/30b/Qwen3-30B-A3B-Instruct-Q4_K_M.gguf --port 8080

# Download embedding model
huggingface-cli download BAAI/bge-m3 --local-dir ~/models/embeddings/bge-m3

# Download reranker model
huggingface-cli download BAAI/bge-reranker-base --local-dir ~/models/rerankers

# Benchmark
./llama-bench -m ~/models/30b/Qwen3-30B-A3B-Q4_K_M.gguf -p 512 -n 128

# Interactive CLI
./llama-cli -m ~/models/30b/model.gguf -p "Your prompt"
```

---

## Model Download Summary

### Chat/Generation Models (llama.cpp)

| Model | URL | Size | Memory |
|-------|-----|------|--------|
| Qwen3-30B-A3B-Instruct | `Qwen/Qwen3-30B-A3B-Instruct-2507-GGUF` | 31B | ~20GB |
| Qwen3-32B-Instruct | `Qwen/Qwen3-32B-Instruct-GGUF` | 32B | ~21GB |
| Qwen3-14B-Instruct | `Qwen/Qwen3-14B-Instruct-GGUF` | 14B | ~9GB |
| Qwen3-8B-Instruct | `Qwen/Qwen3-8B-GGUF` | 8B | ~5GB |

### Embedding Models (sentence-transformers)

| Model | URL | Size | Dimensions |
|-------|-----|------|------------|
| BGE-m3 | `BAAI/bge-m3` | 2.4B | 1024 |
| Qwen3-Embedding-0.6B | `Qwen/Qwen3-Embedding-0.6B` | 0.6B | 1024 |
| EmbeddingGemma-308M | `sentence-transformers/embeddinggemma-300m` | 308M | 768 |
| MiniLM-L12-v2 | `sentence-transformers/all-MiniLM-L12-v2` | 33M | 384 |

### Reranker Models (cross-encoder)

| Model | URL | Size | Improvement |
|-------|-----|------|-------------|
| BGE-Reranker-v2.5-3B | `BAAI/bge-reranker-v2.5-3B` | 3B | +40% |
| BGE-Reranker-base | `BAAI/bge-reranker-base` | 278M | +30% |
| ms-marco-MiniLM | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 22M | +25% |

---

## Performance Benchmarks (Qwen3 on Strix Halo)

### Expected Token Generation Speed

| Model | Quantization | Expected TPS | Notes |
|-------|--------------|--------------|-------|
| Qwen3-8B | Q4_K_M | 80-120 | Fastest |
| Qwen3-14B | Q4_K_M | 50-80 | Balanced |
| Qwen3-30B-A3B | Q4_K_M | 25-40 | MoE efficient |
| Qwen3-32B | Q4_K_M | 20-35 | Dense reliable |
| Qwen3-235B-A22B | Q4_K_M | 2-5 | Flagship, needs VGM |

### RAG Pipeline Performance

| Component | Model | Inference Speed |
|-----------|-------|-----------------|
| Embedding | BGE-m3 | ~100 docs/sec |
| Embedding | MiniLM | ~500 docs/sec |
| Reranker | BGE-Reranker-base | ~50 docs/sec |
| Reranker | ms-marco-MiniLM | ~200 docs/sec |
