"use client";

import React from "react";

interface ReasoningStep {
  type: "think" | "act" | "observe" | "answer";
  content: string;
  tool_name?: string | null;
  tool_args?: Record<string, unknown> | null;
  timestamp: number;
}

interface ReasoningTraceProps {
  steps: ReasoningStep[];
  isStreaming?: boolean;
}

function formatArgs(args?: Record<string, unknown> | null): string {
  if (!args || Object.keys(args).length === 0) return "";
  return JSON.stringify(args).slice(0, 120);
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function ReasoningTrace({ steps, isStreaming = false }: ReasoningTraceProps) {
  if (!steps || steps.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic">
        No reasoning trace yet.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div
          key={`${step.type}-${step.timestamp}-${i}`}
          className={`rounded-md border p-3 text-sm bg-white shadow-sm ${
            step.type === "answer" ? "border-green-200" : "border-gray-200"
          }`}
        >
          {step.type === "think" && (
            <div className="flex items-start gap-2">
              <span>🤔</span>
              <span>Thinking: {step.content}</span>
            </div>
          )}
          {step.type === "act" && (
            <div className="flex items-start gap-2">
              <span>🔧</span>
              <span>
                Action: {step.tool_name}
                {step.tool_args ? `(${formatArgs(step.tool_args)})` : ""}
              </span>
            </div>
          )}
          {step.type === "observe" && (
            <div className="flex items-start gap-2">
              <span>📊</span>
              <span>Observation: {truncate(step.content, 200)}</span>
            </div>
          )}
          {step.type === "answer" && (
            <div className="flex items-start gap-2">
              <span>💡</span>
              <span>Answer: {step.content}</span>
            </div>
          )}
        </div>
      ))}
      {isStreaming && (
        <div className="text-xs text-gray-500">Streaming reasoning...</div>
      )}
    </div>
  );
}

export default ReasoningTrace;
