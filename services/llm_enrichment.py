"""
LLM-powered knowledge enrichment module.

Sends document chunks to the local Qwen LLM (OpenAI-compatible API) and
extracts structured knowledge: summaries, key concepts, Q&A pairs, and
domain-specific metadata (mold defect fields for the mold domain).

The enriched output is used to improve RAG retrieval quality by augmenting
vector store entries with LLM-generated searchable text and metadata.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QAPair:
    """A single question-answer pair extracted from a document chunk."""

    question: str
    answer: str


@dataclass
class EnrichmentResult:
    """Structured knowledge extracted from a document chunk by the LLM."""

    summary: str = ""
    key_concepts: List[str] = field(default_factory=list)
    qa_pairs: List[QAPair] = field(default_factory=list)
    domain_terms: List[str] = field(default_factory=list)
    defect_type: str = ""
    severity: str = ""
    root_cause_category: str = ""
    mold_components: List[str] = field(default_factory=list)
    corrective_actions: List[str] = field(default_factory=list)
    applicable_materials: List[str] = field(default_factory=list)

    def to_enriched_text(self) -> str:
        """Concatenate summary + Q&A pairs + key concepts into searchable text."""
        parts: List[str] = []

        if self.summary:
            parts.append(self.summary)

        for qa in self.qa_pairs:
            parts.append(f"Q: {qa.question}")
            parts.append(f"A: {qa.answer}")

        if self.key_concepts:
            parts.append("Key concepts: " + ", ".join(self.key_concepts))

        if self.domain_terms:
            parts.append("Domain terms: " + ", ".join(self.domain_terms))

        return "\n".join(parts)

    def to_metadata(self) -> Dict[str, Any]:
        """Return dict of non-empty metadata fields for Qdrant payload."""
        meta: Dict[str, Any] = {}

        if self.summary:
            meta["summary"] = self.summary
        if self.key_concepts:
            meta["key_concepts"] = self.key_concepts
        if self.domain_terms:
            meta["domain_terms"] = self.domain_terms
        if self.defect_type:
            meta["defect_type"] = self.defect_type
        if self.severity:
            meta["severity"] = self.severity
        if self.root_cause_category:
            meta["root_cause_category"] = self.root_cause_category
        if self.mold_components:
            meta["mold_components"] = self.mold_components
        if self.corrective_actions:
            meta["corrective_actions"] = self.corrective_actions
        if self.applicable_materials:
            meta["applicable_materials"] = self.applicable_materials
        if self.qa_pairs:
            meta["qa_pairs"] = [
                {"question": qa.question, "answer": qa.answer}
                for qa in self.qa_pairs
            ]

        return meta


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

MOLD_SYSTEM_PROMPT = """\
You are a mold manufacturing knowledge extraction assistant.
Given a document chunk, extract the following fields as a JSON object:

{
  "summary": "A concise 1-2 sentence summary of the content.",
  "key_concepts": ["list", "of", "key", "concepts"],
  "qa_pairs": [{"question": "...", "answer": "..."}],
  "domain_terms": ["technical", "terms", "found"],
  "defect_type": "type of mold defect (e.g. flash, short shot, sink mark)",
  "severity": "high | medium | low",
  "root_cause_category": "category of root cause (e.g. process parameter, mold design, material)",
  "mold_components": ["affected", "mold", "components"],
  "corrective_actions": ["list", "of", "corrective", "actions"],
  "applicable_materials": ["list", "of", "materials"]
}

Rules:
- Return ONLY valid JSON, no extra text.
- If a field is not applicable, use an empty string "" for strings or [] for lists.
- Generate 1-3 Q&A pairs that capture the most important knowledge.
- Use domain-specific terminology from the mold manufacturing industry.
"""

GENERIC_SYSTEM_PROMPT = """\
You are a knowledge extraction assistant.
Given a document chunk, extract the following fields as a JSON object:

{
  "summary": "A concise 1-2 sentence summary of the content.",
  "key_concepts": ["list", "of", "key", "concepts"],
  "qa_pairs": [{"question": "...", "answer": "..."}],
  "domain_terms": ["technical", "terms", "found"],
  "defect_type": "",
  "severity": "",
  "root_cause_category": "",
  "mold_components": [],
  "corrective_actions": [],
  "applicable_materials": []
}

Rules:
- Return ONLY valid JSON, no extra text.
- If a field is not applicable, use an empty string "" for strings or [] for lists.
- Generate 1-3 Q&A pairs that capture the most important knowledge.
- Leave mold-specific fields (defect_type, severity, root_cause_category, mold_components, corrective_actions, applicable_materials) empty.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_system_prompt(domain: str) -> str:
    """Return the appropriate system prompt based on domain."""
    if domain == "mold":
        return MOLD_SYSTEM_PROMPT
    return GENERIC_SYSTEM_PROMPT


def _parse_llm_json(raw: str) -> Optional[Dict]:
    """Strip markdown fencing (```json ... ```) and parse JSON.

    Returns None if parsing fails.
    """
    text = raw.strip()

    # Strip markdown code fencing if present
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse LLM JSON response: %s", e)
        return None


def _dict_to_result(data: Dict) -> EnrichmentResult:
    """Convert a parsed dict to an EnrichmentResult dataclass."""
    qa_pairs = []
    for qa in data.get("qa_pairs", []):
        if isinstance(qa, dict) and "question" in qa and "answer" in qa:
            qa_pairs.append(QAPair(question=qa["question"], answer=qa["answer"]))

    return EnrichmentResult(
        summary=data.get("summary", ""),
        key_concepts=data.get("key_concepts", []),
        qa_pairs=qa_pairs,
        domain_terms=data.get("domain_terms", []),
        defect_type=data.get("defect_type", ""),
        severity=data.get("severity", ""),
        root_cause_category=data.get("root_cause_category", ""),
        mold_components=data.get("mold_components", []),
        corrective_actions=data.get("corrective_actions", []),
        applicable_materials=data.get("applicable_materials", []),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def enrich_chunk(
    text: str, domain: str = "mold"
) -> Optional[EnrichmentResult]:
    """Call the local LLM to extract structured knowledge from a text chunk.

    Args:
        text: The document chunk text to enrich.
        domain: Domain hint — "mold" uses the mold-specific prompt,
                anything else uses the generic prompt.

    Returns:
        An EnrichmentResult on success, or None on any failure
        (connection error, bad JSON, etc.).
    """
    system_prompt = _get_system_prompt(domain)
    url = f"{LLM_BASE_URL}/chat/completions"

    payload = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Extract knowledge from this text:\n\n{text}",
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        parsed = _parse_llm_json(content)
        if parsed is None:
            return None

        return _dict_to_result(parsed)

    except Exception as e:
        logger.warning("LLM enrichment failed: %s", e)
        return None
