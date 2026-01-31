import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

const AGENT_API_URL = process.env.OPENAI_BASE_URL || "http://localhost:8002";
const API_KEY = process.env.OPENAI_API_KEY || "sk-no-key-required";

// Create a custom service adapter that forwards to our Agent API
class BestBoxAgentAdapter extends OpenAIAdapter {
  constructor() {
    super({
      url: `${AGENT_API_URL}/v1/chat/completions`,
      apiKey: API_KEY,
    });
  }
}

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
          model: "Qwen/Qwen3-4B-Instruct",
          backend: "vLLM",
          gpu: "RTX 3080 + P100",
        };
      },
    },
  ],
  // Define the agents that CopilotKit should expose
  agents: [
    {
      name: "default",
      description: "BestBox Enterprise Agent - handles ERP, CRM, IT Ops, and OA queries",
    },
    {
      name: "erp_agent",
      description: "ERP Agent - handles purchase orders, invoices, inventory, and financial reporting",
    },
    {
      name: "crm_agent",
      description: "CRM Agent - handles leads, quotations, opportunities, and sales activities",
    },
    {
      name: "it_ops_agent",
      description: "IT Ops Agent - handles tickets, knowledge base, and system diagnostics",
    },
    {
      name: "oa_agent",
      description: "OA Agent - handles leave approvals, meetings, and document workflows",
    },
  ],
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new BestBoxAgentAdapter(),
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};

export const GET = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new BestBoxAgentAdapter(),
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};

export const OPTIONS = async () => {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
};
