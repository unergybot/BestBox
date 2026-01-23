# BestBox - Enterprise Agentic Applications Demo Kit

**Version:** 1.1  
**Status:** Infrastructure Phase (ROCm Verified ✅)  
**Platform:** AMD Ryzen AI Max+ 395 with Radeon 8060S

---

## Quick Start

### System Status

| Component | Status | Details |
|-----------|--------|---------|
| **Hardware** | ✅ Ready | AMD Ryzen AI Max+ 395, 128GB RAM, 2TB NVMe |
| **GPU** | ✅ Operational | AMD Radeon 8060S (gfx1151), 98GB memory |
| **ROCm** | ✅ Verified | Version 7.2.0 installed and tested |
| **Python Env** | ✅ Complete | Python 3.12.3, PyTorch 2.10.0+rocm7.1, GPU OK |
| **AI Stack** | ⏳ Pending | vLLM + TEI deployment planned |
| **Applications** | ⏳ Pending | 4 demo scenarios in development |

### Project Structure

```
BestBox/
├── docs/
│   ├── product_desc.md              # Product requirements
│   ├── system_design.md             # Complete system architecture (800+ lines)
│   ├── review_checklist.md          # Stakeholder review items (80+)
│   └── rocm_deployment_guide.md     # ROCm 7.2.0 installation guide (NEW)
├── src/                             # (To be created)
│   ├── agents/                      # LangGraph agent implementations
│   ├── tools/                       # Tool adapters for ERP/CRM/OA
│   ├── frontend/                    # CopilotKit UI components
│   └── infrastructure/              # Docker Compose, configs
└── README.md                        # This file
```

---

## Documentation

### Core Documents

1. **[System Design Document](docs/system_design.md)** (800+ lines)
   - Complete 5-layer architecture specification
   - Multi-agent design with LangGraph FSM patterns
   - 4 demo scenarios with detailed workflows
   - 10-week implementation roadmap
   - Technology stack and integration points

2. **[ROCm Deployment Guide](docs/rocm_deployment_guide.md)** (NEW - 500+ lines)
   - Complete ROCm 7.2.0 installation procedure
   - Hardware verification and compatibility
   - GPU performance characteristics
   - Common issues and troubleshooting
   - Integration with PyTorch, vLLM, Docker
   - Environment variables and monitoring tools

3. **[Review Checklist](docs/review_checklist.md)**
   - 80+ validation items for stakeholder review
   - Architecture, models, infrastructure assessment
   - Risk analysis and open questions

4. **[Product Description](docs/product_desc.md)**
   - Original requirements and vision
   - Target audience and use cases

---

## ROCm Installation Summary

### Verified Configuration

```bash
Hardware:    AMD Ryzen AI Max+ 395 w/ Radeon 8060S
GPU Arch:    RDNA 3.5 (gfx1151)
Compute:     40 CUs, 2900 MHz, 98GB memory
OS:          Ubuntu 24.04.3 LTS (kernel 6.14.0-37)
ROCm:        7.2.0 (302 packages installed)
HIP:         7.2.26015
Driver:      amdgpu (in-kernel)
```

### Quick Verification

```bash
# Check GPU is detected
rocminfo | grep -A 5 "Marketing Name"

# Expected output:
# Marketing Name: AMD Radeon 8060S
# Device Type: GPU
# Chip ID: 5510(0x1586)
# Compute Unit: 40

# Check GPU status
rocm-smi

# Verify HIP compilation
hipconfig --full
```

### Key Installation Notes

⚠️ **Critical Steps:**
1. Ubuntu 24.04 has conflicting ROCm 5.7.1 packages - must be removed
2. User must be in `render` and `video` groups for GPU access
3. Group membership requires logout/login or `newgrp render`
4. ROCm 7.2 requires `--allow-downgrades` flag during installation

See **[ROCm Deployment Guide](docs/rocm_deployment_guide.md)** for complete details.

---

## Next Steps (Phase 1: Weeks 1-2)

### Week 1: Python & AI Stack

- [ ] Install Python 3.12+ with uv package manager
- [ ] Setup virtual environment with PyTorch ROCm 6.2
- [ ] Verify PyTorch GPU access: `torch.cuda.is_available()`
- [ ] Deploy vLLM with Qwen3-14B-Instruct model
- [ ] Test vLLM inference API

### Week 2: Infrastructure

- [ ] Deploy PostgreSQL 16 database
- [ ] Deploy Redis 7 for caching
- [ ] Deploy Qdrant vector database
- [ ] Setup Text Embeddings Inference with BGE-M3
- [ ] Create Docker Compose orchestration
- [ ] Configure ROCm device mounting in containers

### Environment Setup

```bash
# Create Python virtual environment
python3 -m venv ~/BestBox/venv
source ~/BestBox/venv/bin/activate

# Install PyTorch with ROCm support
pip3 install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/rocm6.2

# Test GPU access
python3 -c "import torch; print(f'GPU: {torch.cuda.is_available()}')"

# Install vLLM
pip3 install vllm

# Set ROCm environment
export ROCM_PATH=/opt/rocm-7.2.0
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # Map gfx1151 → gfx1100
export PYTORCH_ROCM_ARCH=gfx1100
```

---

## Architecture Highlights

### Multi-Agent System

```
User Query → Classifier Agent → Specialized Agent → Tool Gateway → Enterprise System
                                 ├─ ERP Copilot
                                 ├─ CRM Sales Assistant
                                 ├─ IT Ops Agent
                                 └─ OA Workflow Agent
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **UI** | CopilotKit + React | Real-time chat with generative UI |
| **Orchestration** | LangGraph | Multi-agent FSM coordination |
| **LLM** | Qwen3-14B-Instruct | Primary reasoning engine |
| **Embeddings** | BGE-M3 | Text vectorization (1024-dim) |
| **Vector DB** | Qdrant | Semantic search and RAG |
| **GPU Runtime** | ROCm 7.2.0 + HIP | AMD GPU acceleration |
| **Inference** | vLLM + TEI | High-performance serving |

### Demo Scenarios

1. **ERP Copilot**: Invoice processing, inventory checks, financial reporting
2. **CRM Sales Assistant**: Lead qualification, quotation generation, opportunity tracking
3. **IT Operations Agent**: Ticket routing, knowledge base search, automated diagnostics
4. **OA Workflow Agent**: Leave approvals, meeting scheduling, document workflows

---

## Resource Requirements

### Confirmed Available

- ✅ **GPU Memory**: 98GB (75% of 128GB system RAM)
- ✅ **Compute**: 40 CUs @ 2900 MHz (14.88 TFLOPS FP32)
- ✅ **System RAM**: 128GB DDR5
- ✅ **Storage**: 2TB NVMe SSD
- ✅ **ROCm**: 7.2.0 with HIP, OpenCL, hipBLAS, MIOpen

### Estimated Usage

| Component | Memory | GPU Compute |
|-----------|--------|-------------|
| Qwen3-14B (FP16) | ~28GB | 60% utilization |
| BGE-M3 embeddings | ~2GB | 15% utilization |
| Vector DB cache | ~8GB | N/A |
| OS + overhead | ~10GB | N/A |
| **Total** | **~48GB** | **~75%** |

Remaining capacity: ~50GB for additional models or larger batches.

---

## Development Timeline

### Phase 1: Infrastructure (Weeks 1-2) ⏳ IN PROGRESS
- ROCm installation and verification ✅ DONE
- Python environment setup ⏳ Next
- AI inference stack deployment ⏳ Next
- Database infrastructure ⏳ Pending

### Phase 2: Backend (Weeks 3-4)
- LangGraph agent framework
- Tool gateway development
- CopilotKit integration

### Phase 3: Demo Apps (Weeks 5-8)
- ERP Copilot (Week 5-6)
- CRM Assistant (Week 6-7)
- IT Ops Agent (Week 7-8)
- OA Workflow (Week 8)

### Phase 4: Frontend (Weeks 9-10)
- React + CopilotKit UI
- Mobile responsiveness
- Generative UI components

### Phase 5: Testing & Optimization (Week 11-12)
- Performance benchmarking
- SLA validation
- Documentation and handoff

---

## Key Features

### Production-Ready Architecture
- Multi-agent coordination with LangGraph state machines
- Streaming responses via CopilotKit protocol
- Tool calling with error recovery
- Context management with sliding window

### Enterprise Integration
- RESTful API adapters for ERP/CRM/OA systems
- SQL query generation for relational databases
- Vector search for semantic knowledge retrieval
- Structured output for form generation

### Observability & Monitoring
- LangSmith integration for agent tracing
- Prometheus metrics export
- GPU utilization monitoring (rocm-smi)
- Request/response logging

### Security & Compliance
- 100% on-premise deployment (no external API calls)
- Role-based access control (RBAC)
- Audit logging for all agent actions
- PII detection and masking

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **LLM Latency (P50)** | <500ms | First token for 2K context |
| **LLM Latency (P99)** | <2s | First token for 8K context |
| **Throughput** | 30-50 tok/s | Single user, 14B model |
| **Embedding** | <100ms | 512 tokens to 1024-dim vector |
| **Vector Search** | <50ms | Top-10 results from 100K docs |
| **E2E Response** | <3s | Simple query with 1 tool call |
| **Concurrent Users** | 5-8 users | Shared 14B model instance |

---

## Getting Help

### RAG Pipeline

```bash
# One-time: Seed knowledge base with demo documents
python scripts/seed_knowledge_base.py

# Start reranker service (in separate terminal)
./scripts/start-reranker.sh
```

### Common Commands

```bash
# Check ROCm status
rocm-smi

# Monitor GPU in real-time
watch -n 2 rocm-smi

# Check device permissions
ls -l /dev/kfd /dev/dri/renderD*

# View ROCm environment
hipconfig --full

# Test GPU detection
rocminfo | grep -A 10 "Agent 2"
```

### Troubleshooting

If you encounter GPU access issues:

```bash
# Verify group membership
groups $USER

# If 'render' not shown, activate it:
newgrp render

# Or logout and login again
logout
```

See **[ROCm Deployment Guide - Common Issues](docs/rocm_deployment_guide.md#common-issues-and-solutions)** for detailed troubleshooting.

---

## References

### External Documentation
- [ROCm Documentation](https://rocm.docs.amd.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CopilotKit Documentation](https://docs.copilotkit.ai/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Qwen3 Model Card](https://huggingface.co/Qwen/Qwen3-14B-Instruct)

### Project Links
- System Design: [docs/system_design.md](docs/system_design.md)
- ROCm Guide: [docs/rocm_deployment_guide.md](docs/rocm_deployment_guide.md)
- Review Checklist: [docs/review_checklist.md](docs/review_checklist.md)

---

## License

Proprietary - Internal Demo Project

---

## Contact

For questions or issues, refer to the documentation or contact the BestBox development team.

**Last Updated:** January 22, 2026  
**Project Status:** Phase 1 - Infrastructure Setup (ROCm Verified ✅)
