import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  LangChainAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";
import { ChatOpenAI } from "@langchain/openai";

// Agent API URL - our LangGraph agent system (PRIMARY endpoint for all queries)
const AGENT_API_URL = process.env.AGENT_API_URL || "http://127.0.0.1:8000";
console.log("CopilotKit Agent API URL:", AGENT_API_URL);

// Create LangChain ChatOpenAI model pointing to our Agent API
// This routes through our LangGraph system which handles agent routing and tools
const model = new ChatOpenAI({
  modelName: "bestbox-agent",
  temperature: 0.7,
  configuration: {
    baseURL: `${AGENT_API_URL}/v1`,  // Points to our agent API, not llama-server
    apiKey: "not-needed",
  },
});

// Use LangChainAdapter with our agent API
const serviceAdapter = new LangChainAdapter({
  chainFn: async ({ messages, tools }) => {
    // Normalize messages - ensure all have content defined
    const validMessages = messages.map(m => {
      // If message has undefined/null content, set it to empty string
      if (m.content === undefined || m.content === null) {
        return { ...m, content: "" };
      }
      return m;
    });

    // Ensure we have at least one message
    if (validMessages.length === 0) {
      return model.stream([{ role: "user", content: "Hello" } as any]);
    }

    // Helper to ensure chunks have content (never undefined)
    async function* safeStream(streamPromise: Promise<any>) {
      const stream = await streamPromise;
      for await (const chunk of stream) {
        // Ensure content is always defined
        if (chunk.content === undefined || chunk.content === null) {
          chunk.content = "";
        }
        yield chunk;
      }
    }

    // Stream messages through our agent API (which handles tools internally)
    // We don't bind tools here - our LangGraph agents have their own tools
    return safeStream(model.stream(validMessages)) as any;
  },
}) as LangChainAdapter & { provider: string; model: string };

// Add provider and model properties required by CopilotKit
serviceAdapter.provider = "openai";
serviceAdapter.model = "bestbox-agent";

// Direct API call function for explicit agent queries
async function callAgentApi(messages: any[]): Promise<string> {
  try {
    const response = await fetch(`${AGENT_API_URL}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map((m: any) => ({
          role: m.role,
          content: m.content || ""  // Ensure content is never undefined
        })),
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Agent API error: ${error}`);
    }

    const data = await response.json();
    return data.choices[0].message.content || "";
  } catch (error) {
    console.error("Failed to call agent API:", error);
    throw error;
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
