"use client";

import { useState } from "react";
import ReasoningTrace from "@/components/ReasoningTrace";

interface ReasoningStep {
  type: "think" | "act" | "observe" | "answer";
  content: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  timestamp: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  reasoning_trace?: ReasoningStep[];
}

export default function ReactTestPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:8000/chat/react", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...messages, userMessage].map((m) => ({
            role: m.role,
            content: m.content,
          })),
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.session_id) {
        setSessionId(data.session_id);
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: data.choices[0].message.content,
        reasoning_trace: data.reasoning_trace,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">ReAct Test Page</h1>
            <p className="text-sm text-gray-500 mt-1">
              Test the ReAct reasoning endpoint with visible Think → Act → Observe → Answer traces
            </p>
          </div>
          <div className="flex items-center gap-4">
            {sessionId && (
              <span className="text-xs text-gray-500">
                Session: <code className="bg-gray-100 px-2 py-1 rounded">{sessionId.slice(0, 8)}...</code>
              </span>
            )}
            <button
              onClick={clearChat}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
            >
              Clear
            </button>
            <a
              href="/admin"
              className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              Admin →
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-6 space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-sm p-4 space-y-4 min-h-[400px]">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 py-12">
              <p>Send a message to test ReAct reasoning</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <button
                  onClick={() => setInput("What is the inventory level for WH-001?")}
                  className="px-3 py-1 text-sm bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
                >
                  Inventory for WH-001
                </button>
                <button
                  onClick={() => setInput("Show me the financial summary for this quarter")}
                  className="px-3 py-1 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100"
                >
                  Financial summary
                </button>
                <button
                  onClick={() => setInput("How do I reset a user password?")}
                  className="px-3 py-1 text-sm bg-purple-50 text-purple-700 rounded hover:bg-purple-100"
                >
                  IT Ops help
                </button>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded ${
                    msg.role === "user"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-green-100 text-green-700"
                  }`}
                >
                  {msg.role}
                </span>
              </div>
              <div className="text-gray-800 whitespace-pre-wrap mb-3">{msg.content}</div>
              {msg.reasoning_trace && msg.reasoning_trace.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <div className="text-xs font-medium text-gray-500 mb-2">Reasoning Trace</div>
                  <ReasoningTrace steps={msg.reasoning_trace} />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
              <div className="flex items-center gap-2 text-gray-600">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-400 border-t-transparent" />
                <span>ReAct agent is reasoning...</span>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Ask the ReAct agent..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
          <strong>How it works:</strong> This page calls <code className="bg-blue-100 px-1 rounded">/chat/react</code>{" "}
          which uses the ReAct (Reasoning + Acting) pattern. The agent will Think about the query,
          Act by calling tools, Observe the results, and repeat until it can Answer.
        </div>
      </main>
    </div>
  );
}
