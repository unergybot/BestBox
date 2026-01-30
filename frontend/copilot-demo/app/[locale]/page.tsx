"use client";

import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { VoiceInput } from "@/components/VoiceInput";
import { ServiceStatusCard } from "@/components/ServiceStatusCard";
import { detectTroubleshootingResults } from "@/lib/troubleshooting-detector";
import { TroubleshootingCard } from "@/components/troubleshooting";
import "@copilotkit/react-ui/styles.css";
import React, { useState, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import LanguageSwitcher from "../../components/LanguageSwitcher";

// Component that monitors chat messages and displays troubleshooting cards
function TroubleshootingCardsOverlay() {
  const { visibleMessages } = useCopilotChat();

  // Extract troubleshooting results from all assistant messages
  const allResults = useMemo(() => {
    const results = [];

    console.log("=== TroubleshootingCardsOverlay Debug ===");
    console.log("visibleMessages:", visibleMessages);
    console.log("visibleMessages type:", typeof visibleMessages);
    console.log("Is array:", Array.isArray(visibleMessages));

    // Guard against undefined or non-array visibleMessages
    if (!visibleMessages || !Array.isArray(visibleMessages)) {
      console.log("❌ No messages or not array");
      return results;
    }

    console.log("Message count:", visibleMessages.length);

    for (const msg of visibleMessages) {
      console.log("Processing message:", msg);
      // Check if this is an assistant message with content
      if (msg && typeof msg === "object" && "content" in msg) {
        const content = typeof msg.content === "string" ? msg.content : "";
        console.log("Message content:", content?.substring(0, 100));
        if (content) {
          const detected = detectTroubleshootingResults(content);
          console.log("Detected results:", detected.length);
          // Only include specific_solution type results
          const issues = detected.filter(r => r.result_type === "specific_solution");
          console.log("Filtered issues:", issues.length);
          results.push(...issues);
        }
      }
    }
    console.log("Total results:", results.length);
    return results;
  }, [visibleMessages]);

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

export default function Home() {
  const tCopilot = useTranslations("Copilot");

  const labels = useMemo(() => ({
    title: tCopilot("title"),
    initial: tCopilot("initial"),
  }), [tCopilot]);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <CopilotSidebar
        defaultOpen={true}
        clickOutsideToClose={false}
        labels={labels}
        Input={VoiceInput}
      >
        <MemoizedDashboardContent />
      </CopilotSidebar>
      <TroubleshootingCardsOverlay />
    </CopilotKit>
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
