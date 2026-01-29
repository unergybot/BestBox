"""
Context Manager for BestBox Agents

Handles message truncation, token estimation, and context window management
to prevent "Context size exceeded" errors and reduce latency.

Key optimizations:
1. Sliding window: Keep recent messages, drop old ones
2. Token estimation: Rough estimate to stay within limits
3. Message summarization: Compress tool results
4. System prompt caching: Avoid repetition
"""

from typing import List, Tuple, Optional
from langchain_core.messages import (
    BaseMessage, 
    HumanMessage, 
    AIMessage, 
    SystemMessage,
    ToolMessage
)
import tiktoken
import logging

logger = logging.getLogger(__name__)

# Configuration
MAX_CONTEXT_TOKENS = 3500  # Leave headroom for response (4096 - 600)
MAX_MESSAGES = 10  # Maximum messages in context (excluding system)
MAX_TOOL_RESULT_CHARS = 1500  # Truncate long tool results
CHARS_PER_TOKEN_ESTIMATE = 4  # Rough estimate for non-tiktoken


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Uses character-based estimation for speed.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Rough estimate: ~4 chars per token for English
    # Qwen uses similar tokenization to GPT models
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


def estimate_message_tokens(message: BaseMessage) -> int:
    """
    Estimate tokens for a single message including role overhead.
    
    Args:
        message: LangChain message object
        
    Returns:
        Estimated token count
    """
    content = message.content if isinstance(message.content, str) else str(message.content)
    
    # Add overhead for role tokens and formatting
    overhead = 4  # role + structural tokens
    
    # Tool calls add extra tokens
    if isinstance(message, AIMessage) and message.tool_calls:
        overhead += len(str(message.tool_calls)) // CHARS_PER_TOKEN_ESTIMATE
    
    return estimate_tokens(content) + overhead


def truncate_tool_result(content: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """
    Truncate long tool results to reduce context size.
    
    Args:
        content: Tool result content
        max_chars: Maximum characters to keep
        
    Returns:
        Truncated content with indicator if truncated
    """
    if len(content) <= max_chars:
        return content
    
    # Keep first and last parts for context
    half = max_chars // 2 - 20
    truncated = f"{content[:half]}\n\n[... {len(content) - max_chars} chars truncated for brevity ...]\n\n{content[-half:]}"
    return truncated


def apply_sliding_window(
    messages: List[BaseMessage],
    max_tokens: int = MAX_CONTEXT_TOKENS,
    max_messages: int = MAX_MESSAGES,
    keep_system: bool = True
) -> List[BaseMessage]:
    """
    Apply sliding window to keep messages within context limits.
    
    Strategy:
    1. Always keep system message (if any)
    2. Always keep the last user message
    3. Drop oldest messages first to fit within limits
    
    Args:
        messages: List of messages to process
        max_tokens: Maximum tokens to allow
        max_messages: Maximum number of messages
        keep_system: Whether to preserve system messages
        
    Returns:
        Truncated list of messages
    """
    if not messages:
        return messages
    
    # Separate system messages from others
    system_messages = []
    other_messages = []
    
    for msg in messages:
        if isinstance(msg, SystemMessage) and keep_system:
            system_messages.append(msg)
        else:
            other_messages.append(msg)
    
    # Calculate system message token usage
    system_tokens = sum(estimate_message_tokens(m) for m in system_messages)
    remaining_tokens = max_tokens - system_tokens
    
    if remaining_tokens < 200:
        logger.warning("System prompts consume too many tokens, consider reducing them")
        remaining_tokens = 500  # Minimum for conversation
    
    # Apply message count limit first
    if len(other_messages) > max_messages:
        # Keep most recent messages
        dropped = len(other_messages) - max_messages
        other_messages = other_messages[dropped:]
        logger.info(f"Dropped {dropped} old messages to fit limit")
    
    # Now fit within token limit
    result_messages = []
    current_tokens = 0
    
    # Process from newest to oldest
    for msg in reversed(other_messages):
        msg_tokens = estimate_message_tokens(msg)
        
        # Truncate tool results if needed
        if isinstance(msg, ToolMessage) and len(msg.content or "") > MAX_TOOL_RESULT_CHARS:
            msg = ToolMessage(
                content=truncate_tool_result(msg.content),
                tool_call_id=msg.tool_call_id,
                name=getattr(msg, 'name', None)
            )
            msg_tokens = estimate_message_tokens(msg)
        
        if current_tokens + msg_tokens <= remaining_tokens:
            result_messages.insert(0, msg)
            current_tokens += msg_tokens
        else:
            # Can't fit more messages
            break
    
    # Always include at least the last message
    if not result_messages and other_messages:
        result_messages = [other_messages[-1]]
    
    # Combine: system + filtered messages
    final_messages = system_messages + result_messages
    
    dropped_count = len(messages) - len(final_messages)
    if dropped_count > 0:
        logger.info(f"Context management: kept {len(final_messages)} of {len(messages)} messages (~{current_tokens + system_tokens} tokens)")
    
    return final_messages


def prepare_messages_for_agent(
    messages: List[BaseMessage],
    system_prompt: str,
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> List:
    """
    Prepare messages for agent invocation with context management.
    
    Args:
        messages: Conversation history
        system_prompt: System prompt for the agent
        max_tokens: Maximum tokens for context
        
    Returns:
        Formatted message list ready for LLM
    """
    # Estimate system prompt tokens
    system_tokens = estimate_tokens(system_prompt) + 10  # overhead
    
    # Apply sliding window to messages
    remaining_tokens = max_tokens - system_tokens
    managed_messages = apply_sliding_window(
        messages, 
        max_tokens=remaining_tokens,
        keep_system=False  # We add our own system message
    )
    
    # Return as tuple format for LangChain
    return [("system", system_prompt)] + managed_messages


def get_context_stats(messages: List[BaseMessage]) -> dict:
    """
    Get statistics about current context usage.
    
    Args:
        messages: List of messages
        
    Returns:
        Dict with context statistics
    """
    total_tokens = sum(estimate_message_tokens(m) for m in messages)
    
    return {
        "message_count": len(messages),
        "estimated_tokens": total_tokens,
        "remaining_tokens": MAX_CONTEXT_TOKENS - total_tokens,
        "at_risk": total_tokens > MAX_CONTEXT_TOKENS * 0.8,
        "exceeded": total_tokens > MAX_CONTEXT_TOKENS
    }
