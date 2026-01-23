#!/bin/bash
# Patch @copilotkitnext/agent to work with llama-server
# llama-server doesn't support:
# 1. OpenAI Responses API (/v1/responses) - must use Chat Completions API (/v1/chat/completions)
# 2. z.any() JSON schemas - must use z.object({}).passthrough() for valid schemas

AGENT_DIR="node_modules/@copilotkitnext/agent/dist"

if [ -d "$AGENT_DIR" ]; then
  echo "Patching @copilotkitnext/agent for llama-server compatibility..."
  
  for file in "$AGENT_DIR/index.mjs" "$AGENT_DIR/index.js"; do
    if [ -f "$file" ]; then
      # Patch 1: Use chat completions API instead of responses API
      sed -i 's/return openai(model);/return openai.chat(model);/' "$file"
      
      # Patch 2: Replace z.any() with z.object({}).passthrough() for valid JSON schemas
      sed -i 's/z\.any()\.describe/z.object({}).passthrough().describe/g' "$file"
      
      # Patch 3: Replace z.any().optional() with z.object({}).passthrough().optional()
      sed -i 's/z\.any()\.optional()\.describe/z.object({}).passthrough().optional().describe/g' "$file"
      
      echo "  ✓ Patched $(basename $file)"
    fi
  done
  
  echo "✅ Patch complete! CopilotKit is now compatible with llama-server"
else
  echo "⚠️ @copilotkitnext/agent not found. Run 'npm install' first."
fi
