import {
  CopilotRuntime,
  LangChainAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { ChatOpenAI } from "@langchain/openai";
import { NextRequest } from "next/server";

// Connect to local llama-server using LangChain (better support for custom endpoints)
// Connect to local LangGraph Agent API
const model = new ChatOpenAI({
  modelName: "BestBox-Agent",
  temperature: 0,
  configuration: {
    baseURL: "http://127.0.0.1:8000/v1", // Point to Python Agent API
    apiKey: "not-needed", 
  },
});

const serviceAdapter = new LangChainAdapter({
  chainFn: async ({ messages, tools }) => {
    // We ignore client-side tools and just call our agent
    // Note: We use invoke (blocking) instead of stream because our Agent API is currently blocking
    return model.invoke(messages);
  },
});

// Define actions (tools) for the agent
// Note: Verification tools are now handled by the Python Agent.
// We keep this runtime minimal.
const runtime = new CopilotRuntime({
  actions: [
    {
      name: "get_system_info",
      description: "Get information about the BestBox system",
      parameters: [],
      handler: async () => {
        return {
          system: "BestBox Enterprise Agentic Demo",
          framework: "LangGraph (Python)",
          agents: ["Router", "ERP", "CRM", "IT Ops", "OA"],
          status: "connected"
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
