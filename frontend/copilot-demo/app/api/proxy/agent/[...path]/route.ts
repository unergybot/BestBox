import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const runtime = "nodejs";

function getAgentApiBase(): string {
  const explicit = process.env.OPENAI_BASE_URL || process.env.NEXT_PUBLIC_AGENT_API_URL || process.env.AGENT_API_URL;
  if (explicit) {
    const withoutVersion = explicit.replace(/\/v1\/?$/, "");
    return withoutVersion.replace(/\/$/, "");
  }
  const port = process.env.NEXT_PUBLIC_AGENT_API_PORT || process.env.AGENT_API_PORT || "8000";
  return `http://127.0.0.1:${port}`;
}

async function proxyAgentRequest(req: NextRequest, pathSegments: Array<string> | undefined) {
  const path = pathSegments?.join("/") ?? "";
  const incomingUrl = new URL(req.url);
  const base = getAgentApiBase();
  const targetUrl = new URL(`${base}/${path}`);

  // Preserve query params, but also ensure tool-results are scoped to this browser session.
  // This prevents global-latest cross-talk and also makes results fetchable even if the
  // assistant content strips hidden tags.
  const query = new URLSearchParams(incomingUrl.search);
  const cookieSession = req.cookies.get("bbx_session")?.value;
  const isToolResults = path === "v1/tool-results/latest" || path === "v1/tool-results/clear";
  if (isToolResults && cookieSession && !query.has("session_id")) {
    query.set("session_id", `ui-${cookieSession}`);
  }
  targetUrl.search = query.toString();

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const response = await fetch(targetUrl, {
    method: req.method,
    headers,
    body: hasBody ? req.body : undefined,
    redirect: "manual",
    ...(hasBody ? { duplex: "half" } : {}),
  });

  return new NextResponse(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

// Next.js 16+ requires params to be awaited
type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}

export async function POST(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}

export async function PUT(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}

export async function PATCH(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}

export async function DELETE(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}

export async function OPTIONS(req: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyAgentRequest(req, params.path);
}
