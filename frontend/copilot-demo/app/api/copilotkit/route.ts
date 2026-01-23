import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  LangChainAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";
import { ChatOpenAI } from "@langchain/openai";

// Agent API URL - our LangGraph agent system
const AGENT_API_URL = "http://127.0.0.1:8000/v1/chat/completions";

// LLM base URL for llama-server
const LLM_BASE_URL = process.env.OPENAI_BASE_URL || "http://127.0.0.1:8080/v1";
console.log("CopilotKit LLM baseURL:", LLM_BASE_URL);

// Create LangChain ChatOpenAI model pointing to local llama-server
// This uses the standard /v1/chat/completions endpoint (not /v1/responses)
const model = new ChatOpenAI({
  modelName: "qwen2.5-14b",
  temperature: 0.7,
  configuration: {
    baseURL: LLM_BASE_URL,
    apiKey: process.env.OPENAI_API_KEY || "not-needed",
  },
});

// Use LangChainAdapter which properly handles local OpenAI-compatible servers
// It uses LangChain's ChatOpenAI which calls /v1/chat/completions
const serviceAdapter = new LangChainAdapter({
  chainFn: async ({ messages, tools }) => {
    // Filter out messages with undefined content and ensure all have proper format
    const validMessages = messages
      .map(m => {
        // If message has undefined/null content, set it to empty string
        if (m.content === undefined || m.content === null) {
          return { ...m, content: "" };
        }
        return m;
      })
      .filter(m => {
        // After normalizing, skip messages with truly empty content unless they have tool_calls
        if (typeof m.content === 'string' && m.content.trim() === '') {
          // Keep the message if it has tool_calls (for tool use messages)
          return !!(m as any).tool_calls || !!(m as any).tool_call_id;
        }
        return true;
      });

    // Ensure we have at least one message
    if (validMessages.length === 0) {
      // Return a simple message if no valid messages
      return model.stream([{ role: "user", content: "Hello" } as any]);
    }

    // If tools are available, bind them to the model
    if (tools && tools.length > 0) {
      return model.bindTools(tools).stream(validMessages);
    }
    // Otherwise just stream the messages
    return model.stream(validMessages);
  },
}) as LangChainAdapter & { provider: string; model: string };

// Add provider and model properties required by CopilotKit's BuiltInAgent
// This prevents the "Unknown provider undefined" error
serviceAdapter.provider = "openai";
serviceAdapter.model = "qwen2.5-14b";

async function callAgentApi(messages: any[]): Promise<string> {
  try {
    const response = await fetch(AGENT_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map((m: any) => ({ role: m.role, content: m.content })),
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
      handler: async ({ query }: { query: string }) => {
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
