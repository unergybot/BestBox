import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// Hardware/model configuration - set via environment for multi-GPU support
const LLM_MODEL = process.env.LLM_MODEL || "Qwen3-4B-Instruct";
const LLM_BACKEND = process.env.LLM_BACKEND || "vLLM";
const GPU_NAME = process.env.GPU_NAME || "RTX 3080 / P100";

console.log("OPENAI_BASE_URL:", process.env.OPENAI_BASE_URL);

// Use OpenAIAdapter - it will use env vars to create the client
// Do NOT pass a custom openai client to avoid version mismatch issues
const serviceAdapter = new OpenAIAdapter({
  model: "bestbox-agent",
});

const runtime = new CopilotRuntime({
  actions: [
    {
      name: "get_system_info",
      description: "Get information about the BestBox system",
      parameters: [],
      handler: async () => {
        return {
          system: "BestBox Enterprise Agent",
          framework: "LangGraph (Python)",
          agents: ["Router", "ERP", "CRM", "IT Ops", "OA", "Mold"],
          status: "connected",
          model: LLM_MODEL,
          backend: LLM_BACKEND,
          gpu: GPU_NAME,
        };
      },
    },
  ],
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
