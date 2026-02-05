# Agentic RAG-R1 Integration Design & Implementation Plan

**Date:** 2026-02-04  
**Status:** Draft  
**Phase:** 3 - Demo Applications (RAG Track)

## Overview

This document reviews the Agentic-RAG-R1 repository and proposes how to integrate its reinforcement-learning-based agentic RAG capabilities into BestBox. The focus is to improve tool usage decisions, retrieval quality, and structured reasoning for RAG answers, while keeping BestBox’s multi-agent architecture intact.

## Repository Review (Agentic-RAG-R1)

**Core capabilities:**
- Reinforcement learning (GRPO/DAPO/PPO/SFT) to train an agentic RAG policy model.
- Structured action tags in generation (`<reasoning>`, `<search>`, `<summary>`, `<answer>`) with tool interruption logic.
- Reward shaping: correctness, format compliance, and RAG quality (via RAGAS-like evaluator).
- Tool interface abstraction (`Tools`) supporting search tools (Wikipedia and web).
- LoRA + quantization options for efficient fine-tuning.

**Primary runtime components:**
- `src/models/model.py` — generation loop with tool interruptions.
- `src/models/reward*.py` — reward functions for RL.
- `src/train.py` — GRPO/DAPO training pipeline.
- `service/chat_server.py` — FastAPI inference server.

## Value to BestBox

1. **Better tool-use policy:** RL-trained decision-making for when and how to call RAG/search tools can reduce hallucinations and improve precision on knowledge-heavy questions.
2. **Structured reasoning traces:** The tag-based format is compatible with BestBox’s multi-agent prompts and could enable UI enhancements (e.g., showing search steps or citations).
3. **Domain tuning:** LoRA fine-tuning on enterprise data (ERP/CRM/IT Ops/OA) can align tool usage to BestBox-specific workflows.
4. **Quality evaluation:** The RAG reward evaluation loop provides a reusable framework for benchmarking retrieval quality against enterprise datasets.
5. **Smaller policy model option:** A smaller “policy” model can be used for tool selection, with BestBox’s larger model used for final response synthesis.

## Workability Assessment

**Feasibility: Partially workable (recommended as a staged integration).**

**Pros:**
- Compatible with BestBox’s RAG architecture (Qdrant + BGE-M3 + reranker).
- LoRA path aligns with BestBox’s existing model strategy.
- The tool schema can be adapted to BestBox’s tool APIs.

**Gaps / Risks:**
- Training scripts assume CUDA + Deepspeed; ROCm support needs validation.
- Reward functions rely on external LLM eval endpoints; BestBox needs a local evaluation model or a sandboxed evaluator.
- Tool definitions are currently Wikipedia-centric; must be replaced with BestBox tools (ERP/CRM/IT Ops/OA + `search_knowledge_base`).
- The current repo uses direct token-level formatting constraints; BestBox prompts need alignment.

**Conclusion:**
- **Workable** if approached as a **pilot integration**: adopt the policy-format and reward logic first, then expand to full RL training when infrastructure is validated.

## Proposed Integration Design

### 1) Agentic Policy Layer
A “policy model” decides when to retrieve and which tool to call; BestBox’s main model handles final response generation.

**Flow:**
```
User Query
  → Policy Model (Agentic-RAG-R1 style tags)
  → BestBox tool execution (search_knowledge_base / ERP / CRM / IT Ops / OA)
  → Retrieved evidence
  → Final response by BestBox main model
```

### 2) Tool Interface Adapter
Replace Agentic-RAG-R1 `Tools` with BestBox tool API. The tags remain consistent:
- `<search>` blocks map to `search_knowledge_base`
- `<tool>` or tag-enriched variants map to domain tools

### 3) Reward Shaping (Offline)
Use RAG quality scoring (e.g., relevance, factuality) to score training rollouts. Replace external API evaluation with local evaluator.

### 4) Dataset Strategy
- Use existing BestBox demo documents.
- Generate synthetic Q&A pairs by prompting LLMs with domain docs.
- Label expected tool usage and search queries.

## Implementation Plan

### Phase 0 — Feasibility & Environment (1–2 days)
1. Validate PyTorch + Deepspeed support on target hardware.
2. Run a small GRPO training job on a lightweight model (3B) in a sandbox environment.
3. Decide on a local evaluation model (for reward computation).

### Phase 1 — Adapter Layer (2–3 days)
1. Implement a BestBox tool adapter compatible with Agentic-RAG-R1’s tag format.
2. Define a prompt/response format aligned with BestBox tool calling.
3. Create a minimal policy inference service in BestBox (FastAPI or in-process tool).

### Phase 2 — Dataset & Rewards (2–4 days)
1. Build a dataset generator: query → tool invocation → expected answer.
2. Integrate a local evaluation pipeline for correctness + RAG quality scoring.
3. Validate reward outputs on a small test set.

### Phase 3 — Training & LoRA (3–5 days)
1. Fine-tune the policy model with LoRA on BestBox data.
2. Run evaluation on test scenarios (ERP/CRM/IT Ops/OA).
3. Track improvements in tool usage and retrieval precision.

### Phase 4 — Runtime Integration (2–3 days)
1. Add policy model routing into BestBox agent pipeline.
2. Enable optional fallback to baseline (non-agentic) mode.
3. Add logging and evaluation metrics.

## Implementation Details

### New Components in BestBox

**1) Tool Adapter**
- File: `src/tools/agentic_rag_tools.py`
- Maps `<search>` and `<tool>` tags to BestBox tool execution

**2) Policy Service (Optional)**
- File: `services/agentic_policy/server.py`
- Runs the policy model for tool-selection inference

**3) Dataset Generator**
- File: `scripts/build_agentic_rag_dataset.py`
- Generates prompts + expected tool use

**4) Reward Evaluator**
- File: `services/agentic_policy/reward.py`
- Local evaluator: correctness + RAG quality (without external API)

**5) Integration Hooks**
- File: `src/agents/graph.py`
- Adds policy routing before tool execution

### Configuration
Add environment keys:
- `AGENTIC_POLICY_MODEL_PATH`
- `AGENTIC_POLICY_DEVICE`
- `AGENTIC_POLICY_ENABLED=true/false`

### Evaluation Metrics
- Tool usage accuracy (% correct tool calls)
- Retrieval precision@k
- End-to-end answer quality (LLM judge + human spot-check)
- Latency overhead vs baseline

## Dependencies

- `peft`, `accelerate`, `deepspeed` (training only)
- `transformers`, `torch` (runtime)
- Optional: `ragas` or custom evaluation module

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ROCm training instability | Medium | Run training on CUDA or reduce to SFT/LoRA only |
| Evaluation latency | Medium | Cache reward model outputs; use smaller judge model |
| Tool-tag mismatch | Medium | Enforce strict parsing + unit tests |
| Dataset quality | High | Start with small curated set; iterate |

## Success Criteria

- ≥15% improvement in tool usage accuracy over baseline prompts.
- ≥10% improvement in retrieval precision@5 on internal test set.
- No regression in end-to-end answer quality.
- Policy routing overhead < 300ms P95.

## Next Actions

1. Confirm target hardware for training and evaluation.
2. Create a small pilot dataset (20–50 prompts per domain).
3. Prototype the tool adapter and policy inference wrapper.
4. Decide on a local evaluation model.

---

If approved, begin Phase 0 with a lightweight pilot experiment.
