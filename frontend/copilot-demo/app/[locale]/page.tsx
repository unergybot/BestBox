"use client";

import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { VoiceInput } from "@/components/VoiceInput";
import { ServiceStatusCard } from "@/components/ServiceStatusCard";
import { detectTroubleshootingResults } from "@/lib/troubleshooting-detector";
import { TroubleshootingCard } from "@/components/troubleshooting";
import { ChatMessagesProvider, useChatMessages as useTroubleshootingMessages } from "@/contexts/ChatMessagesContext";
import "@copilotkit/react-ui/styles.css";
import React, { useState, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import LanguageSwitcher from "../../components/LanguageSwitcher";

import { TroubleshootingIssue } from "@/types/troubleshooting";

// Custom code block renderer that detects and renders troubleshooting cards
function TroubleshootingCodeBlock({ inline, className, children, ...props }: any) {
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';

  // Only process JSON code blocks
  if (!inline && language === 'json') {
    const code = String(children).replace(/\n$/, '');

    try {
      const parsed = JSON.parse(code);

      // Check if this is troubleshooting data
      if (parsed && parsed.results && Array.isArray(parsed.results)) {
        const issues = parsed.results.filter((r: any) => r.result_type === 'specific_solution');

        console.log('[TroubleshootingCards] Total issues:', issues.length);

        // Deduplicate by case_id + issue_number + problem + solution (multiple solutions for same problem)
        const seenKeys = new Set<string>();
        const uniqueIssues = issues.filter((issue: TroubleshootingIssue) => {
          const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}-${issue.solution}`;
          console.log('[TroubleshootingCards] Checking:', key.substring(0, 80), 'Seen:', seenKeys.has(key));
          if (seenKeys.has(key)) {
            return false;
          }
          seenKeys.add(key);
          return true;
        });

        console.log('[TroubleshootingCards] Unique issues:', uniqueIssues.length);
        console.log('[TroubleshootingCards] About to render', uniqueIssues.length, 'cards');

        // Debug: Log each card being rendered
        uniqueIssues.forEach((issue, idx) => {
          console.log(`[TroubleshootingCards] Rendering card ${idx + 1}:`, {
            issue_number: issue.issue_number,
            problem: issue.problem.substring(0, 30),
            solution: issue.solution.substring(0, 50)
          });
        });

        if (uniqueIssues.length > 0) {
          return (
            <div className="space-y-4 my-4 p-4 border-2 border-blue-500 rounded-lg bg-blue-50">
              <div className="text-lg font-bold text-blue-900 mb-3 p-2 bg-white rounded">
                🔍 Found {uniqueIssues.length} troubleshooting solution{uniqueIssues.length > 1 ? 's' : ''}
              </div>
              {uniqueIssues.map((issue: TroubleshootingIssue, index: number) => (
                <div key={`card-${index}-${issue.issue_number}`}>
                  <div className="text-xs text-gray-500 mb-1">Card {index + 1} of {uniqueIssues.length}</div>
                  <TroubleshootingCard
                    data={issue}
                  />
                </div>
              ))}
            </div>
          );
        }
      }
    } catch (e) {
      // Not troubleshooting JSON, fallback to default
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

        {/* Service Health Status */}
        <ServiceStatusCard />

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
