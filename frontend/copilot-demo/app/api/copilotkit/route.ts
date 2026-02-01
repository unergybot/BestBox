import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// Agent API URL - configured via OPENAI_BASE_URL environment variable
// CopilotKit's OpenAIAdapter will create its own OpenAI client using:
// - OPENAI_BASE_URL (points to our LangGraph backend)
// - OPENAI_API_KEY (placeholder for local LLM)
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
          agents: ["Router", "ERP", "CRM", "IT Ops", "OA"],
          status: "connected",
          model: "Qwen3-4B-Instruct",
          backend: "vLLM (CUDA)",
          gpu: "NVIDIA RTX 3080 + Tesla P100",
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
