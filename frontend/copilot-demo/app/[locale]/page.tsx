"use client";

import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotChat, AssistantMessage as CopilotKitAssistantMessage } from "@copilotkit/react-ui";
import { VoiceInput } from "@/components/VoiceInput";
import { ServiceStatusCard } from "@/components/ServiceStatusCard";
import { detectTroubleshootingResults, isTroubleshootingResult, normalizeToTroubleshootingIssue } from "@/lib/troubleshooting-detector";
import { TroubleshootingCard } from "@/components/troubleshooting";
import { ChatMessagesProvider, useChatMessages as useTroubleshootingMessages } from "@/contexts/ChatMessagesContext";
import "@copilotkit/react-ui/styles.css";
import React, { useState, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import LanguageSwitcher from "../../components/LanguageSwitcher";

import { TroubleshootingIssue } from "@/types/troubleshooting";

function SanitizedAssistantMessage(props: React.ComponentProps<typeof CopilotKitAssistantMessage>) {
  const raw = (props as any)?.message?.content;
  const content = typeof raw === "string" ? raw : "";

  // Hide speech-control blocks from the visible chat bubble.
  // (We do not mutate CopilotKit's underlying message state, so TTS can still read the tags.)
  // Handle both correct [/SPEECH] and malformed [SPEECH] closing tags (LLM sometimes omits the /)
  const sanitizedContent = content
    .replace(/\[SPEECH\][\s\S]*?\[\/SPEECH\]/g, "")  // Correct format: [SPEECH]...[/SPEECH]
    .replace(/\[SPEECH\][\s\S]*?\[SPEECH\]/g, "")    // Malformed format: [SPEECH]...[SPEECH]
    .trim();

  const message = (props as any)?.message
    ? ({ ...(props as any).message, content: sanitizedContent } as any)
    : (props as any).message;

  return <CopilotKitAssistantMessage {...(props as any)} message={message} />;
}

// Custom code block renderer that detects and renders troubleshooting cards
function TroubleshootingCodeBlock({ inline, className, children, ...props }: any) {
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';

  // Only process JSON-like code blocks (not inline code).
  if (!inline && (language === 'json' || language === 'jsonc' || language === '')) {
    const code = Array.isArray(children) ? children.join('') : String(children);
    const normalized = code.replace(/\n$/, '').trim();

    // Try to parse as JSON directly (since we already have the code block content)
    let troubleshootingIssues: TroubleshootingIssue[] = [];

    try {
      const parsed = JSON.parse(normalized);

      // Check if it's a troubleshooting search results wrapper
      if (parsed && parsed.results && Array.isArray(parsed.results)) {
        const issues = parsed.results
          .filter((r: any) => isTroubleshootingResult(r))
          .map((r: any) => normalizeToTroubleshootingIssue(r))
          .filter((r: TroubleshootingIssue) => r.result_type === 'specific_solution');

        if (issues.length > 0) {
          // Deduplicate by case_id + issue_number + problem + solution
          const seenKeys = new Set<string>();
          troubleshootingIssues = issues.filter((issue: TroubleshootingIssue) => {
            const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}-${issue.solution}`;
            if (seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
          });
        }
      }
      // Check if it's a raw array of troubleshooting results (some models output this format)
      else if (Array.isArray(parsed)) {
        const issues = parsed
          .filter((r: any) => isTroubleshootingResult(r))
          .map((r: any) => normalizeToTroubleshootingIssue(r))
          .filter((r: TroubleshootingIssue) => r.result_type === 'specific_solution');

        if (issues.length > 0) {
          const seenKeys = new Set<string>();
          troubleshootingIssues = issues.filter((issue: TroubleshootingIssue) => {
            const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}-${issue.solution}`;
            if (seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
          });
        }
      }
      // Check if it's a single troubleshooting result
      else if (isTroubleshootingResult(parsed)) {
        const issue = normalizeToTroubleshootingIssue(parsed);
        if (issue.result_type === 'specific_solution') {
          troubleshootingIssues = [issue];
        }
      }
    } catch {
      // Not valid JSON or not troubleshooting data - fall through to default rendering
    }

    if (troubleshootingIssues.length > 0) {
      return (
        <div className="space-y-4 my-4">
          {troubleshootingIssues.map((issue: TroubleshootingIssue, index: number) => (
            <TroubleshootingCard
              key={`${issue.case_id}-${issue.issue_number}-${index}`}
              data={issue}
            />
          ))}
        </div>
      );
    }
  }

  // Default code block rendering
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
}
import { useChatMessages } from "@/contexts/ChatMessagesContext";

function TroubleshootingCardsOverlay() {
  const { messages } = useChatMessages();

  const allResults = useMemo(() => {
    const results: TroubleshootingIssue[] = [];

    if (!messages || !Array.isArray(messages)) {
      return results;
    }

    console.log("=== TroubleshootingCardsOverlay Debug ===");
    console.log("Messages count:", messages.length);

    for (const msg of messages) {
      if (msg && typeof msg === "object" && "content" in msg) {
        const content = typeof msg.content === "string" ? msg.content : "";
        if (content) {
          const detected = detectTroubleshootingResults(content);
          console.log(`Detected ${detected.length} results from message`);
          if (detected.length > 0) {
            console.log("First result:", JSON.stringify(detected[0], null, 2));
          }
          const issues = detected
            .filter((r): r is TroubleshootingIssue => r.result_type === "specific_solution")
            .map(r => r as TroubleshootingIssue);
          results.push(...issues);
        }
      }
    }
    console.log("Total issues for cards:", results.length);
    return results;
  }, [messages]);

  if (allResults.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 max-w-md max-h-96 overflow-y-auto space-y-4 z-50 pointer-events-none">
      {allResults.map((result, index) => (
        <div key={result.case_id || index} className="pointer-events-auto">
          <TroubleshootingCard data={result} />
        </div>
      ))}
    </div>
  );
}

import { CopilotChatRecorder } from "@/components/CopilotChatRecorder";
import { CopilotTTS } from "@/components/CopilotTTS";

export default function Home() {
  const tCopilot = useTranslations("Copilot");

  const labels = useMemo(() => ({
    title: tCopilot("title"),
    initial: tCopilot("initial"),
  }), [tCopilot]);

  const markdownTagRenderers = useMemo(() => ({
    code: TroubleshootingCodeBlock,
  }), []);

  return (
    <ChatMessagesProvider>
      <CopilotKit runtimeUrl="/api/copilotkit">
        {/* TTS component watches CopilotKit messages and speaks [SPEECH] content */}
        <CopilotTTS />
        <div className="flex flex-col lg:flex-row h-screen">

          {/* Dashboard Column - 40% on desktop, hidden on mobile */}
          <div className="hidden lg:block lg:w-[40%] overflow-y-auto bg-gradient-to-br from-blue-50 to-indigo-100">
            <MemoizedDashboardContent />
          </div>

          {/* Chat Column - 60% on desktop, full width on mobile */}
          <div className="w-full lg:w-[60%] flex flex-col border-l border-gray-200">
            <CopilotChatRecorder>
              <CopilotChat
                labels={labels}
                Input={VoiceInput}
                AssistantMessage={SanitizedAssistantMessage}
                markdownTagRenderers={markdownTagRenderers}
                className="h-full"
              />
            </CopilotChatRecorder>
          </div>

        </div>
      </CopilotKit>
    </ChatMessagesProvider>
  );
}

const MemoizedDashboardContent = React.memo(DashboardContent);

function DashboardContent() {
  const t = useTranslations("Home");
  const locale = useLocale();
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  const scenarios = ["erp", "crm", "itops", "oa", "mold"] as const;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <LanguageSwitcher />
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            {t("title")}
          </h1>
          <p className="text-lg text-gray-600">
            {t("subtitle")}
          </p>
        </div>

        {/* Management Portals */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            {t("portals.title")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <a
              href={`/${locale}/admin`}
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.adminPortal")}</div>
              <div className="text-sm text-gray-600">/{locale}/admin</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.agentApi")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000"}</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_ERPNEXT_URL || "http://localhost:8002"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.erp")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_ERPNEXT_URL || "http://localhost:8002"}</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.grafana")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001"}</div>
            </a>
          </div>

          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
            <a
              href={process.env.NEXT_PUBLIC_JAEGER_URL || "http://localhost:16686"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.jaeger")}
            </a>
            <a
              href={process.env.NEXT_PUBLIC_PROMETHEUS_URL || "http://localhost:9090"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.prometheus")}
            </a>
            <a
              href={process.env.NEXT_PUBLIC_QDRANT_URL || "http://localhost:6333"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.qdrant")}
            </a>
          </div>
        </div>

        {/* Demo Scenarios */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            {t("scenarios.title")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scenarios.map((s) => (
              <button
                key={s}
                onClick={() => setDemoScenario(s)}
                className={`p-6 rounded-lg border-2 transition-all text-left ${demoScenario === s
                  ? s === "erp" ? "border-blue-500 bg-blue-50" :
                    s === "crm" ? "border-green-500 bg-green-50" :
                      s === "itops" ? "border-orange-500 bg-orange-50" :
                        s === "mold" ? "border-teal-500 bg-teal-50" :
                          "border-purple-500 bg-purple-50"
                  : `border-gray-200 hover:${s === "erp" ? "border-blue-300" :
                    s === "crm" ? "border-green-300" :
                      s === "itops" ? "border-orange-300" :
                        s === "mold" ? "border-teal-300" :
                          "border-purple-300"
                  }`
                  }`}
              >
                <div className="text-xl font-semibold mb-2">{t(`scenarios.${s}.title`)}</div>
                <p className="text-gray-600 text-sm">
                  {t(`scenarios.${s}.desc`)}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Selected Scenario Details */}
        {demoScenario && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-semibold mb-3 text-gray-800">
              {t(`scenarios.${demoScenario}.queries`)}
            </h3>
            <ul className="space-y-2 text-gray-600">
              {(t.raw(`sampleQueries.${demoScenario}`) as string[]).map((query, i) => (
                <li key={i}>• "{query}"</li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-gray-500">
              {t("tip")}
            </p>
          </div>
        )}

        {/* System Status (moved under Scenarios) */}
        <div className="mt-6">
          <ServiceStatusCard />
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>{t("footer.poweredBy")}</p>
          <p className="mt-1">
            {t("footer.specs")}
          </p>
        </div>
      </div>
    </div>
  );
}
