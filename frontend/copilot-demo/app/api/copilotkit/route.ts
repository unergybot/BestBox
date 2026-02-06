import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import OpenAI from "openai";

function getAgentApiBaseUrl(): string {
  const raw = process.env.OPENAI_BASE_URL;
  if (!raw) {
    throw new Error("OPENAI_BASE_URL is not set");
  }
  return raw.replace(/\/$/, "").replace(/\/v1\/?$/, "");
}

function getOrCreateUiSessionId(req: NextRequest): string {
  const existing = req.cookies.get("bbx_session")?.value;
  if (existing && existing.length >= 8) return existing;
  return crypto.randomUUID();
}

console.log("OPENAI_BASE_URL:", process.env.OPENAI_BASE_URL);

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
  const uiSessionId = getOrCreateUiSessionId(req);
  const baseURL = getAgentApiBaseUrl();

  // Send the raw cookie value; the Python backend adds the "ui-" prefix
  // to match what the proxy injects on tool-results fetches.
  const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY || "local",
    baseURL,
    defaultHeaders: {
      "X-BBX-Session": uiSessionId,
    },
  });

  const serviceAdapter = new OpenAIAdapter({
    model: "bestbox-agent",
    openai,
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  const response = await handleRequest(req);
  const nextResponse = new NextResponse(response.body, {
    status: response.status,
    headers: response.headers,
  });
  nextResponse.cookies.set("bbx_session", uiSessionId, {
    path: "/",
    sameSite: "lax",
  });
  return nextResponse;
};
