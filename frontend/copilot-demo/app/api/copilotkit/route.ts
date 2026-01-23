import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  LangChainAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";
import { ChatOpenAI } from "@langchain/openai";

// Agent API URL - our LangGraph agent system
const AGENT_API_URL = "http://127.0.0.1:8000/v1/chat/completions";

// Configure LangChain model to use local llama-server
const model = new ChatOpenAI({
  modelName: "qwen2.5-14b",
  temperature: 0.7,
  configuration: {
    baseURL: process.env.OPENAI_BASE_URL || "http://127.0.0.1:8080/v1",
    apiKey: process.env.OPENAI_API_KEY || "not-needed",
  },
});

console.log("CopilotKit LangChain baseURL:", process.env.OPENAI_BASE_URL || "http://127.0.0.1:8080/v1");

// Create LangChainAdapter without provider/model properties to prevent BuiltInAgent creation
const serviceAdapter = new LangChainAdapter({
  chainFn: async ({ messages, tools }) => {
    return model.bindTools(tools).stream(messages);
  },
});

async function callAgentApi(messages: any[]): Promise<string> {
  try {
    const response = await fetch(AGENT_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map(m => ({ role: m.role, content: m.content })),
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Agent API error: ${error}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  } catch (error) {
    console.error("Failed to call agent API:", error);
    throw error;
  }
}

const runtime = new CopilotRuntime({
  actions: [
    {
      name: "query_bestbox_agent",
      description: "Send a query to the BestBox LangGraph agent for ERP, CRM, IT Ops, or OA tasks. Use this for complex business queries that need agent routing.",
      parameters: [
        {
          name: "query",
          type: "string",
          description: "The user's query or task for the agent system",
          required: true,
        },
      ],
      handler: async ({ query }) => {
        const messages = [{ role: "user", content: query }];
        return await callAgentApi(messages);
      },
    },
    {
      name: "get_system_info",
      description: "Get information about the BestBox system",
      parameters: [],
      handler: async () => {
        return {
          system: "BestBox Enterprise Agentic Demo",
          framework: "LangGraph (Python)",
          agents: ["Router", "ERP", "CRM", "IT Ops", "OA"],
          status: "connected",
          model: "Qwen2.5-14B-Instruct",
          backend: "llama.cpp (Vulkan)",
          gpu: "AMD Radeon 8060S",
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
